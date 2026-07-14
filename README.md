# PoolAIQ — AI-Guided Pool Chemistry Recovery System

**Capstone Project | Author: Velavan Nedunchezhiyan**

> Born from a real 2-month battle to clear a cloudy 18,000-gallon salt pool. Generic pool-store advice treated every visit as a fresh start — no memory of what was already tried, no view of the whole system, and each fix often undid the last one. PoolAIQ exists to remember, reason, and guide.

---

## 0. Live Demo

A working web UI is included — upload a test-strip photo (or replay a real
moment from the case study) and watch PoolAIQ reason over this pool's full
history live. See `webapp/README.md` for setup (2 minutes) and a suggested
demo script for a panel presentation.

### Build status (honest, as of this commit)

The architecture diagram in Section 3 describes the target system. Not all of
it is built. Here is what's real vs. designed-but-not-built:

| Component | Status | Detail |
|---|---|---|
| Vision extraction | **Built** | Live Claude API call in `webapp/app.py`, using `prompts/extraction_prompt.md` verbatim |
| Pool state store | **Built (hybrid: fixed + JSON persistence)** | `prototype/case_study_data.py` remains a fixed, hardcoded 7-reading dataset (never modified). `webapp/reading_store.py` + `webapp/merged_state.py` add real persistence ON TOP of it — new readings from live uploads survive across requests and feed back into subsequent reasoning. Not the full `schema/pool_state.sql` database design, but no longer "no persistence between requests" either. See Section 3d. |
| Reasoning / recommendation engine | **Built** | `prototype/reasoning_engine.py` — deterministic rules + trend detection, tested against real case-study data |
| RAG retrieval layer | **Built** | Real TF-IDF + cosine-similarity retrieval over two corpora (general chemistry KB + this pool's history), built fresh per-request in `prototype/rag/`, surfaced in the UI with source attribution. See Section 3a for the honest tradeoffs (in-memory index, lexical not semantic matching, small seed KB). |
| Human-in-the-loop approval | **Built (UI only)** | Approve/Reject buttons work and gate the demo flow, but don't write to a real task queue |
| Task/notification engine | **Not built** | `api/task_schema.json` documents the intended shape; no SMS/push code exists |
| Commerce hook | **Not built** | Documented in Section 3 only |
| MCP (tool-use protocol) | **Built** | Real MCP server (`mcp_server/`) with two tools — `find_product` and `send_task_notification` — running over the actual stdio protocol (verified via a real MCP client subprocess handshake, not just decorated functions). See Section 3b. |
| Multi-agent orchestration | **Built** | Three agents (`agents/`) with a strictly typed message-passing contract, coordinated by an orchestrator. The Safety Agent has genuine, independently-enforced veto authority over the Reasoning Agent's output — demonstrated live via a constructed case where the Reasoning Agent proposes a chemical addition with no awareness of an active wait window, and the Safety Agent blocks it before it reaches a human. See Section 3c. |

**Why this table exists:** an earlier draft of this README described the
target architecture in a way that could be misread as describing what was
already running. It wasn't. This project is honest about that gap because
the whole thesis is about a system that doesn't overclaim to a pool owner —
it should hold itself to the same standard.

```bash
cd webapp && pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python3 app.py
# open http://localhost:5000
```

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

## 3a. What "Real RAG" Requires Here (and what changed)

The original diagram labeled the retrieval step "RAG Retrieval Layer" but the
prototype just read a Python list — that's not retrieval, that's just...
having the list. Real RAG needs three things that weren't there:

1. **A corpus that's actually too big to pass in full context.** This pool's
   history (7 readings) fits trivially in a prompt — no retrieval is needed
   to reason over 7 rows. RAG only earns its keep once you're reasoning over
   *many pools* or a large general chemistry knowledge base (manufacturer
   dosing tables, safety interaction rules, forum-scraped troubleshooting
   patterns) where you can't just paste everything in.
2. **An embedding + similarity search step**, so a new reading retrieves the
   *most relevant* prior readings/KB chunks — not just "all of them."
3. **A retrieval step that's inspectable** — for the safety-critical parts of
   this system, being able to show *which specific prior reading or KB
   passage* justified a recommendation is not optional. This is implemented
   in `prototype/rag/` (see below) as `retrieved_context` returned alongside
   every recommendation.

### What's now built (`prototype/rag/`)

- `knowledge_base.py` — a small seed corpus of general pool chemistry facts
  (chunked, one fact per entry) distinct from this pool's own history
- `embed_store.py` — embeds the KB + this pool's readings using a local
  sentence-transformer model (no external API dependency for the retrieval
  step itself — keeps the demo runnable offline), stores vectors in a
  simple in-memory index (documented as a stand-in for a real vector DB —
  see limitations below)
- `retriever.py` — given a new reading, retrieves the top-k most relevant
  prior readings AND the top-k most relevant KB chunks, returns both with
  similarity scores
- `reasoning_engine.py` now accepts `retrieved_context` and threads it into
  the diagnosis output as `retrieved_context_used` (matching the
  `prompts/reasoning_prompt.md` output schema, which already specified this
  field but nothing was populating it)

### Known limitations of this RAG implementation (stated up front)

- In-memory vector index, not a real vector DB (Pinecone/Weaviate/pgvector) —
  fine for one pool's demo corpus, would not scale past a handful of pools
- KB seed corpus is small (~15 entries) and hand-written, not scraped/curated
  at scale — sufficient to demonstrate the retrieval mechanism, not a
  production knowledge base
- No re-ranking step — pure cosine similarity, which is known to
  under-perform on domain-specific technical text vs. a fine-tuned or
  hybrid (BM25 + embedding) retriever
- **TF-IDF ranking is imperfect on adjacent chemistry topics.** Verified
  during testing: for the pH+alkalinity query, the correct KB entry
  (`kb_alk_ph_coupling`) sometimes ranks #2 instead of #1, because
  `kb_calcium_hardness_scale` shares enough incidental term overlap
  ("scale", "ppm", chemistry vocabulary) to score competitively. This is
  the exact lexical-vs-semantic gap a neural embedding model would close.
  **Current mitigation:** the rule-based detectors in `reasoning_engine.py`
  (e.g. `check_alkalinity_ph_coupling`) fire independently of retrieval
  ranking — when a rule fires, the code does a *targeted* lookup for its
  specific supporting KB entry by ID, rather than trusting top-k rank
  alone. This means retrieval quality currently matters more for the
  general "what's relevant" citations than for the safety-critical
  pattern-detection logic itself, which stays deterministic. Worth stating
  plainly: this is a reasonable interim design, not a fully-solved
  retrieval problem.
- **Verified second example of the same gap:** a query for "free chlorine is
  high" does not retrieve `kb_breakpoint_chlorination` in top-3, even though
  it's conceptually the most relevant entry, because that KB text is written
  around "combined chlorine" terminology rather than "free chlorine" — the
  two concepts are chemically related but lexically distant. This is the
  clearest concrete case for why a semantic embedding model (once network
  constraints allow deploying one) would materially improve retrieval
  quality here, beyond what better keyword engineering could fix.

## 3b. MCP — One Protocol Boundary for External Resources

### Why this matters architecturally, not just as a checkbox

Before this was built, `webapp/app.py` would have needed to directly import
a product catalog module and a notification-sending module — and every
future consumer of PoolAIQ's reasoning output (a CLI tool, a second web
app, an SMS-in webhook that lets a user text a photo directly) would need
its own copy of that same import logic. Swapping the stub product catalog
for a real Leslie's API, or the stub notification log for real Twilio,
would mean hunting down every call site across every consumer.

