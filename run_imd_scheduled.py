"""Launch generate_bulletin.py for Task Scheduler without a killable console."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
PYTHONW = ROOT / "venv" / "Scripts" / "pythonw.exe"
GENERATOR = ROOT / "generate_bulletin.py"
LOG_FILE = ROOT / "imd_scheduler.log"
LOCK_PATH = ROOT / ".imd_generate.lock"
ARCHIVE_DIR = ROOT / "generated_slots"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

from imd_slot_tracker import (
    current_due_slot,
    describe_catchup,
    mark_slot_completed,
    missed_slots,
    next_scheduled_slot,
    now_ist,
    simulate_missed,
    slot_key,
)


def log(handle, message: str) -> None:
    handle.write(message)
    if not message.endswith("\n"):
        handle.write("\n")
    handle.flush()


def acquire_lock():
    handle = open(LOCK_PATH, "a+b")
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return handle
    except OSError:
        handle.close()
        return None


def release_lock(handle) -> None:
    if handle is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    handle.close()


def archive_outputs(slot) -> None:
    ARCHIVE_DIR.mkdir(exist_ok=True)
    stamp = slot.strftime("%Y%m%d_%H%M")
    for source_name, dest_name in (
        ("IMD_Nowcast_Bulletin.docx", f"IMD_Nowcast_Bulletin_{stamp}.docx"),
        ("final_bulletin.png", f"final_bulletin_{stamp}.png"),
    ):
        source = ROOT / source_name
        if source.is_file():
            shutil.copy2(source, ARCHIVE_DIR / dest_name)


def run_generator(handle) -> int:
    if not PYTHON.is_file():
        log(handle, f"ERROR: Python not found: {PYTHON}")
        return 1
    if not GENERATOR.is_file():
        log(handle, f"ERROR: generate_bulletin.py not found: {GENERATOR}")
        return 1
    interpreter = PYTHONW if PYTHONW.is_file() else PYTHON
    completed = subprocess.run(
        [str(interpreter), "-u", str(GENERATOR)],
        cwd=str(ROOT),
        stdout=handle,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
    )
    return completed.returncode


def generate_for_slot(handle, slot, reason: str) -> int:
    lock = acquire_lock()
    if lock is None:
        log(handle, f"WARNING: generation already running; skipped {slot_key(slot)}")
        return 0
    try:
        log(handle, f"{reason}: {slot.strftime('%H:%M')}")
        code = run_generator(handle)
        if code == 0:
            mark_slot_completed(slot)
            archive_outputs(slot)
            log(handle, f"Completed slot: {slot_key(slot)}")
        else:
            log(handle, f"Generation failed for slot {slot_key(slot)} with exit {code}")
        return code
    finally:
        release_lock(lock)


def run_scheduled(handle) -> int:
    current = now_ist()
    slot = current_due_slot(current)
    nxt = next_scheduled_slot(current)
    log(handle, f"Scheduled run at {current.strftime('%Y-%m-%d %H:%M:%S')} IST")
    log(handle, f"Current due slot: {slot.strftime('%H:%M')}")
    log(handle, f"Next scheduled slot: {nxt.strftime('%H:%M')}")
    return generate_for_slot(handle, slot, "On-slot generation")


def run_catchup(handle) -> int:
    current = now_ist()
    pending = missed_slots(current)
    nxt = next_scheduled_slot(current)
    if not pending:
        log(handle, "No missed slot")
        log(handle, f"Next scheduled slot: {nxt.strftime('%H:%M')}")
        return 0
    worst = 0
    for slot in pending:
        log(handle, f"Missed slot detected: {slot.strftime('%H:%M')}")
        code = generate_for_slot(handle, slot, "Generating missed bulletin")
        if code != 0:
            worst = code
            break
    log(handle, f"Next scheduled slot: {nxt.strftime('%H:%M')}")
    return worst


def run_simulations(handle) -> int:
    cases = [
        ("09:00 missed, startup 10:00", "2026-09-27 10:00", ["2026-09-27 06:00"]),
        ("09:00 missed, startup 11:59", "2026-09-27 11:59", ["2026-09-27 06:00"]),
        ("09:00 missed, startup 12:01", "2026-09-27 12:01", ["2026-09-27 06:00"]),
        ("09:00 and 12:00 missed, startup 13:00", "2026-09-27 13:00", ["2026-09-27 06:00"]),
        ("No missed slot", "2026-09-27 10:00", ["2026-09-27 09:00"]),
    ]
    log(handle, "===== CATCH-UP SIMULATION =====")
    for title, now_text, completed in cases:
        result = simulate_missed(now_text, completed)
        log(handle, f"{title}")
        log(handle, f"  now={result['now']}")
        log(handle, f"  missed={result['missed'] or ['(none)']}")
        log(handle, f"  next={result['next']}")
    live = describe_catchup()
    log(handle, "===== LIVE CATCH-UP STATUS =====")
    log(handle, f"now={live['now']}")
    log(handle, f"missed={live['missed'] or ['(none)']}")
    log(handle, f"next={live['next']}")
    return 0


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="IMD scheduled bulletin runner")
    parser.add_argument("--catch-up", action="store_true", help="Generate only missed IST slots up to now.")
    parser.add_argument("--simulate", action="store_true", help="Print catch-up decisions; do not generate.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with LOG_FILE.open("a", encoding="utf-8", errors="replace") as handle:
        log(handle, f"===== {datetime.now():%Y-%m-%d %H:%M:%S} start =====")
        if args.simulate:
            code = run_simulations(handle)
        elif args.catch_up:
            code = run_catchup(handle)
        else:
            code = run_scheduled(handle)
        log(handle, f"===== {datetime.now():%Y-%m-%d %H:%M:%S} exit {code} =====")
        return code


if __name__ == "__main__":
    sys.exit(main())
