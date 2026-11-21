import concurrent.futures
from contextlib import closing
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from api import handle
from energy import ApiError, EnergyService, iso
from local import make_server
from sqlite_store import SQLiteStore


NOW = datetime(2026, 7, 3, 9, 0, tzinfo=timezone.utc)
ORIGIN = "http://127.0.0.1:5173"
TOKEN = "local-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteStore(":memory:")
        self.addCleanup(self.store.close)
        self.service = EnergyService(self.store, "local", clock=lambda: NOW)
        self.start = NOW - timedelta(minutes=4)

    def sample(self, seconds=0, power=2, room="computer-lab", start=None):
        return {"room_id": room, "timestamp": iso((start or self.start) + timedelta(seconds=seconds)),
                "power_kw": power}

    def request(self, method, path, *, query=None, headers=None, data=None, raw=None):
        status, result_headers, body = handle(
            self.service, TOKEN, ORIGIN, method, path, query, headers,
            raw if raw is not None else json.dumps(data).encode(),
        )
        return status, result_headers, json.loads(body) if body else None

    def test_integrates_trapezoid_and_estimates_cost_and_carbon(self):
        self.service.ingest(self.sample(power=2))
        self.service.ingest(self.sample(60, 4))
        data = self.service.analytics("today")
        self.assertAlmostEqual(data["totals"]["energy_kwh"], 0.05)
        self.assertAlmostEqual(data["totals"]["cost_inr"], 0.4)
        self.assertAlmostEqual(data["totals"]["carbon_kg"], 0.0355)
        slot = next(slot for slot in data["series"] if slot["value"] is not None)
        self.assertAlmostEqual(slot["value"], 3)

    def test_three_rooms_total_one_kwh_at_default_rates(self):
        start = NOW - timedelta(minutes=10)
        powers = {"computer-lab": 3, "library": 1.5, "classroom": 1.5}
        for room, power in powers.items():
            for seconds in range(0, 601, 60):
                self.service.ingest(self.sample(seconds, power, room, start))
        self.assertEqual(self.service.rooms()["reporting_rooms"], 3)
        self.assertEqual(self.service.rooms()["current_power_kw"], 6)
        for period in ("today", "7d", "30d"):
            data = self.service.analytics(period)
            self.assertEqual(data["tariff_inr_per_kwh"], 8)
            self.assertEqual(data["emission_kg_per_kwh"], 0.71)
            self.assertAlmostEqual(data["totals"]["energy_kwh"], 1)
            self.assertEqual(data["totals"]["cost_inr"], 8)
            self.assertEqual(data["totals"]["carbon_kg"], 0.71)
            self.assertEqual([row["energy_kwh"] for row in data["by_room"]], [0.5, 0.25, 0.25])
            self.assertTrue(all(row["has_data"] for row in data["by_room"]))

    def test_measured_zero_is_distinct_from_missing_data(self):
        for seconds in (0, 5):
            self.service.ingest(self.sample(seconds, 0))
        data = self.service.analytics("today")
        self.assertEqual(data["daily"][0]["rooms"], {"computer-lab": 0})
        self.assertEqual(data["daily"][0]["energy_kwh"], 0)
        self.assertEqual([row["has_data"] for row in data["by_room"]], [True, False, False])

    def test_does_not_bridge_long_gaps_or_invent_power(self):
        self.service.ingest(self.sample(power=2))
        self.service.ingest(self.sample(121, 4))
        data = self.service.analytics("today")
        self.assertEqual(data["totals"]["energy_kwh"], 0)
        self.assertFalse(data["has_data"])
        self.assertTrue(all(point["value"] is None for point in data["series"]))
        rooms = self.service.rooms()
        self.assertEqual(rooms["reporting_rooms"], 0)
        self.assertIsNone(rooms["current_power_kw"])

    def test_cross_midnight_with_zero_later_power(self):
        start = datetime(2026, 7, 2, 18, 29, 30, tzinfo=timezone.utc)
        self.service.ingest(self.sample(power=4, start=start))
        self.service.ingest(self.sample(60, 0, start=start))
        daily = self.service.analytics("7d")["daily"]
        self.assertAlmostEqual(daily[-2]["energy_kwh"], 0.025)
        self.assertAlmostEqual(daily[-1]["energy_kwh"], 1 / 120)
        self.assertAlmostEqual(self.service.analytics("7d")["totals"]["energy_kwh"], 1 / 30)

    def test_threshold_alert_opens_continues_and_resolves(self):
        transitions = [self.service.ingest(self.sample(i * 5, power))[1]["alert_transition"]
                       for i, power in enumerate((4, 5, 5.5, 3, 0))]
        self.assertEqual(transitions, ["normal", "opened", "continued", "resolved", "normal"])
        alerts = self.service.alerts()
        self.assertEqual(len(alerts["history"]), 1)
        self.assertEqual(alerts["active"], [])
        alert = alerts["history"][0]
        self.assertEqual(alert["reasons"], ["threshold"])
        self.assertEqual(alert["peak_kw"], 5.5)
        self.assertIsNotNone(alert["resolved_at"])

    def test_spike_below_threshold_stays_active_until_recovery(self):
        for i, power in enumerate((1.5, 3, 3, 2.4)):
            self.service.ingest(self.sample(i * 5, power))
        active = self.service.alerts()["active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["reasons"], ["spike"])
        self.assertEqual(self.service.recommendations()[0]["type"], "spike")
        self.service.ingest(self.sample(20, 1.7))
        self.assertEqual(len(self.service.alerts()["history"]), 1)
        self.assertEqual(self.service.alerts()["active"], [])

    def test_after_hours_recommendation_uses_campus_time_and_freshness(self):
        overnight = datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc)
        service = EnergyService(self.store, "local", clock=lambda: overnight)
        service.ingest(self.sample(power=1.5, room="library", start=overnight))
        types = {item["type"] for item in service.recommendations()}
        self.assertIn("after_hours", types)
        self.assertEqual(service.rooms()["current_power_kw"], 1.5)
        self.assertEqual(self.service.recommendations(
            [{**service.rooms()["rooms"][1], "stale": True}]
        ), [])

    def test_high_and_threshold_recommendations_clear_on_recovery(self):
        for i, power in enumerate((3, 4.5, 5.1, 5.4, 3)):
            sample = self.sample(i * 5, power, start=NOW - timedelta(seconds=20))
            self.service.ingest(sample)
            result = self.request("GET", "/rooms")[2]["recommendations"]
            expected = ([], ["high"], ["threshold"], ["threshold"], [])[i]
            self.assertEqual([item["type"] for item in result], expected)
        alerts = self.service.alerts()
        self.assertEqual(len(alerts["history"]), 1)
        self.assertEqual(alerts["history"][0]["peak_kw"], 5.4)
        self.assertEqual(alerts["active"], [])

    def test_historical_reads_and_alerts_survive_reopening_sqlite(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            original = self.sample(power=2)
            spike = self.sample(5, 6.4)
            recovery = self.sample(10, 2)
            with closing(SQLiteStore(path)) as first:
                self.service = EnergyService(first, "local", clock=lambda: NOW)
                for sample in (original, spike, recovery):
                    self.assertEqual(self.service.ingest(sample)[0], 201)
                self.service.update_config({"tariff_inr_per_kwh": 9})

            with closing(SQLiteStore(path)) as reopened:
                self.service = EnergyService(reopened, "local", clock=lambda: NOW)
                query = {"room_id": "computer-lab", "from": original["timestamp"],
                         "to": spike["timestamp"], "limit": "2"}
                history = self.request("GET", "/readings", query=query)[2]
                self.assertEqual(history["readings"], [spike, original])
                data = self.request("GET", "/analytics", query={"period": "7d"})[2]
                self.assertAlmostEqual(data["totals"]["energy_kwh"], 42 / 3600)
                self.assertEqual(data["tariff_inr_per_kwh"], 9)
                self.assertEqual(self.request("GET", "/alerts")[2]["history"][0]["resolved_at"],
                                 recovery["timestamp"])

    def test_idempotency_and_ordering(self):
        self.service.ingest(self.sample())
        payload = self.sample(10)
        self.service.ingest(payload)
        self.assertEqual(self.service.ingest(payload)[0], 200)
        for invalid in (self.sample(5), self.sample(10, 3)):
            with self.assertRaises(ApiError) as ctx:
                self.service.ingest(invalid)
            self.assertEqual(ctx.exception.status, 409)
        self.assertAlmostEqual(self.service.analytics("today")["totals"]["energy_kwh"], 20 / 3600)

    def test_concurrent_duplicate_updates_rollups_once(self):
        self.service.ingest(self.sample())
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            codes = list(executor.map(lambda _: self.service.ingest(self.sample(5))[0], range(8)))
        self.assertEqual(codes.count(201), 1)
        self.assertEqual(codes.count(200), 7)
        self.assertAlmostEqual(self.service.analytics("today")["totals"]["energy_kwh"], 10 / 3600)

    def test_authentication_content_type_and_json(self):
        args = ("POST", "/readings")
        self.assertEqual(self.request(*args, data=self.sample())[0], 401)
        self.assertEqual(self.request(*args, headers={"Authorization": f"Bearer {TOKEN}"})[0], 415)
        self.assertEqual(self.request(*args, headers=AUTH, raw=b"{bad")[0], 400)
        self.assertEqual(self.request(*args, headers=AUTH, raw=b" " * 4097)[0], 413)
        status, response_headers, response = self.request(*args, headers=AUTH, data=self.sample())
        self.assertEqual(status, 201)
        self.assertEqual(response_headers["Access-Control-Allow-Origin"], ORIGIN)
        self.assertEqual(response["reading"], self.sample())
        self.assertEqual(self.request(*args, headers=AUTH, data=self.sample())[0], 200)

    def test_reading_validation(self):
        for extra in ({"room_id": "invalid"}, {"room_id": []}, {"power_kw": -1}, {"power_kw": 101},
                      {"power_kw": True}, {"power_kw": float("nan")}, {"timestamp": "2026-07-03T09:00:00"},
                      {"timestamp": iso(NOW + timedelta(seconds=31))}, {"unknown": 3}):
            with self.subTest(extra=extra):
                self.assertEqual(self.request("POST", "/readings", headers=AUTH,
                                              data={**self.sample(), **extra})[0], 400)

    def test_read_contracts_and_query_validation(self):
        self.service.ingest(self.sample())
        self.service.ingest(self.sample(5, room="library"))
        self.assertEqual(self.request("GET", "/config")[2]["mode"], "local")
        self.assertEqual(len(self.request("GET", "/rooms")[2]["rooms"]), 3)
        self.assertEqual(self.request("GET", "/alerts")[2], {"active": [], "history": []})
        self.assertEqual(self.request("GET", "/readings", query={"room_id": "library"})[2]["readings"],
                         [self.sample(5, room="library")])
        self.assertEqual(self.request("GET", "/readings")[0], 400)
        self.assertEqual(self.request("GET", "/readings", query={
            "room_id": "library", "from": iso(NOW), "to": iso(NOW - timedelta(minutes=5)),
        })[0], 400)
        self.assertEqual(self.request("GET", "/readings", query={
            "room_id": "library", "to": "0001-01-01T00:00:00Z",
        })[0], 400)
        self.assertEqual(self.request("GET", "/analytics", query={"period": "90d"})[0], 400)
        self.assertEqual(self.request("GET", "/alerts", query={"limit": "-1"})[0], 400)
        self.assertEqual(self.request("GET", "/missing")[0], 404)
        self.assertEqual(self.request("POST", "/alerts")[0], 405)
        self.assertEqual(self.request("OPTIONS", "/config")[0], 204)

    def test_update_config_recalculates_estimates_and_applies_threshold(self):
        update = {"tariff_inr_per_kwh": 10, "emission_kg_per_kwh": 0.5, "thresholds_kw": {"computer-lab": 1.9}}
        self.assertEqual(self.request("PUT", "/config", data=update)[0], 401)
        self.assertEqual(self.request("PUT", "/config", headers=AUTH, data={"thresholds_kw": None})[0], 400)
        self.assertEqual(self.request("PUT", "/config", headers=AUTH, data=update)[2]["tariff_inr_per_kwh"], 10)
        self.assertEqual(self.service.ingest(self.sample())[1]["alert_transition"], "opened")
        self.service.ingest(self.sample(60))
        data = self.service.analytics("7d", "computer-lab")
        self.assertAlmostEqual(data["totals"]["cost_inr"], 1 / 3, places=5)
        self.assertAlmostEqual(data["totals"]["carbon_kg"], 1 / 60, places=5)
        self.assertEqual(len(data["by_room"]), 1)

    def test_local_http_roundtrip(self):
        server = make_server("127.0.0.1", 0, self.service, TOKEN, ORIGIN)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}"
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(url + "/readings", data=b"{}", method="POST"), timeout=2)
        self.assertEqual(ctx.exception.code, 401)
        ctx.exception.close()
        with urlopen(Request(url + "/readings", method="POST", headers=AUTH,
                             data=json.dumps(self.sample()).encode()), timeout=2) as response:
            self.assertEqual(response.status, 201)
        with urlopen(url + "/readings?room_id=computer-lab", timeout=2) as response:
            self.assertEqual(json.load(response)["readings"], [self.sample()])
