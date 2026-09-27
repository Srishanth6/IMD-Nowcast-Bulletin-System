#!/usr/bin/env python3
"""Run the full IMD nowcast bulletin pipeline on a 3-hour IST schedule."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IST = timezone(timedelta(hours=5, minutes=30))
SCHEDULE_HOURS = (0, 3, 6, 9, 12, 15, 18, 21)
STOP = False


def now_ist() -> datetime:
    return datetime.now(IST)


def next_schedule_time(now: datetime | None = None) -> datetime:
    current = (now or now_ist()).astimezone(IST)
    for hour in SCHEDULE_HOURS:
        candidate = current.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > current:
            return candidate
    tomorrow = current + timedelta(days=1)
    return tomorrow.replace(hour=SCHEDULE_HOURS[0], minute=0, second=0, microsecond=0)


def handle_shutdown(signum, frame):
    global STOP
    STOP = True
    print(f"[{now_ist().strftime('%H:%M')} IST] Scheduler stopping gracefully.")


def run_cycle_once():
    sys.path.insert(0, str(ROOT))
    from generate_bulletin import run_bulletin_cycle

    return run_bulletin_cycle()


def parse_args():
    parser = argparse.ArgumentParser(description="Run the IMD nowcast bulletin scheduler.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle immediately and exit.")
    parser.add_argument("--sleep-seconds", type=int, default=60, help="Polling interval while waiting for the next 3-hour slot.")
    return parser.parse_args()


def main():
    args = parse_args()
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("=" * 70)
    print(" IMD NOWCAST BULLETIN SCHEDULER (IST / 3-HOUR CYCLES)")
    print("=" * 70)

    if args.once:
        print(f"[{now_ist().strftime('%H:%M:%S')} IST] Single-cycle test mode: running bulletin pipeline immediately.")
        result = run_cycle_once()
        print(f"Single-cycle result: {result.get('status', 'unknown')}")
        if result.get('status') == 'failed':
            return 1
        return 0

    initial_run_done = False
    while not STOP:
        now = now_ist()
        if not initial_run_done:
            print(f"[{now.strftime('%H:%M:%S')} IST] Starting immediate bulletin cycle")
            run_cycle_once()
            initial_run_done = True
            next_run = next_schedule_time(now)
            print(f"[{now_ist().strftime('%H:%M:%S')} IST] Next update scheduled for {next_run.strftime('%Y-%m-%d %H:%M IST')}")
        else:
            next_run = next_schedule_time(now)
            if now.minute == 0 and now.second == 0 and now.hour in SCHEDULE_HOURS:
                print(f"[{now.strftime('%H:%M:%S')} IST] Starting bulletin cycle")
                run_cycle_once()
                next_run = next_schedule_time(now)
                print(f"[{now_ist().strftime('%H:%M:%S')} IST] Next update scheduled for {next_run.strftime('%Y-%m-%d %H:%M IST')}")

        delay_seconds = max(0, (next_run - now).total_seconds())
        print(f"[{now_ist().strftime('%H:%M:%S')} IST] Waiting until {next_run.strftime('%Y-%m-%d %H:%M IST')} ({int(delay_seconds // 60)} minutes remaining)")
        while not STOP and delay_seconds > 0:
            sleep_for = min(args.sleep_seconds, delay_seconds)
            time.sleep(sleep_for)
            delay_seconds -= sleep_for

    print("Scheduler shut down cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
