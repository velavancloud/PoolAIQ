# PoolAIQ — Live Demo

A real, running web app for the capstone panel demo. Upload a test strip photo
and watch PoolAIQ extract readings via Claude's vision API, merge them into
this pool's **actual historical timeline**, and reason over the full history —
the core thesis of the project, made tangible.

## Setup (2 minutes)

```bash
cd webapp
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here     # get one at console.anthropic.com
python3 app.py
```

Open **http://localhost:5000**

**No API key?** The three "replay case study" buttons work with zero
configuration — they replay real moments from the timeline through the same
reasoning engine, without needing a live vision call. Use these if you're
demoing somewhere without reliable wifi/API access.

## What's actually real here (not mocked)

- **Vision extraction**: `/api/analyze` makes a live call to Claude using the
  exact system prompt documented in `../prompts/extraction_prompt.md` — not a
  copy, the file is read directly at request time.
- **Reasoning engine**: `/api/analyze` and `/api/analyze_demo` both call
  `../prototype/reasoning_engine.py`'s `recommend()` function directly — the
  same tested code from the prototype, not reimplemented for the demo.
- **RAG retrieval**: every recommendation is grounded in a real TF-IDF +
  cosine-similarity retrieval step over two corpora — a general pool
  chemistry knowledge base (`../prototype/rag/knowledge_base.py`) and this
  pool's own reading history — built and queried fresh on every request via
  `../prototype/rag/embed_store.py`. Retrieved passages are shown in the UI
  with source attribution and match scores, not just returned as an unused
  API field. See `../prototype/rag/README.md` for the retrieval design and
  documented lexical-vs-semantic tradeoffs.
- **Historical grounding**: Every analysis loads `build_case_study_state()`
  from `../prototype/case_study_data.py` — the real anonymized readings from
  the actual 2-month timeline — and reasons over the FULL history, not just
  the new reading.
- **Hard safety gates**: `active_wait_window()` checks run before any pattern
  detection, exactly as documented in `../README.md` Section 4, principle 2.
- **MCP tool calls**: product recommendations and the Approve button's
  notification dispatch both go through a real MCP server subprocess
  (`../mcp_server/server.py`), via the sync bridge in `mcp_client.py` — not
  direct Python imports. See `../README.md` Section 3b for the full
  architecture and `../mcp_server/test_mcp_client.py` for a protocol-level
  test independent of the webapp.
- **Multi-agent orchestration**: Section 03 of the page ("Three agents, one
  non-bypassable check") calls `/api/analyze_agents`, which runs the real
  `../agents/orchestrator.py` pipeline — not a UI-only simulation. The
  "Run veto case" button triggers `orchestrator.demo_veto_scenario()`,
  where the Reasoning Agent (which has no code path to check wait windows
  anymore) proposes a chemical addition, and the Safety Agent —
  independently, with zero LLM calls — blocks it. See `../README.md`
  Section 3c.

## What's simplified for the demo (be upfront about this to the panel)

- Vision extraction accepts any pool test-strip-shaped photo, but the demo's
  case-study history is fixed (not per-user pools) — a production version
  would look up the specific pool_id from the uploaded photo's context.
- `requires_human_approval` is always `true` per the hard-coded design
  principle, but "Approve" in this demo just shows a confirmation message —
  it doesn't actually write to a task queue or send an SMS (that's the
  `api/task_schema.json` + notification engine, which is documented but not
  built for this demo).
- No persistent database — `case_study_data.py` is read fresh on every
  request. A production version uses the `schema/pool_state.sql` model.

## Demo script (suggested flow for the panel)

1. **Open with the thesis, not the tool.** "Retail pool stores test water in
   isolation each visit. This is what happens when a system remembers."

