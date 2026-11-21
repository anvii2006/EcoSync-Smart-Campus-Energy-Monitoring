"""Electricity telemetry, energy integration and anomaly rules."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from time import sleep
from zoneinfo import ZoneInfo

from store import Conflict, Increment, Put


UTC = timezone.utc
CAMPUS = ZoneInfo("Asia/Kolkata")
EARLIEST_TIMESTAMP = datetime(2000, 1, 1, tzinfo=UTC)
ROOMS = {
    "computer-lab": {"name": "Computer Lab", "location": "Technology Wing", "threshold_kw": 4.8},
    "library": {"name": "Library", "location": "Main Building", "threshold_kw": 2.8},
    "classroom": {"name": "Classroom", "location": "Academic Wing", "threshold_kw": 2.4},
}
SETTINGS = "SYSTEM", "SETTINGS"
DEFAULTS = {
    "tariff_inr_per_kwh": 8,
    "emission_kg_per_kwh": 0.71,
    "thresholds_kw": {room_id: room["threshold_kw"] for room_id, room in ROOMS.items()},
}
SLOT = timedelta(minutes=30)
MAX_GAP_SECONDS = 120
STALE_SECONDS = 20
SCALE = 1_000_000_000


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def iso(dt):
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str) or not 20 <= len(value) <= 32 or "T" not in value:
        raise ApiError(400, "timestamp must be an ISO 8601 datetime with a timezone.")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError
        dt = dt.astimezone(UTC)
    except (ValueError, OverflowError):
        raise ApiError(400, "timestamp must be an ISO 8601 datetime with a timezone.") from None
    if dt < EARLIEST_TIMESTAMP:
        raise ApiError(400, "timestamp must be on or after 2000-01-01 UTC.")
    return dt


def number(value, low, high, field):
    if type(value) not in (int, float) or not low <= value <= high or not isfinite(value):
        raise ApiError(400, f"{field} must be a number from {low} to {high}.")
    return round(value, 9)


def validate_room(room_id):
    if not isinstance(room_id, str) or room_id not in ROOMS:
        raise ApiError(400, "room_id must be computer-lab, library or classroom.")
    return room_id


def estimate(energy, settings):
    return {
        "energy_kwh": round(energy, 8),
        "cost_inr": round(energy * settings["tariff_inr_per_kwh"], 6),
        "carbon_kg": round(energy * settings["emission_kg_per_kwh"], 6),
    }


def slot_start(dt):
    local = dt.astimezone(CAMPUS)
    return local.replace(minute=(local.minute // 30) * 30, second=0, microsecond=0)


def interval_totals(previous, reading):
    """Allocate a trapezoid across local half-hour slots and calendar days."""
    totals = defaultdict(lambda: {"energy_nkwh": 0, "duration_ms": 0})
    if previous is None:
        return totals
    start, end = timestamp(previous["timestamp"]), timestamp(reading["timestamp"])
    gap = (end - start).total_seconds()
    if not 0 < gap <= MAX_GAP_SECONDS:
        return totals

    start_kw, end_kw = previous["power_kw"], reading["power_kw"]
    cursor = start
    while cursor < end:
        slot = slot_start(cursor)
        stop = min(end, slot + SLOT)
        seconds = (stop - cursor).total_seconds()
        power_at_start = start_kw + (end_kw - start_kw) * (cursor - start).total_seconds() / gap
        power_at_end = start_kw + (end_kw - start_kw) * (stop - start).total_seconds() / gap
        energy = round((power_at_start + power_at_end) / 2 * seconds / 3600 * SCALE)
        for key in ("DAY#" + slot.date().isoformat(), "SLOT#" + iso(slot)):
            totals[key]["energy_nkwh"] += energy
            totals[key]["duration_ms"] += round(seconds * 1000)
        cursor = stop
    return totals


def anomaly(reading, previous, active, threshold):
    power = reading["power_kw"]
    current = reading["timestamp"]
    reasons = []
    if power > threshold:
        reasons.append("threshold")

    baseline = previous["power_kw"] if previous else None
    comparable = previous and (timestamp(current) - timestamp(previous["timestamp"])).total_seconds() <= MAX_GAP_SECONDS
    spike = comparable and power >= baseline * 1.8 and power - baseline >= 0.75
    if spike:
        reasons.append("spike")
    if active:
        recovery = active.get("spike_recovery_kw")
        if reasons or (recovery is not None and power > min(threshold, recovery)):
            updated = {**active, "peak_kw": max(active["peak_kw"], power)}
            updated["reasons"] = list(dict.fromkeys(active["reasons"] + reasons))
            if recovery is None and spike:
                updated["spike_recovery_kw"] = round(baseline + 0.4, 4)
            return updated, "continued"
        return {**active, "resolved_at": current, "status": "resolved"}, "resolved"
    if reasons:
        return {
            "id": f'{reading["room_id"]}/{current}',
            "room_id": reading["room_id"],
            "started_at": current,
            "resolved_at": None,
            "status": "active",
            "reasons": reasons,
            "initial_kw": power,
            "peak_kw": power,
            "threshold_kw": threshold,
            "spike_recovery_kw": round(baseline + 0.4, 4) if spike else None,
        }, "opened"
    return None, "normal"


class EnergyService:
    def __init__(self, store, mode, clock=None):
        self.store = store
        self.mode = mode
        self.clock = clock or (lambda: datetime.now(UTC))

    def settings(self):
        settings = {**DEFAULTS, "version": 1}
        for attempt in range(4):
            saved = self.store.get(*SETTINGS)
            if saved is not None:
                return saved
            try:
                self.store.commit([Put(*SETTINGS, settings, ("version", None))])
                return settings
            except Conflict:
                sleep(0.02 * (attempt + 1))
        raise ApiError(503, "Settings are busy. Retry shortly.")

    def config(self):
        settings = self.settings()
        return {
            **{field: settings[field] for field in DEFAULTS},
            "mode": self.mode,
            "timezone": str(CAMPUS),
            "working_hours": {"start": "08:00", "end": "18:00"},
            "poll_interval_seconds": 5,
            "max_integration_gap_seconds": MAX_GAP_SECONDS,
        }

    def update_config(self, body):
        if not isinstance(body, dict) or not body or set(body) - DEFAULTS.keys():
            raise ApiError(400, "Provide tariff_inr_per_kwh, emission_kg_per_kwh or thresholds_kw.")
        overrides = {}
        for field, maximum in (("tariff_inr_per_kwh", 1000), ("emission_kg_per_kwh", 10)):
            if field in body:
                overrides[field] = number(body[field], 0, maximum, field)
        thresholds = body.get("thresholds_kw", {})
        if not isinstance(thresholds, dict):
            raise ApiError(400, "thresholds_kw must be an object keyed by room ID.")
        for room_id, value in thresholds.items():
            validate_room(room_id)
            thresholds[room_id] = number(value, 0.1, 100, f"thresholds_kw.{room_id}")
        for attempt in range(4):
            previous = self.settings()
            updated = {**previous, **overrides, "version": previous["version"] + 1,
                       "thresholds_kw": {**previous["thresholds_kw"], **thresholds}}
            try:
                self.store.commit([Put(*SETTINGS, updated, ("version", previous["version"]))])
                return self.config()
            except Conflict:
                sleep(0.02 * (attempt + 1))
        raise ApiError(503, "Settings are busy. Retry shortly.")

    def ingest(self, body):
        if not isinstance(body, dict) or set(body) != {"room_id", "timestamp", "power_kw"}:
            raise ApiError(400, "Provide room_id, timestamp and power_kw.")
        room_id = validate_room(body["room_id"])
        dt = timestamp(body["timestamp"])
        if dt > self.clock() + timedelta(seconds=30):
            raise ApiError(400, "timestamp is outside the accepted range.")
        reading = {"room_id": room_id, "timestamp": iso(dt),
                   "power_kw": number(body["power_kw"], 0, 100, "power_kw")}
        pk, key = f"ROOM#{room_id}", "READING#" + reading["timestamp"]
        for attempt in range(4):
            existing = self.store.get(pk, key)
            if existing:
                if existing["power_kw"] != reading["power_kw"]:
                    raise ApiError(409, "A different reading already uses this timestamp.")
                return 200, {"reading": existing, "duplicate": True}
            state = self.store.get(pk, "META") or {}
            previous = state.get("latest")
            if previous and previous["timestamp"] >= reading["timestamp"]:
                # A concurrent request may have committed this reading after our first lookup.
                existing = self.store.get(pk, key)
                if existing and existing["power_kw"] == reading["power_kw"]:
                    return 200, {"reading": existing, "duplicate": True}
                raise ApiError(409, "Readings must arrive in timestamp order for each room.")
            threshold = self.settings()["thresholds_kw"][room_id]
            old_alert = state.get("active_alert")
            alert, transition = anomaly(reading, previous, old_alert, threshold)
            metadata = {
                "room_id": room_id, "name": ROOMS[room_id]["name"], "location": ROOMS[room_id]["location"],
                "latest": reading, "version": reading["timestamp"],
                "active_alert": None if transition == "resolved" else alert,
            }
            changes = [
                Put(pk, "META", metadata, ("version", state.get("version"))),
                Put(pk, key, reading, ("timestamp", None)),
            ]
            if alert and alert != old_alert:
                changes.append(Put(pk, "ALERT#" + alert["started_at"], alert))
            changes.extend(Increment(pk, rollup, values) for rollup, values in
                           interval_totals(previous, reading).items())
            try:
                self.store.commit(changes)
                return 201, {"reading": reading, "duplicate": False, "alert_transition": transition}
            except Conflict:
                sleep(0.02 * (attempt + 1))
        raise ApiError(503, "Room is busy. Retry shortly.")

    def rooms(self):
        settings = self.settings()
        now = self.clock()
        result = []
        for room_id, room in ROOMS.items():
            pk = f"ROOM#{room_id}"
            state = self.store.get(pk, "META") or {}
            latest = state.get("latest")
            stale = latest is None or (now - timestamp(latest["timestamp"])).total_seconds() > STALE_SECONDS
            result.append({
                "id": room_id, "name": state.get("name", room["name"]),
                "location": state.get("location", room["location"]),
                "threshold_kw": settings["thresholds_kw"][room_id],
                "latest": latest, "stale": stale, "active_alert": state.get("active_alert"),
            })
        fresh = [room["latest"]["power_kw"] for room in result if not room["stale"]]
        return {
            "rooms": result,
            "current_power_kw": round(sum(fresh), 4) if fresh else None,
            "reporting_rooms": len(fresh),
            "as_of": iso(now),
        }

    def readings(self, room_id, start, end, limit):
        return {"readings": [
            item for _, item in self.store.query(f"ROOM#{room_id}", "READING#" + iso(start),
                                                  "READING#" + iso(end), limit, newest=True)
        ]}

    def alerts(self, room_id=None, limit=50):
        ids = [room_id] if room_id else ROOMS
        active, history = [], []
        for key in ids:
            pk = f"ROOM#{key}"
            current = (self.store.get(pk, "META") or {}).get("active_alert")
            if current:
                active.append(current)
            history.extend(item for _, item in self.store.query(pk, "ALERT#", "ALERT#~", limit, newest=True))
        return {
            "active": sorted(active, key=lambda alert: alert["started_at"], reverse=True),
            "history": sorted(history, key=lambda alert: alert["started_at"], reverse=True)[:limit],
        }

    def analytics(self, period, room_id=None):
        now = self.clock().astimezone(CAMPUS)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days = {"today": 1, "7d": 7, "30d": 30}[period]
        start = today - timedelta(days=days - 1)
        settings = self.settings()
        ids = [room_id] if room_id else list(ROOMS)
        per_day = {(start + timedelta(days=i)).date().isoformat(): {} for i in range(days)}
        slots = {}
        if period == "today":
            count = int((slot_start(now) - today) / SLOT) + 1
            slots = {iso(today + i * SLOT): {} for i in range(count)}
        comparison = []
        total = 0
        for key in ids:
            pk = f"ROOM#{key}"
            room_total = 0
            day_items = self.store.query(pk, "DAY#" + start.date().isoformat(), "DAY#" + today.date().isoformat())
            for sk, item in day_items:
                room_total += item["energy_nkwh"]
                per_day[sk[4:]][key] = item["energy_nkwh"] / SCALE
            for sk, item in (self.store.query(pk, "SLOT#" + iso(today), "SLOT#" + iso(slot_start(now))) if slots else []):
                slots[sk[5:]][key] = item["energy_nkwh"] / SCALE * 3_600_000 / item["duration_ms"]
            total += room_total
            comparison.append({"room_id": key, "has_data": bool(day_items), **estimate(room_total / SCALE, settings)})
        daily = [
            {"at": date, "rooms": values, "value": sum(values.values()) if values else None,
             **estimate(sum(values.values()), settings)}
            for date, values in per_day.items()
        ]
        series = [{"at": at, "rooms": values, "value": round(sum(values.values()), 5) if values else None}
                  for at, values in slots.items()] if slots else daily
        return {
            "period": period, "from": iso(start), "to": iso(now),
            "series_unit": "kW" if slots else "kWh", "series": series,
            "daily": daily, "by_room": comparison, "totals": estimate(total / SCALE, settings),
            "tariff_inr_per_kwh": settings["tariff_inr_per_kwh"],
            "emission_kg_per_kwh": settings["emission_kg_per_kwh"],
            "has_data": any(day["value"] is not None for day in daily),
        }

    def recommendations(self, rooms=None):
        if rooms is None:
            rooms = self.rooms()["rooms"]
        result = []
        for room in rooms:
            alert = room["active_alert"]
            power = room["latest"]["power_kw"] if room["latest"] else 0
            key = room["id"]
            if alert:
                spike = "spike" in alert["reasons"]
                result.append({
                    "room_id": key, "type": "spike" if spike else "threshold",
                    "title": "Inspect an unexpected load" if spike else "Check high-draw equipment",
                    "message": "Check which equipment started when the spike began." if spike
                               else "Switch off unnecessary appliances and verify the room threshold.",
                })
            elif not room["stale"] and power >= 0.85 * room["threshold_kw"]:
                result.append({
                    "room_id": key, "type": "high", "title": "Review equipment in use",
                    "message": "This room is near its configured limit. Turn off equipment that is idle.",
                })
            if not room["stale"]:
                hour = timestamp(room["latest"]["timestamp"]).astimezone(CAMPUS).hour
                if (hour < 8 or hour >= 18) and power >= 0.45 * room["threshold_kw"]:
                    result.append({
                        "room_id": key, "type": "after_hours", "title": "Reduce after-hours usage",
                        "message": "Switch off unused lighting, computers and HVAC outside 08:00–18:00 IST.",
                    })
        return result
