"""Generate one API reading per room every five seconds."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
import queue
import random
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo


ROOM_IDS = ("computer-lab", "library", "classroom")
TIMEZONE = ZoneInfo("Asia/Kolkata")
DEMO_TOKEN = "ecosync-local-demo"
SPIKE_KW = {"computer-lab": 6.4, "library": 4.1, "classroom": 3.7}


def sample(room_id, now, rng, spike=False):
    if spike:
        return SPIKE_KW[room_id]
    local = now.astimezone(TIMEZONE)
    hour = local.hour + local.minute / 60
    evening = 0.40 + 0.60 * math.exp(-((hour - 13) / 5.5) ** 2)
    morning = math.exp(-((hour - 10.6) / 2.4) ** 2)
    afternoon = math.exp(-((hour - 15.6) / 2.7) ** 2)
    weekday = 0.94 if local.weekday() >= 5 else 1
    base, load, wave = {
        "computer-lab": (0.78, 2.25 * morning + 2.75 * afternoon + 0.42 * evening, 0.16),
        "library": (0.5, 1.25 * evening + 0.45 * afternoon, 0.07),
        "classroom": (0.37, 0.91 * morning + 1.16 * afternoon + 0.32 * evening, 0.11),
    }[room_id]
    fluctuation = wave * math.sin(hour * 2.1 + len(room_id))
    return round(max(0.2, base + weekday * load + fluctuation + rng.uniform(-0.065, 0.065)), 3)


def reading(room_id, now, rng, spike=False):
    return {"room_id": room_id, "timestamp": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "power_kw": sample(room_id, now, rng, spike)}


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(opener, url, token, payload):
    request = Request(url + "/readings", data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with opener.open(request, timeout=3) as response:
                return json.load(response)
        except HTTPError as error:
            with error:
                detail = error.read(1024).decode(errors="replace")
                message = f"HTTP {error.code} {detail}"
            if error.code not in {429, 500, 502, 503, 504}:
                print(f'{payload["room_id"]}: {message}', file=sys.stderr, flush=True)
                if error.code in {401, 403, 404}:
                    raise SystemExit("Check ECOSYNC_API_URL and ECOSYNC_TOKEN.")
                return None
        except (URLError, TimeoutError, OSError, ValueError) as error:
            message = str(error)
        if attempt < 2:
            time.sleep(0.35 * (2 ** attempt))
    print(f'{payload["room_id"]}: dropped after three attempts ({message})', file=sys.stderr, flush=True)
    return None


def listen(commands):
    for line in sys.stdin:
        commands.put(line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="While running, type a room ID and press Enter to trigger a spike.")
    parser.add_argument("--url", default=os.getenv("ECOSYNC_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--spike", choices=ROOM_IDS, help="Spike this room on cycles two and three.")
    parser.add_argument("--spike-every", type=int, default=0, metavar="CYCLES", help="Optional recurring spikes, minimum 4 cycles.")
    parser.add_argument("--cycles", type=int, default=0, help="Stop after N cycles. Zero runs until interrupted.")
    parser.add_argument("--seed", type=int, help="Repeatable random variations.")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    endpoint = urlsplit(url)
    loopback = endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
    if not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or (
            endpoint.scheme != "https" and not (endpoint.scheme == "http" and loopback)):
        parser.error("Use HTTPS for AWS or HTTP on loopback, without credentials, query or fragment.")
    token = os.getenv("ECOSYNC_TOKEN") or (DEMO_TOKEN if loopback else "")
    if not token or (not loopback and len(token) < 32):
        parser.error("Set ECOSYNC_TOKEN to the AWS stack's write token (minimum 32 characters).")
    if args.cycles < 0 or (args.spike_every and args.spike_every < 4):
        parser.error("--cycles cannot be negative and --spike-every must be zero or at least 4.")

    rng = random.Random(args.seed)
    opener = build_opener(RejectRedirects())
    commands = queue.Queue()
    threading.Thread(target=listen, args=(commands,), daemon=True).start()
    held = {}
    if sys.stdin.isatty():
        print("Trigger a spike by entering computer-lab, library or classroom.", flush=True)
    cycle = 0
    deadline = time.monotonic()
    try:
        while not args.cycles or cycle < args.cycles:
            cycle += 1
            if args.spike and cycle == 2:
                held[args.spike] = 2
            if args.spike_every and cycle % args.spike_every == 0:
                held[rng.choice(ROOM_IDS)] = 2
            while not commands.empty():
                room_id = commands.get_nowait()
                if room_id in ROOM_IDS:
                    held[room_id] = 2
                elif room_id:
                    print("Enter computer-lab, library or classroom.", flush=True)
            now = datetime.now(timezone.utc)
            for room_id in ROOM_IDS:
                spike = held.get(room_id, 0) > 0
                payload = reading(room_id, now, rng, spike)
                result = post(opener, url, token, payload)
                if result:
                    status = "duplicate" if result["duplicate"] else result["alert_transition"]
                    print(f'{payload["timestamp"]} {room_id:<13} {payload["power_kw"]:5.3f} kW  {status}', flush=True)
                if spike:
                    held[room_id] -= 1
            if args.cycles and cycle == args.cycles:
                break
            deadline = max(deadline + 5, time.monotonic())
            time.sleep(max(0, deadline - time.monotonic()))
    except KeyboardInterrupt:
        print("\nSimulator stopped.", flush=True)


if __name__ == "__main__":
    main()