MCP collapses this to one boundary: any MCP client — this webapp, a future
CLI, Claude itself in an agentic workflow — talks to `mcp_server/server.py`
the same way, over the same protocol, regardless of what's actually running
behind the tools.

### What's built (`mcp_server/`)

- `server.py` — a real MCP server using the official Anthropic `mcp` SDK's
  `FastMCP` interface, exposing three tools:
  - `find_product(product_category, issue)` — looks up which product
    addresses a chemistry issue or product category
  - `send_task_notification(channel, to, body, task_id)` — dispatches an
    SMS/push notification
  - `get_notification_log()` — returns everything sent so far (debug/demo)
- `catalog_data.py` — a 9-product stub catalog standing in for a real
  retailer API (Leslie's, Amazon)
- `notification_store.py` — an in-memory stub standing in for a real
  SMS/push provider (Twilio, OneSignal)
- `test_mcp_client.py` — a **real MCP client** that spawns `server.py` as a
  subprocess and calls all three tools over the actual stdio protocol
  (`ListToolsRequest`/`CallToolRequest`, logged by the SDK itself) —
  this is the file that proves the server genuinely speaks MCP rather than
  being Python functions with `@mcp.tool()` decorators that are never
  actually invoked through the protocol layer
- `webapp/mcp_client.py` — a sync bridge Flask's request handlers use to
  call the MCP server (Flask's dev server is synchronous; the MCP SDK's
  client is async — this module spins up a short-lived event loop per call)

### How it's wired into the demo

`webapp/app.py`'s `enrich_with_product_lookup()` calls `find_product` via
MCP whenever the reasoning engine's output includes a `product_category` —
visible in the UI as a product card tagged "via mcp: find_product" with
real SKU/price/size data, not a hardcoded string.

The `/api/approve` endpoint calls `send_task_notification` via MCP only
after the human clicks Approve in the UI — this is the actual enforcement
of `requires_human_approval: true` (from `prompts/reasoning_prompt.md`'s
output schema) at the route level, not just a UI state that has no backend
effect.

### Honest tradeoffs, stated plainly

- **Stub backends.** `catalog_data.py` and `notification_store.py` are
  hand-written stand-ins, not real API integrations. What's real is the
  protocol boundary — swapping in a real Leslie's product API or a real
  Twilio call means editing those two files only, not any calling code.
- **Subprocess-per-call, not a persistent session.** `mcp_client.py` spawns
  a fresh `server.py` subprocess for every single tool call (confirmed via
  the `ListToolsRequest` log line appearing on every request in testing).
  A production deployment would keep one long-lived MCP client
  session (or a small connection pool) instead of paying subprocess-spawn
  cost per request — this demo optimizes for "obviously correct and easy
  to verify" over "fast," which is the right tradeoff for a capstone
  artifact but not for production load.
- **Auth was initially absent, now added for the HTTP transport.** The
  original version of this section said "no auth on the MCP server" — true
  at the time, for stdio. That's since been closed:
  `POOLAIQ_MCP_TRANSPORT=streamable-http` mode requires
  `POOLAIQ_MCP_SERVER_API_KEY` and refuses to start without it, enforced
  by a bearer-token middleware wrapping FastMCP's HTTP app (not the SDK's
  full OAuth `AuthSettings` — deliberately scoped down, since that path
  requires standing up a real OAuth authorization server with an
  `issuer_url`, more machinery than this project needs; a real bearer-key
  check was the correctly-scoped choice, stated as such rather than
  silently under-building). Stdio transport still has no auth —
  appropriate, since stdio's security boundary is "can this process spawn
  a subprocess on this machine," not a network concern.
