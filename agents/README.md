# Multi-Agent System

Three agents with a real, enforced handoff — not three functions renamed to
sound like agents. See `README.md` Section 3c at the project root for the
full design rationale.

## Run the proof-of-concept

```bash
cd agents
python3 orchestrator.py
```

This runs two scenarios:
1. **Normal flow** — a stable reading passes through all three agents, Safety
   Agent approves.
2. **Veto scenario** — a reading is queried 15 minutes into a real 4-hour
   acid wait window from the case study. The Reasoning Agent proposes
   "add chemical" (it has no code path that checks wait windows anymore —
   that logic was deliberately removed from it). The Safety Agent, checking
   independently, vetoes the proposal before it would ever reach a human.

The second scenario is the actual proof this is doing real work: delete
`safety_agent.py`'s call from `orchestrator.py` and this exact case would
incorrectly surface a chemical-addition recommendation to a human 15 minutes
after an acid dose.

## Files

- `messages.py` — the typed message contracts between agents. Read this
  first — it defines what "boundary" means concretely in this system:
  each agent's entire interface is its `run()` function's input/output type.
- `extraction_agent.py` — photo → structured readings. Wraps the same
  Claude vision call the pre-multi-agent webapp used, now scoped to a
  single-responsibility module.
- `reasoning_agent.py` — extraction result → diagnosis + proposal. Wraps
  the RAG retrieval and pattern-detection logic from
  `prototype/reasoning_engine.py`, with the hard safety check
  (`active_wait_window`) deliberately REMOVED from this agent's
  responsibility — it now belongs solely to `safety_agent.py`.
- `safety_agent.py` — proposal → verdict (approved or vetoed). Zero LLM
  calls. Re-fetches pool state independently rather than trusting the
  Reasoning Agent's view of it.
- `orchestrator.py` — coordinates the sequence, enforces that the Safety
  Agent's check can never be skipped, and contains the `demo_veto_scenario()`
  proof-of-concept.

## Why three agents, and why THESE three

Splitting reasoning from safety-checking isn't just for architectural
tidiness — it directly addresses a real failure mode from the source case
study: chemicals were repeatedly added without the person tracking whether
a prior addition's wait window had elapsed. A single monolithic reasoning
function that both diagnoses AND checks safety rules has an implicit
coupling risk: a change made for reasoning-quality reasons (e.g. adjusting
how a diagnosis is worded) sits in the same review surface, the same file,
the same function, as the safety-critical wait-window check. Splitting them
into separate files/modules/agents means a change to one cannot silently
also weaken the other — they have to be touched, reviewed, and tested
independently.

## What was deliberately NOT built this way

**The Safety Agent is not an LLM.** This was a considered rejection, not a
shortcut. See the module docstring in `safety_agent.py` and README.md
Section 3c for the full reasoning: an LLM safety-checking another LLM's
output is still fundamentally one class of system checking itself, with
all the same failure modes (inconsistency across runs, susceptibility to
being argued around) plus added latency and cost. A safety gate that's
supposed to always fire under a defined condition should not have a
probability attached to whether it fires.
