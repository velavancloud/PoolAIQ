"""
Reading Store — JSON file persistence for readings added AFTER the fixed
case-study dataset.

Design decision, stated plainly: the original 7 case-study readings in
prototype/case_study_data.py stay exactly as they are — hardcoded, fixed,
the ground-truth timeline this whole capstone is built on. This module
does NOT touch that file or that data. It only appends NEW readings (from
live photo uploads or demo actions) to a separate JSON log, and the
reasoning/agent layers see the combination of both: fixed history +
persisted additions, chronologically merged.

Why JSON-file and not SQLite/a real DB: this is a single-user capstone demo
running on one machine. A JSON file is trivially inspectable (open it in
any editor, read exactly what's stored), requires no schema migration
tooling, and is honest about being a demo-appropriate choice rather than
a production one. schema/pool_state.sql already documents what a real
production schema would look like — this file is explicitly NOT that,
and doesn't pretend to be.

Concurrency note: no file locking. Fine for a local single-user demo;
would corrupt under concurrent writes in any multi-user deployment. Stated
here rather than discovered the hard way.
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE_PATH = os.path.join(DATA_DIR, "added_readings.json")

_lock = threading.Lock()  # protects against concurrent requests within THIS process
                           # (does not protect against multiple processes — see docstring)


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(STORE_PATH):
        with open(STORE_PATH, "w") as f:
            json.dump([], f)


def add_reading(readings_dict: dict, source: str, read_at: Optional[datetime] = None,
                 diagnosis: str = "", safety_verdict: str = "") -> dict:
    """
    Appends a new reading to the persisted log. Stores the raw readings
    PLUS the diagnosis/verdict that were produced for it at the time, so
    the trend view can show not just numbers but what the system concluded
    about each one historically — useful for a reviewer checking whether
    the system's own past reasoning holds up in hindsight.
    """
    _ensure_store()
    read_at = read_at or datetime.now()

    entry = {
        "read_at": read_at.isoformat(),
        "source": source,
        "readings": readings_dict,
        "diagnosis": diagnosis,
        "safety_verdict": safety_verdict,
        "added_to_store_at": datetime.now().isoformat(),
    }

    with _lock:
        with open(STORE_PATH) as f:
            data = json.load(f)
        data.append(entry)
        with open(STORE_PATH, "w") as f:
            json.dump(data, f, indent=2)

    return entry


def get_all_added_readings() -> list:
    _ensure_store()
    with _lock:
        with open(STORE_PATH) as f:
            return json.load(f)


def clear_store():
    """Resets the persisted log back to empty — used by the UI's 'reset demo
    data' action so a panel demo isn't polluted by readings from a prior
    run/rehearsal."""
    _ensure_store()
    with _lock:
        with open(STORE_PATH, "w") as f:
            json.dump([], f)


if __name__ == "__main__":
    clear_store()
    entry = add_reading(
        {"ph": 7.5, "free_chlorine_ppm": 2.1},
        source="test",
        diagnosis="Test entry",
        safety_verdict="approved",
    )
    print("Added:", entry)
    print()
    print("All added readings:", get_all_added_readings())
