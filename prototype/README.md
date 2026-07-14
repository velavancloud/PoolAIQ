# Prototype: Reasoning Engine

A runnable, dependency-free Python demonstration of the core thesis: **a system
with access to a pool's full history catches root-cause patterns that
single-visit advice structurally cannot.**

## Run it

```
python3 case_study_data.py
```

This replays three real moments from the actual case study timeline (see
`../docs/case-study-timeline.md`) through the reasoning engine:

1. **6/29 — pH just overcorrected to 6.7.** Only one prior alkalinity reading
   exists at this point, so the engine correctly falls back to standard
   symptom-level advice (same as retail would give).

2. **7/3 — pH recurred to 8.0, the SECOND time this happened.** This is the
   moment the engine's `check_alkalinity_ph_coupling()` function fires,
   correctly identifying that elevated Total Alkalinity is buffering pH back
   up — the actual root cause that took ~2 weeks to find manually in the real
   timeline. **A retail visit at this exact moment, with this exact reading,
   produced a treatment plan that only addressed pH directly (soda ash) — not
   alkalinity.** This prototype demonstrates the alternative outcome.

3. **7/11 — final stabilized reading.** Chlorine is high (6.29, from an active
   super-chlorinate cycle) but pH/alkalinity have held. The engine correctly
   does NOT re-fire the resolved alkalinity pattern (this was a bug caught and
   fixed during development — see git-equivalent note in `reasoning_engine.py`
   comments) and instead flags the new, current issue (chlorine too high to
   swim yet).

## What this demonstrates for the capstone write-up

- **Hard safety rules are checked independently of pattern detection** —
  `active_wait_window()` runs first, before any generative or pattern-based
  reasoning, and can't be overridden by it.
- **Trend detection over single-point evaluation** — `detect_recurring_correction_failure()`
  and `check_alkalinity_ph_coupling()` both require *history*, not just the
  latest reading, to fire.
- **Deterministic core, LLM-augmentable shell** — this rule-based engine is
  Phase 3 from the README roadmap. Phase 4 wraps this same logic with an LLM
  call (using `prompts/reasoning_prompt.md`) for nuance and natural-language
  explanation, but the hard safety gates and pattern thresholds here would
  remain non-LLM and non-overridable, per the safety design principle in the
  main README.

## Changelog

- **Bug found and fixed during MCP integration testing:** `active_wait_window()`
  didn't check that an addition's timestamp was actually before the query
  timestamp — a query for a point in time (e.g. 2026-06-21) that came
  BEFORE a later addition in the data (2026-06-30) would incorrectly treat
  that future addition as an active wait window, blocking any
  recommendation. Fixed by requiring `0 <= elapsed < requires_wait_hours`
  instead of just `elapsed < requires_wait_hours`. Caught because building
  the MCP demo scenario for `product_recommendation` (June 21) exercised a
  code path the original three scenarios (June 29 / July 3 / July 11, all
  later in the timeline than every addition in the dataset) never hit —
  worth noting as a case for testing multiple points across a timeline,
  not just monotonically-later ones.

## Known simplifications (documented, not hidden)

- `IDEAL_RANGES` doesn't yet account for pool-specific factors (surface type
  age, salt vs. tablet sanitizer) — a real system would adjust ranges per
  `PoolProfile`.
- The swing-detection threshold (`swings >= 2`) is a placeholder heuristic,
  not tuned against a labeled dataset — flagged in README.md Section 8 as a
  known risk area (false positive/negative rates on this specific logic
  should be a capstone evaluation metric).
- `case_study_data.py` uses a subset of the real timeline's additions (not
  every single chemical add is modeled) — sufficient to demonstrate the
  pattern-detection thesis, not a complete replay.