- **Deployment.** See `mcp_server/deploy/README.md` — the server can now
  run as a real network-addressable HTTP service, with a working EC2
  Terraform template (`mcp_server/deploy/ec2/`) as the reference
  deployment. Azure and GCP are explicitly not built yet; that README
  states what carries over unchanged (the Dockerfile, `config.py`'s
  environment-variable surface) versus what needs building fresh per
  cloud.
- **Server-side inference.** A new `reason_about_reading` tool lets the
  MCP server itself make a Claude call using its own configured
  `ANTHROPIC_API_KEY` — distinct from the webapp's separate key used for
  vision extraction. Deliberately narrow-scoped (plain-language
  explanation only, no dosing authority) rather than a general-purpose
  inference proxy, consistent with the "narrow tool boundaries" principle
  this section already argues for.

## 3c. Multi-Agent — Genuine Separation of Authority, Not Renamed Functions

### The question that had to be answered honestly first

Before building this, the real question wasn't "how do we add multi-agent" —
it was "does splitting this into multiple agents actually improve anything,
or would it just be architecture theater on top of code that already works
as one function?" The honest answer: a naive 3-way split (Extraction Agent,
Reasoning Agent, "Safety Agent" that's just a third LLM call reviewing the
second one's output) would have been theater, and arguably worse than the
monolith — an LLM checking another LLM's safety output is still one class
of system checking itself, just with extra latency and a diagram that looks
more impressive.

### What was actually built instead

Three agents with a real authority boundary:

