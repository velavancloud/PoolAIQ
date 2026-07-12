# PoolAIQ — AI-Guided Pool Chemistry Recovery System

**Capstone Project | Author: Velavan Nedunchezhiyan**

> Born from a real 2-month battle to clear a cloudy 18,000-gallon salt pool. Generic pool-store advice treated every visit as a fresh start — no memory of what was already tried, no view of the whole system, and each fix often undid the last one. PoolAIQ exists to remember, reason, and guide.

---

## 1. The Problem

Pool chemistry is a **coupled system**, not a checklist:
- Raising pH also raises alkalinity (and vice versa)
- CYA (stabilizer) shields chlorine but also dilutes its punch
- Shock dosing depends on *combined* chlorine, not just what's low
- Fixes are sequenced (metals → shock → clarifier → CYA → phosphates) and **timing violations cause visible regressions**

Retail pool stores (Leslie's, etc.) test water in isolation each visit. They don't know:
- What you added 3 days ago
- Whether two products were combined unsafely
- Whether your last "fix" is still working through the system
- Your specific equipment (filter type, salt cell, waterfall aeration)

**Result:** owners bounce between contradictory advice, chase symptoms instead of root causes, and can spend months (and hundreds of dollars) without resolution — exactly what happened in the source case study for this project (see `docs/case-study-timeline.md`).

## 2. The Insight

Every water test strip photo + every retail printout is a **timestamped state snapshot**. Stitched together, they form a time series that reveals:
- Which interventions actually moved the needle
- Which recommendations conflicted with prior treatment (e.g., "add soda ash" prescribed while alkalinity was already climbing)
- Root-cause patterns invisible in any single visit (e.g., alkalinity buffering pH back up every time, independent of how much acid was added)

**PoolAIQ's core value: persistent memory + systemic reasoning, not another generic chemical calculator.**

## 3. System Architecture

```
┌─────────────────┐
│   User Input     │  Photo (test strip / retail printout) OR manual entry
│  (SMS / App /    │  "Pool still cloudy, added X yesterday"
│   Web upload)    │
└────────┬─────────┘
         │
         v
┌─────────────────────────┐
│  Vision Extraction Layer │  OCR + VLM parses:
│  (multimodal LLM call)   │   - strip colors → ppm values
│                          │   - retail printout tables → structured JSON
└────────┬─────────────────┘
         │
         v
┌─────────────────────────┐
│   Pool State Store        │  Time-series DB (see schema/pool_state.sql)
│   (structured history)    │   - every reading, every chemical added,
│                            │     every equipment event, timestamped
└────────┬───────────────────┘
         │
         v
┌─────────────────────────────┐
│   RAG Retrieval Layer         │  Retrieves:
│   (vector store over:         │   - this pool's own history (primary signal)
│    - prior readings            │   - general pool chemistry knowledge base
│    - chemical interaction KB   │   - manufacturer dosing tables
│    - this pool's equipment)    │   - safety rules (never mix X+Y same day)
└────────┬───────────────────────┘
         │
         v
┌─────────────────────────────┐
│  Reasoning + Recommendation   │  LLM call grounded in retrieved context:
│  Engine                       │   - diagnoses root cause (not just symptom)
│                                │   - checks for conflicts with recent additions
│                                │   - proposes ONE prioritized next action
│                                │   - flags "wait and retest" as a valid action
└────────┬───────────────────────┘
         │
         v
┌─────────────────────────────┐
│   Human-in-the-Loop Gate      │  User (or licensed pro) approves/edits
│   (required before any        │   before task is created — chemical safety
│    chemical is "prescribed")  │   is never fully autonomous
└────────┬───────────────────────┘
         │
         v
┌─────────────────────────────┐
│   Task + Notification Engine  │  - Creates task w/ exact dose, timing,
│                                │     wait-time before next step
│                                │   - SMS/push reminder at scheduled time
│                                │   - "Mark complete" → logs to state store
│                                │     → triggers next step in sequence
└────────┬───────────────────────┘
         │
         v
┌─────────────────────────────┐
│   Commerce Hook (optional)    │  If chemical not in user's on-hand inventory:
│   (API to Leslie's/Amazon/    │   - suggest exact product + quantity
│    Instacart pool suppliers)  │   - deep-link to cart (no auto-purchase)
└─────────────────────────────┘
         │
         v
┌─────────────────────────────┐
│  Weekly Maintenance Mode      │  Once stabilized (defined thresholds held
│  (post-recovery)              │   for N consecutive tests):
│                                │   - switches from "recovery" to "maintain"
│                                │   - simple weekly reminder cadence
│                                │   - lighter-touch, fewer interventions
└─────────────────────────────┘
```

## 4. Core Design Principles

1. **Memory over memory-less advice.** Every recommendation must cite what's already in the water and what's already been tried.
2. **Human-in-the-loop is non-negotiable for chemical dosing.** The system proposes; a human (owner or, ideally, a licensed pool pro reviewing remotely) approves. This is a liability and safety requirement, not just a UX choice.
3. **One variable at a time.** The system should actively resist "kitchen sink" dosing — this was the single biggest failure mode in the source case study.
4. **Root cause > symptom.** E.g., don't just prescribe acid for high pH — check if alkalinity is the actual driver and flag the pattern.
5. **Sequencing and timing are first-class data.** "Wait 4 hours" isn't a footnote — it's a scheduled task with its own reminder.
6. **Graceful degradation.** If confidence is low (blurry photo, conflicting signals), the system should say so and request a retest rather than guessing.

## 5. MVP Scope (what to build first)

| Phase | Feature | Why first |
|---|---|---|
| 1 | Photo → structured reading extraction | Everything downstream depends on this |
| 2 | Pool state timeline (single pool, manual entry fallback) | Proves the memory thesis |
| 3 | Rule-based recommendation engine (no LLM yet) | Encodes known-good logic (Leslie's treatment plan structure) as a deterministic baseline |
| 4 | RAG layer + LLM reasoning on top of rules | Adds nuance: pattern detection, conflict flags |
| 5 | Human approval + task creation | Required before any "go live" |
| 6 | SMS/push notifications | Closes the loop |
| 7 | Commerce hook | Nice-to-have, not core thesis |
| 8 | Maintenance mode | Long-term retention feature |

## 6. Files in this project

- `docs/case-study-timeline.md` — the real 2-month timeline this project is based on, anonymized
- `docs/failure-modes.md` — catalog of the specific mistakes made (retail whiplash, timing violations, etc.) mapped to system features that prevent them
- `docs/timeline-photos/` — **16 real, dated photos/videos** from the actual case study (May 24 – Jul 13), indexed in `timeline-photos/README.md`. This is the ground-truth visual dataset for testing the Vision Extraction Layer.
- `schema/pool_state.sql` — proposed data model
- `prompts/extraction_prompt.md` — the vision extraction system prompt
- `prompts/reasoning_prompt.md` — the recommendation engine system prompt
- `api/task_schema.json` — task/notification object shape
- `prototype/` — working, tested Python reasoning engine, replayed against the real timeline data (see `prototype/README.md`)

## 7. Evaluation / Success Metrics

- **Time-to-clear**: days from "cloudy" flag to 3 consecutive clear/stable readings (baseline: ~60 days manual)
- **Chemical additions per week**: should trend down as system enforces "one variable at a time" (baseline: up to 5-6/week during crisis phase)
- **Conflict catches**: number of times system flags "this contradicts a treatment still in progress" before user acts
- **Retention into maintenance mode**: % of users who stay engaged post-recovery for ongoing upkeep

## 8. Known Limitations / Honest Risks

- Vision extraction from consumer test strips is inherently noisy (lighting, strip degradation, color perception) — system must express uncertainty, not false precision
- Liability: recommending chemical dosing carries real safety risk (chlorine gas from improper mixing, chemical burns). MVP must never fully automate dosing without human confirmation, and should include hard-coded safety guardrails independent of the LLM (e.g., never recommend acid + chlorine same-day regardless of what reasoning layer outputs)
- Equipment diagnosis (salt cell failure, filter type mismatch) is out of scope for v1 — flagged as a known gap, not solved
