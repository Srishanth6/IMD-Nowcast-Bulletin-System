"""IST 3-hour slot tracking for missed-bulletin catch-up.

Uses a fixed UTC+05:30 offset. Do not use ZoneInfo("Asia/Kolkata").
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLOT_STATE_PATH = ROOT / ".imd_nowcast_slots.json"
CYCLE_STATE_PATH = ROOT / ".imd_nowcast_cycle_state.json"
OUTPUT_PATH = ROOT / "IMD_Nowcast_Bulletin.docx"

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


def load_slot_state() -> dict:
    if not SLOT_STATE_PATH.exists():
        return {"completed_slots": []}
    try:
        data = json.loads(SLOT_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"completed_slots": []}
    slots = data.get("completed_slots") or []
    return {"completed_slots": sorted(set(slots))}


def save_slot_state(state: dict) -> dict:
    slots = sorted(set(state.get("completed_slots") or []))
    payload = {"completed_slots": slots}
    SLOT_STATE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def mark_slot_completed(slot: datetime) -> None:
    state = load_slot_state()
    key = slot_key(slot)
    if key not in state["completed_slots"]:
        state["completed_slots"].append(key)
    save_slot_state(state)


def infer_completed_from_existing_output() -> str | None:
    """If a successful bulletin already exists, treat its due slot as completed."""
    timestamps: list[datetime] = []
    if CYCLE_STATE_PATH.exists():
        try:
            data = json.loads(CYCLE_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if data.get("status") in {"success", "locked"}:
            generated = str(data.get("generated_at") or "")
            match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", generated)
            if match:
                timestamps.append(
                    datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
                )
    if OUTPUT_PATH.exists():
        timestamps.append(datetime.fromtimestamp(OUTPUT_PATH.stat().st_mtime, tz=IST))
    if not timestamps:
        return None
    return slot_key(current_due_slot(max(timestamps)))


def completed_slot_keys() -> set[str]:
    state = load_slot_state()
    keys = set(state["completed_slots"])
    inferred = infer_completed_from_existing_output()
    if inferred:
        keys.add(inferred)
        if inferred not in state["completed_slots"]:
            state["completed_slots"].append(inferred)
            save_slot_state(state)
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
