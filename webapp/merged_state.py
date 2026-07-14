"""
Combines the fixed case-study dataset (prototype/case_study_data.py — never
modified) with any readings persisted via reading_store.py (from live
uploads or demo actions) into a single chronological PoolState.

This is the actual "read + write" loop: build_case_study_state() gives the
read-only ground truth; get_all_added_readings() gives what's accumulated
since; this module merges them so every agent/reasoning call sees the full,
current picture — new readings actually affect trend detection and root-
cause pattern matching against the ORIGINAL timeline, not a separate
disconnected log.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prototype"))
from reasoning_engine import PoolState, Reading  # noqa: E402
from case_study_data import build_case_study_state  # noqa: E402

from reading_store import get_all_added_readings  # noqa: E402


def build_merged_state() -> PoolState:
    """
    Returns a PoolState with the fixed case-study readings PLUS every
    persisted addition, sorted chronologically. Called fresh on every
    request — the persisted store is the source of truth for "what's new,"
    not an in-memory cache that could drift from the JSON file.
    """
    state = build_case_study_state()

    added = get_all_added_readings()
    for entry in added:
        r = entry["readings"]
        reading = Reading(
            read_at=datetime.fromisoformat(entry["read_at"]),
            source=entry.get("source", "home_strip"),
            free_chlorine_ppm=r.get("free_chlorine_ppm"),
            total_chlorine_ppm=r.get("total_chlorine_ppm"),
            ph=r.get("ph"),
            total_alkalinity_ppm=r.get("total_alkalinity_ppm"),
            calcium_hardness_ppm=r.get("calcium_hardness_ppm"),
            cyanuric_acid_ppm=r.get("cyanuric_acid_ppm"),
            copper_ppm=r.get("copper_ppm"),
            phosphates_ppb=r.get("phosphates_ppb"),
            salt_ppm=r.get("salt_ppm"),
        )
        state.readings.append(reading)

    # Keep the merged timeline chronological — persisted additions could in
    # principle be backfilled with an earlier read_at (e.g. correcting a
    # demo timestamp), so sort rather than assume append-order is time-order.
    state.readings.sort(key=lambda r: r.read_at)

    return state


if __name__ == "__main__":
    state = build_merged_state()
    print(f"Merged state: {len(state.readings)} total readings")
    for r in state.readings:
        print(f"  {r.read_at} ({r.source}) — pH={r.ph} FCl={r.free_chlorine_ppm}")
