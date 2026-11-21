from datetime import datetime, timezone
import random
import unittest

from energy import EnergyService
from simulate import ROOM_IDS, reading, sample
from sqlite_store import SQLiteStore


class SimulatorTest(unittest.TestCase):
    def test_room_patterns_and_api_compatible_payloads(self):
        rng = random.Random(18)
        daytime = datetime(2026, 7, 3, 9, 45, tzinfo=timezone.utc)
        night = daytime.replace(hour=21)
        store = SQLiteStore(":memory:")
        self.addCleanup(store.close)
        service = EnergyService(store, "local", clock=lambda: daytime)
        readings = []
        for room in ROOM_IDS:
            normal = reading(room, daytime, rng)
            readings.append(normal["power_kw"])
            self.assertEqual(service.ingest(normal)[0], 201)
            self.assertGreater(normal["power_kw"], sample(room, night, rng))
            self.assertGreater(sample(room, daytime, rng, spike=True), normal["power_kw"])
        self.assertEqual(len(set(readings)), 3)