2. **Click "Jun 21 — Low CYA, MCP product lookup."** Point out the product
   card that appears under the recommendation, tagged *"via mcp:
   find_product."* Say explicitly: *"This system never hand-codes 'if low
   CYA, say buy Conditioner.' It calls out to an external tool over the
   actual Model Context Protocol — the same protocol Claude uses for tool
   use generally. Right now that tool is backed by a small stub catalog,
   but the protocol boundary means swapping in a real Leslie's or Amazon
   API later only touches one file, not every place a product gets
   recommended."* Click **Approve & create task** — narrate that this
   fires a second, real MCP call (`send_task_notification`) and show the
   confirmation message with the returned notification id and timestamp.

3. **Click "Jun 29 — pH overcorrected."** Point out: engine gives standard
   symptom-level advice here — same as any retail store would, because there
   isn't enough history yet to see a pattern. This is intentionally the
   "boring" baseline case.

4. **Click "Jul 03 — pH recurs."** This is the moment. Point out the
   root-cause flag: *"pH is unstable AND Total Alkalinity has been reading
   high."* Explain: **this exact reading, at a real Leslie's visit, produced
   a treatment plan that only addressed pH — not alkalinity.** The system
   catches what the single-visit advisor structurally couldn't.

   **Scroll to the "Retrieved context (RAG)" panel below the recommendation.**
   This is the actual retrieval step, not decoration — point out the two
   source types (blue "knowledge base" tags vs. amber "this pool" tags) and
   the match percentages. Say explicitly: *"This diagnosis didn't just come
   from a rule firing — it's grounded in a retrieved passage from a general
   chemistry knowledge base AND retrieved prior readings from this specific
   pool. You can inspect exactly what informed this recommendation."*

5. **Click "Jul 11 — stabilized."** Show the system doesn't just keep firing
   the same pattern forever — it recognizes resolution and moves to a
   different, current issue (chlorine too high to swim yet).

6. **If time/API access allows: live upload.** Take out your phone, photograph
   a test strip (even a random one, or reuse a photo from
   `../docs/timeline-photos/`), upload it live. Narrate the extraction JSON
   as it streams back, then the recommendation.

7. **If asked "is that MCP call actually real or just an API route":** open
   a terminal and run `python3 ../mcp_server/test_mcp_client.py` live. This
   bypasses the webapp entirely — a standalone MCP client spawning the
   server as its own subprocess and calling all three tools over stdio,
   with the SDK's own protocol-level logging (`ListToolsRequest`,
   `CallToolRequest`) visible in the output. This is the strongest single
   piece of evidence that the MCP integration isn't decorative.

8. **Scroll to Section 03 — "Three agents, one non-bypassable check."**
   Click **"Run normal case"** first — walk through the three agent nodes
   lighting up left to right, ending in a calm sage-green "approved" verdict.

   Then click **"Run veto case."** This is the strongest moment in the
   whole demo — build it up: *"This is a real case from the timeline —
   15 minutes after a real acid addition, well inside its 4-hour wait
   window. The Reasoning Agent doesn't check wait windows anymore — I
   removed that logic from it on purpose, so this proposal is unaware
   it's unsafe."* Point at the Reasoning Agent node turning coral, then
   the Safety Agent node. *"The Safety Agent re-checks the pool's state
   completely independently — it doesn't trust anything the Reasoning
   Agent assumed — and blocks it. What the human would have seen is not
   the chemical recommendation; it's this safe alternative instead."*

   **If pushed on whether this is 'real' multi-agent or just a diagram:**
   say plainly that the transport is in-process (documented, not hidden —
   see README.md Section 3c), but the AUTHORITY boundary is real: run
   `python3 ../agents/orchestrator.py` in a terminal to show the same
   veto happening completely outside the webapp, then offer to open
   `agents/reasoning_agent.py` and show there is no wait-window check
   anywhere in that file — the Safety Agent is not decorative, it is the
   only thing in the system that catches this case.

## Known rough edges (own these, don't hide them)

- Flask dev server only — fine for a demo, `debug=True` should never ship
- No auth, no rate limiting, no persistent storage
- If the uploaded photo isn't a recognizable test strip, Claude's extraction
  may return mostly `null` fields — the UI will show `—` for those pads
  rather than crash, but it's not a graceful "please retake this photo" UX yet