- **Extraction Agent** (`agents/extraction_agent.py`) — photo → structured
  readings. Same Claude vision call as before, now scoped to a
  single-responsibility module with a typed input/output.
- **Reasoning Agent** (`agents/reasoning_agent.py`) — extraction result →
  diagnosis + proposal. Runs the same RAG retrieval and pattern-detection
  logic as `prototype/reasoning_engine.py`, but with one deliberate change:
  **the hard safety wait-window check was removed from this agent
  entirely.** It has no code path that checks wait windows anymore.
- **Safety Agent** (`agents/safety_agent.py`) — proposal → verdict. **Zero
  LLM calls.** Every check is a deterministic Python function. Re-fetches
  pool state independently rather than trusting the Reasoning Agent's view
  of it. Can VETO a proposal outright, substituting a safe alternative that
  is what actually reaches the human — the original proposal never does.

### The proof, not just the claim

`agents/orchestrator.py`'s `demo_veto_scenario()` constructs a real case
from the timeline: a reading queried 15 minutes into an actual 4-hour acid
wait window from the case study (the real June 30 acid addition at 6:45pm).
The Reasoning Agent — which has no mechanism to check wait windows anymore —
proposes adding shock. The Safety Agent, checking independently, catches
this and vetoes it:

```
Reasoning Agent proposed: Correct free_chlorine_ppm toward ideal range...
Safety Agent verdict: vetoed
Safety Agent reason: Active wait window: a acid addition (24oz) at 06:45 PM
  requires 3.8 more hour(s) before any new chemical addition.
```

This is verifiable by deleting the `safety_agent.run()` call from
`orchestrator.py` — that exact case would then incorrectly surface a
chemical-addition recommendation to a human 15 minutes after an acid dose.
The separation is doing real work, not just providing a more elaborate
diagram of the same function.

Run it yourself: `python3 agents/orchestrator.py` — prints both the normal
(approved) and veto cases side by side. Also wired into the webapp UI as
Section 03, with two buttons ("Run normal case" / "Run veto case") that
call the same orchestrator through `/api/analyze_agents`.

### Honest tradeoffs, stated plainly

- **In-process, not distributed.** All three agents currently run as
  Python function calls within one process — not separate OS processes or
  network services. The MESSAGE CONTRACT (`agents/messages.py`'s typed
  dataclasses) is strictly enforced — no agent reaches into another's
  internals, each only sees what the previous agent chose to put in its
  output message — but the TRANSPORT is not distributed. A production
  version could put each agent behind its own MCP server (see Section 3b)
  using the same message dataclasses serialized to JSON across that
  boundary, without changing the contract itself.
- **Some duplication with `prototype/reasoning_engine.py`.** The
  Reasoning Agent's pattern-detection logic (root-cause coupling, recurring
  correction failure detection) currently re-implements calls into the same
  underlying functions from `reasoning_engine.py` rather than that file
  being fully decomposed into agent modules. This was a deliberate scope
  decision for capstone timeline reasons — the two systems (direct
  `recommend()` call vs. full agent pipeline) are kept side by side in the
  webapp (`/api/analyze_demo` vs `/api/analyze_agents`) rather than one
  replacing the other, so both remain inspectable.
- **`_rule_max_single_dose` is a documented no-op.** The rule slot exists
  in `safety_agent.py` but has nothing to check yet, because proposals
  don't currently compute exact doses (the Reasoning Agent's instructions
  say "use conservative dose," not a number). Stated as a known gap rather
  than removed or hidden.

## 3d. Persistence — New Uploads Actually Become History

### The gap this closes

Every previous version of `/api/analyze` did the same thing: extract a
reading, append it to a COPY of the fixed case-study history, reason over
that copy once, and discard it. The next upload started from the same
fixed 7 readings again — nothing a user uploaded ever accumulated, and the
"full history" the README kept promising was, for any reading you actually
uploaded yourself, a lie by omission: your reading was never really part of
history for the NEXT analysis.

### What's built now

- `webapp/reading_store.py` — appends new readings to a JSON file
  (`webapp/data/added_readings.json`), separate from and never modifying
  `prototype/case_study_data.py`'s fixed dataset
- `webapp/merged_state.py` — builds a single chronological `PoolState`
  combining the fixed 7 readings with everything persisted since, sorted
  by timestamp (not append-order, in case of out-of-order demo timestamps)
