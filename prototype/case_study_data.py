"""
Replays the real timeline from docs/case-study-timeline.md as structured
PoolState objects, for testing reasoning_engine.py against actual events.
"""

from datetime import datetime
from reasoning_engine import PoolProfile, PoolState, Reading, Addition


def build_case_study_state() -> PoolState:
    profile = PoolProfile(gallons=18000, sanitizer_type="salt", has_waterfall_or_aeration=True)
    state = PoolState(profile=profile)

    # --- Readings, chronological (subset of real timeline, illustrating the pH/alkalinity pattern) ---
    state.readings = [
        Reading(datetime(2026, 6, 21, 13, 7), "retail_test",
                free_chlorine_ppm=1.0, total_chlorine_ppm=7.86, ph=7.4,
                total_alkalinity_ppm=120, calcium_hardness_ppm=229,
                cyanuric_acid_ppm=24, copper_ppm=0.5, phosphates_ppb=422, salt_ppm=2800),

        Reading(datetime(2026, 6, 25, 17, 42), "retail_test",
                free_chlorine_ppm=0.12, total_chlorine_ppm=0.12, ph=7.5,
                total_alkalinity_ppm=108, calcium_hardness_ppm=261,
                cyanuric_acid_ppm=12, copper_ppm=0.3, phosphates_ppb=232, salt_ppm=2901),

        Reading(datetime(2026, 6, 29, 18, 4), "retail_test",
                free_chlorine_ppm=0.27, total_chlorine_ppm=1.93, ph=6.7,  # overcorrected low
                total_alkalinity_ppm=118, calcium_hardness_ppm=235,
                cyanuric_acid_ppm=50, copper_ppm=0.2, phosphates_ppb=227, salt_ppm=2901),

        Reading(datetime(2026, 6, 30, 20, 30), "home_strip",
                free_chlorine_ppm=None, total_chlorine_ppm=None, ph=8.0,  # soda ash overcorrected high
                total_alkalinity_ppm=None),

        Reading(datetime(2026, 6, 30, 22, 45), "home_strip",
                free_chlorine_ppm=None, total_chlorine_ppm=None, ph=7.3,  # small acid dose corrected
                total_alkalinity_ppm=None),

        Reading(datetime(2026, 7, 3, 18, 2), "retail_test",
                free_chlorine_ppm=1.35, total_chlorine_ppm=1.91, ph=8.0,  # pH recurred to high AGAIN
                total_alkalinity_ppm=131, calcium_hardness_ppm=265,
                cyanuric_acid_ppm=50, copper_ppm=0.2, phosphates_ppb=181, salt_ppm=3080),

        Reading(datetime(2026, 7, 11, 12, 18), "retail_test",
                free_chlorine_ppm=6.29, total_chlorine_ppm=6.29, ph=7.7,  # finally stable
                total_alkalinity_ppm=115, calcium_hardness_ppm=303,
                cyanuric_acid_ppm=48, copper_ppm=0.0, phosphates_ppb=114, salt_ppm=3223),
    ]

    # --- A representative set of additions from the timeline ---
    state.additions = [
        Addition(datetime(2026, 6, 30, 18, 45), "acid", 24, "oz", requires_wait_hours=4),
        Addition(datetime(2026, 6, 30, 20, 45), "base", 48, "oz", requires_wait_hours=4),  # soda ash
    ]

    return state


if __name__ == "__main__":
    from reasoning_engine import recommend
    from datetime import timedelta
    import json

    state = build_case_study_state()

    print("=" * 70)
    print("REPLAY: recommendation at the 6/29 reading (pH=6.7, just overcorrected)")
    print("=" * 70)
    as_of = state.readings[2].read_at  # the 6/29 reading
    state_snapshot = PoolState(profile=state.profile,
                                readings=state.readings[:3],
                                additions=[a for a in state.additions if a.added_at <= as_of])
    print(json.dumps(recommend(state_snapshot, as_of), indent=2, default=str))

    print()
    print("=" * 70)
    print("REPLAY: recommendation at the 7/3 reading (pH=8.0 AGAIN — this is where")
    print("        the root-cause detector should fire, unlike single-visit retail advice)")
    print("=" * 70)
    as_of = state.readings[5].read_at
    state_snapshot = PoolState(profile=state.profile,
                                readings=state.readings[:6],
                                additions=[a for a in state.additions if a.added_at <= as_of])
    print(json.dumps(recommend(state_snapshot, as_of), indent=2, default=str))

    print()
    print("=" * 70)
    print("REPLAY: final 7/11 reading (stabilized)")
    print("=" * 70)
    as_of = state.readings[-1].read_at + timedelta(hours=1)
    print(json.dumps(recommend(state, as_of), indent=2, default=str))
