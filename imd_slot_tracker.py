"""IST 3-hour slot tracking for missed-bulletin catch-up.

Uses a fixed UTC+05:30 offset. Do not use ZoneInfo("Asia/Kolkata").
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLOT_STATE_PATH = ROOT / ".imd_nowcast_slots.json"
CYCLE_STATE_PATH = ROOT / ".imd_nowcast_cycle_state.json"
OUTPUT_PATH = ROOT / "IMD_Nowcast_Bulletin.docx"
ARCHIVE_DIR = ROOT / "generated_slots"
SLOT_STATE_VERSION = 2

IST = timezone(timedelta(hours=5, minutes=30))
SLOT_HOURS = (0, 3, 6, 9, 12, 15, 18, 21)
SLOT_FMT = "%Y-%m-%d %H:%M"


def now_ist() -> datetime:
    return datetime.now(IST)


def as_ist(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


def slot_key(slot: datetime) -> str:
    return as_ist(slot).strftime(SLOT_FMT)


def parse_slot_key(key: str) -> datetime:
    return datetime.strptime(key, SLOT_FMT).replace(tzinfo=IST)


def current_due_slot(when: datetime) -> datetime:
    """Most recent scheduled slot at or before `when`. Never a future slot."""
    current = as_ist(when).replace(second=0, microsecond=0)
    hour = max(h for h in SLOT_HOURS if h <= current.hour)
    return current.replace(hour=hour, minute=0)


def next_scheduled_slot(when: datetime) -> datetime:
    """Next scheduled slot strictly after `when`."""
    current = as_ist(when)
    for hour in SLOT_HOURS:
        candidate = current.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > current:
            return candidate
    tomorrow = current + timedelta(days=1)
    return tomorrow.replace(hour=SLOT_HOURS[0], minute=0, second=0, microsecond=0)


def slots_after_through(after: datetime | None, through: datetime) -> list[datetime]:
    """Scheduled slots in (after, through], never after `through`."""
    through = as_ist(through)
    if through.tzinfo is None:
        through = through.replace(tzinfo=IST)
    if after is None:
        return [current_due_slot(through)]
    after = as_ist(after)
    slots: list[datetime] = []
    cursor = next_scheduled_slot(after)
    while cursor <= through:
        slots.append(cursor)
        cursor = next_scheduled_slot(cursor)
    return slots


def _archived_slot_exists(key: str) -> bool:
    """run_imd_scheduled.py archives outputs only after a successful generation."""
    try:
        stamp = parse_slot_key(key).strftime("%Y%m%d_%H%M")
    except ValueError:
        return False
    return (ARCHIVE_DIR / f"IMD_Nowcast_Bulletin_{stamp}.docx").is_file()


def _valid_slot_key(key) -> bool:
    if not isinstance(key, str):
        return False
    try:
        return slot_key(parse_slot_key(key)) == key and parse_slot_key(key).hour in SLOT_HOURS
    except (ValueError, OverflowError):
        return False


def load_slot_state() -> dict:
    """Read the slot file.

    Version 2 files list only explicit successes. Older (unversioned) files may
    contain slots that were wrongly inferred from the DOCX modified time after a
    failed run, so a legacy entry is kept only when there is success evidence:
    its archived bulletin exists, or it matches the last successful cycle state.
    """
    if not SLOT_STATE_PATH.exists():
        return {"completed_slots": []}
    try:
        data = json.loads(SLOT_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"completed_slots": []}
    if not isinstance(data, dict):
        return {"completed_slots": []}
    raw = data.get("completed_slots")
    slots = [key for key in raw if _valid_slot_key(key)] if isinstance(raw, list) else []
    if data.get("version") != SLOT_STATE_VERSION:
        success_key = success_slot_from_cycle_state()
        slots = [key for key in slots if key == success_key or _archived_slot_exists(key)]
    return {"completed_slots": sorted(set(slots))}


def save_slot_state(state: dict) -> dict:
    slots = sorted({key for key in (state.get("completed_slots") or []) if _valid_slot_key(key)})
    payload = {"version": SLOT_STATE_VERSION, "completed_slots": slots}
    tmp = SLOT_STATE_PATH.with_name(SLOT_STATE_PATH.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    last_error = None
    for _attempt in range(3):  # Windows: a reader/AV scanner may hold the file briefly
        try:
            os.replace(tmp, SLOT_STATE_PATH)
            return payload
        except OSError as error:
            last_error = error
            time.sleep(0.2)
    try:
        tmp.unlink()
    except OSError:
        pass
    raise last_error


def mark_slot_completed(slot: datetime) -> bool:
    """Record an explicit success. Call only after generate_bulletin.py exits 0.
    Returns False (never raises) if the slot file could not be written."""
    try:
        state = load_slot_state()
        key = slot_key(slot)
        if key not in state["completed_slots"]:
            state["completed_slots"].append(key)
        save_slot_state(state)
        return True
    except OSError:
        return False


def success_slot_from_cycle_state() -> str | None:
    """Slot whose window contains the last cycle-state record with status 'success'."""
    if not CYCLE_STATE_PATH.exists():
        return None
    try:
        data = json.loads(CYCLE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("status") != "success":
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", data.get("generated_at") if isinstance(data.get("generated_at"), str) else "")
    if not match:
        return None
    try:
        generated = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        return slot_key(current_due_slot(generated))
    except (ValueError, OverflowError):
        return None


def infer_completed_from_existing_output() -> str | None:
    """Explicit success only. The DOCX modified time is never used, because a
    failed run restores the previous bulletin and that must not count."""
    return success_slot_from_cycle_state()


def completed_slot_keys() -> set[str]:
    state = load_slot_state()
    keys = set(state["completed_slots"])
    inferred = infer_completed_from_existing_output()
    if inferred:
        keys.add(inferred)
    return keys


def last_completed_slot(keys: set[str] | None = None) -> datetime | None:
    keys = keys if keys is not None else completed_slot_keys()
    if not keys:
        return None
    return parse_slot_key(max(keys))


def missed_slots(when: datetime | None = None) -> list[datetime]:
    current = as_ist(when or now_ist())
    keys = completed_slot_keys()
    last = last_completed_slot(keys)
    pending = []
    for slot in slots_after_through(last, current):
        if slot_key(slot) not in keys:
            pending.append(slot)
    return pending


def describe_catchup(when: datetime | None = None) -> dict:
    current = as_ist(when or now_ist())
    pending = missed_slots(current)
    return {
        "now": current.strftime("%Y-%m-%d %H:%M:%S"),
        "missed": [slot_key(slot) for slot in pending],
        "next": slot_key(next_scheduled_slot(current)),
        "last_completed": slot_key(last) if (last := last_completed_slot()) else None,
    }


def simulate_missed(now_text: str, completed: list[str]) -> dict:
    """Test helper. `now_text` is IST 'YYYY-MM-DD HH:MM'."""
    when = datetime.strptime(now_text, SLOT_FMT).replace(tzinfo=IST)
    keys = set(completed)
    last = parse_slot_key(max(keys)) if keys else None
    pending = [
        slot_key(slot)
        for slot in slots_after_through(last, when)
        if slot_key(slot) not in keys
    ]
    return {
        "now": now_text,
        "completed": sorted(keys),
        "missed": pending,
        "next": slot_key(next_scheduled_slot(when)),
    }