- `agents/reasoning_agent.py` and `agents/safety_agent.py` both now accept
  an optional `state_builder` parameter (default: the fixed case-study
  dataset, so every prior test/demo is unaffected) — the webapp passes
  `build_merged_state` instead, so both the Reasoning Agent's pattern
  detection AND the Safety Agent's independent wait-window check see live
  persisted readings, not just the frozen 7
- `/api/analyze` now runs the FULL three-agent pipeline (previously it
  called `reasoning_engine.recommend()` directly, skipping the Safety
  Agent entirely) against the merged state, and persists the result
  regardless of the Safety Agent's verdict — a vetoed reading is still
  real data worth keeping in the trend
- `/api/trend` serves the merged history for the new Section 04 trend
  chart/table in the UI; `/api/trend/reset` clears persisted additions
  back to the original 7 for repeated demo rehearsals

### Verified

A synthetic reading with elevated pH and alkalinity, persisted through this
pipeline, was confirmed to trigger the SAME `check_alkalinity_ph_coupling`
root-cause detector described in Section 3c — proving new uploads
genuinely participate in the pattern-detection logic against the real
historical timeline, not just get appended to a display list. Full
read-write-read round trip confirmed: reading persisted → `/api/trend`
reflects it → a second simulated upload's reasoning call sees the first
one in its history.

### Honest limitations

- **Untested against the literal Anthropic vision API call in this
  environment** (no API key available in the sandbox this was built in).
  Every other link in the chain — extraction via the same code path demo
  scenarios use, reasoning, safety check, persistence, trend serving, UI
  rendering — was independently verified. The vision API call itself is
  unchanged, previously-working code from earlier commits.
- **JSON file, no locking beyond a single in-process thread lock.** Stated
  in `reading_store.py`'s docstring: fine for one local demo user, would
  corrupt under real concurrent multi-user writes. `schema/pool_state.sql`
  already documents what a real production schema looks like — this is
  explicitly a demo-appropriate substitute, not a claim of production
  readiness.
- **A vetoed reading still gets persisted.** This was a deliberate choice
  (the reading itself is real data, independent of what the system
  recommended doing about it) but means the trend table can show a
  "⛔ vetoed" row that a viewer might misread as "this reading was
  rejected/discarded" rather than "a proposed ACTION in response to this
  reading was blocked." Worth clarifying if it comes up live.

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
- `prototype/` — working, tested Python reasoning engine + RAG layer, replayed against the real timeline data (see `prototype/README.md`)
- `mcp_server/` — real MCP server (5 tools including server-side inference) supporting BOTH stdio (local) and HTTP (deployed) transport, with bearer-token auth for HTTP, a real Docker image, and a working EC2 Terraform deployment template (see Section 3b and `mcp_server/deploy/README.md`)
- `agents/` — three-agent system (Extraction/Reasoning/Safety) with a real, independently-enforced veto boundary — includes a runnable proof (`orchestrator.py`) that the Safety Agent catches what the Reasoning Agent cannot see (see Section 3c)
- `webapp/reading_store.py`, `webapp/merged_state.py` — persistence layer so live-uploaded readings actually accumulate into history and affect subsequent reasoning, not just get displayed once and discarded (see Section 3d)

## 7. Evaluation / Success Metrics

- **Time-to-clear**: days from "cloudy" flag to 3 consecutive clear/stable readings (baseline: ~60 days manual)
- **Chemical additions per week**: should trend down as system enforces "one variable at a time" (baseline: up to 5-6/week during crisis phase)
- **Conflict catches**: number of times system flags "this contradicts a treatment still in progress" before user acts
- **Retention into maintenance mode**: % of users who stay engaged post-recovery for ongoing upkeep

## 8. Known Limitations / Honest Risks

- Vision extraction from consumer test strips is inherently noisy (lighting, strip degradation, color perception) — system must express uncertainty, not false precision
- Liability: recommending chemical dosing carries real safety risk (chlorine gas from improper mixing, chemical burns). MVP must never fully automate dosing without human confirmation, and should include hard-coded safety guardrails independent of the LLM (e.g., never recommend acid + chlorine same-day regardless of what reasoning layer outputs)
- Equipment diagnosis (salt cell failure, filter type mismatch) is out of scope for v1 — flagged as a known gap, not solved
