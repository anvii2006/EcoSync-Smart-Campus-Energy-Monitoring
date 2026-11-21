"""Load optional demonstration history into a fresh local SQLite database."""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys

from simulate import ROOM_IDS, TIMEZONE, reading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from energy import EnergyService
from local import DEFAULT_DB
from sqlite_store import SQLiteStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--days", type=int, choices=range(1, 8), default=7)
    args = parser.parse_args()
    store = SQLiteStore(args.db)
    try:
        if any(store.get(f"ROOM#{room}", "META") for room in ROOM_IDS):
            parser.error("This database already has readings. Specify a fresh path with --db.")
        engine = EnergyService(store, "local")
        rng = random.Random(123)
        now = datetime.now(timezone.utc)
        today = now.astimezone(TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = (today - timedelta(days=args.days - 1)).astimezone(timezone.utc)
        count = 0
        while cursor < now:
            local = cursor.astimezone(TIMEZONE)
            scripted_event = local.date() == (today - timedelta(days=1)).date() and (
                local.hour == 14 and 12 <= local.minute < 16
            )
            for room in ROOM_IDS:
                engine.ingest(reading(room, cursor, rng, scripted_event and room == "computer-lab"))
                count += 1
            cursor += timedelta(minutes=2)
        last = datetime.now(timezone.utc) - timedelta(seconds=1)
        if last > cursor - timedelta(minutes=2):
            for room in ROOM_IDS:
                engine.ingest(reading(room, last, rng))
                count += 1
        print(f"Seeded {count:,} simulated readings into {args.db}. Start the local API and simulator.")
    finally:
        store.close()


if __name__ == "__main__":
    main()
