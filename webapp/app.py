"""
PoolAIQ Demo Server

A real, runnable Flask app that demonstrates the full thesis end-to-end:
  1. User uploads a test strip photo
  2. Server calls Claude (vision) to extract structured readings — using
     the actual prompts/extraction_prompt.md system prompt
  3. Extracted reading is merged into the case study's historical PoolState
  4. prototype/reasoning_engine.py runs against the FULL history (not just
     the new reading) to produce a diagnosis + recommendation
  5. UI renders the diagnosis, explicitly showing which prior readings/events
     were used — the actual differentiator vs. single-visit retail advice

Run:
    export ANTHROPIC_API_KEY=your_key_here
    python3 app.py
Then open http://localhost:5000
"""

import os
import sys
import json
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template

# Import the real reasoning engine + case study data (not duplicated logic)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prototype"))
from reasoning_engine import PoolState, Reading, recommend, IDEAL_RANGES  # noqa: E402
from case_study_data import build_case_study_state  # noqa: E402

# MCP client bridge — all product lookups and notification dispatch go
# through the real MCP server subprocess, not direct imports of
# mcp_server/catalog_data.py or notification_store.py. See mcp_client.py
# for why this boundary matters.
from mcp_client import find_product_via_mcp, send_notification_via_mcp  # noqa: E402

# Multi-agent orchestrator — a SEPARATE code path from recommend() above,
# deliberately kept side by side rather than silently replacing it. This
# lets the demo show both: the direct reasoning-engine call (simpler,
# faster, what /api/analyze_demo already used) and the full three-agent
# pipeline with a real, independently-checked Safety Agent veto boundary
# (/api/analyze_agents). See agents/README.md and README.md Section 3c.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
import orchestrator  # noqa: E402
from messages import ExtractionRequest, ReasoningRequest  # noqa: E402
import extraction_agent as extraction_agent_module  # noqa: E402
import reasoning_agent as reasoning_agent_module  # noqa: E402
import safety_agent as safety_agent_module  # noqa: E402

# Persistence layer — new readings from live uploads get appended here and
# merged with the fixed case-study dataset on every subsequent request.
# See reading_store.py and merged_state.py for the read/write design.
from reading_store import add_reading, get_all_added_readings, clear_store  # noqa: E402
from merged_state import build_merged_state  # noqa: E402

app = Flask(__name__)

EXTRACTION_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "extraction_prompt.md"
)


def load_extraction_system_prompt() -> str:
    """Pull the actual system prompt out of prompts/extraction_prompt.md so the
    demo uses the SAME prompt documented in the capstone, not a copy that can drift."""
    with open(EXTRACTION_PROMPT_PATH) as f:
        content = f.read()
    # extract the fenced code block
    start = content.find("```") + 3
    end = content.find("```", start)
    return content[start:end].strip()


def extract_reading_from_photo(image_bytes: bytes, media_type: str) -> dict:
    """Calls Claude with the project's real extraction prompt against an uploaded photo."""
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    system_prompt = load_extraction_system_prompt()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract the readings from this pool test strip photo, "
                                "following the JSON output format exactly. Respond with "
                                "ONLY the JSON object, no other text.",
                    },
                ],
            }
        ],
    )

    text = response.content[0].text.strip()
    # strip markdown fences if the model wrapped it
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def enrich_with_product_lookup(recommendation: dict) -> dict:
    """
    Calls the real MCP server (via mcp_client.py) to look up a product for
    the recommendation's proposed action, and attaches it as
    proposed_action.product_lookup. This is the concrete proof that the
    reasoning engine's output flows through the MCP tool boundary rather
    than the webapp hand-coding "if category == acid, say Muriatic Acid"
    inline.

    Failure is non-fatal: if the MCP subprocess call fails for any reason
    (e.g. not installed in some environment), the recommendation still
    returns — product_lookup is just omitted, with the error visible for
    debugging. A missing product suggestion should never block a safety
    recommendation from reaching the user.
    """
    action = recommendation.get("proposed_action", {})
    category = action.get("product_category", "")
    if not category or category == "unknown":
        return recommendation

    try:
        lookup = find_product_via_mcp(product_category=category)
        recommendation["proposed_action"]["product_lookup"] = lookup
        recommendation["proposed_action"]["product_lookup_source"] = "mcp:find_product"
    except Exception as e:
        recommendation["proposed_action"]["product_lookup_error"] = str(e)

    return recommendation


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/history")
def get_history():
    """Return the case study's full reading history for the timeline view."""
    state = build_case_study_state()
    readings = []
    for r in state.readings:
        readings.append({
            "read_at": r.read_at.isoformat(),
            "source": r.source,
            "free_chlorine_ppm": r.free_chlorine_ppm,
            "total_chlorine_ppm": r.total_chlorine_ppm,
            "ph": r.ph,
            "total_alkalinity_ppm": r.total_alkalinity_ppm,
            "calcium_hardness_ppm": r.calcium_hardness_ppm,
            "cyanuric_acid_ppm": r.cyanuric_acid_ppm,
            "copper_ppm": r.copper_ppm,
            "phosphates_ppb": r.phosphates_ppb,
            "salt_ppm": r.salt_ppm,
        })
    return jsonify({"readings": readings, "ideal_ranges": IDEAL_RANGES})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Core demo endpoint: accepts an uploaded photo and runs the FULL
    multi-agent pipeline (Extraction Agent -> Reasoning Agent -> Safety
    Agent, via agents/orchestrator.py) against the MERGED state — the
    fixed case-study history plus every reading persisted from a previous
    upload in this session. This is the actual read+write loop:

      1. Extraction Agent turns the photo into structured readings
      2. Reasoning Agent + Safety Agent reason over merged_state.py's
         build_merged_state() — original 7 readings + anything added since
      3. If the Safety Agent approves, the new reading is PERSISTED via
         reading_store.add_reading() — it becomes part of history for the
         NEXT upload, and appears in the trend view (/api/trend)
      4. If the Safety Agent vetoes, the reading is still persisted (it's
         real data, worth keeping in the trend regardless of what the
         system recommended doing about it) but the response makes the
         veto clearly visible rather than silently downgrading it

    This replaces the previous version of this endpoint, which called
    reasoning_engine.recommend() directly against a copy of the fixed
    history that was discarded after the request — no persistence, no
    Safety Agent, no trend. See README.md Section 3d for why the older
    /api/analyze_demo and /api/analyze_agents endpoints are kept
    unchanged alongside this one rather than consolidated.
    """
    if "photo" not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400

    file = request.files["photo"]
    image_bytes = file.read()
    media_type = file.content_type or "image/jpeg"

    now = datetime.now()

    try:
        extraction_result = extraction_agent_module.run(
            ExtractionRequest(image_bytes=image_bytes, media_type=media_type)
        )
    except Exception as e:
        return jsonify({"error": f"Vision extraction failed: {str(e)}"}), 500

    reasoning_proposal = reasoning_agent_module.run(
        ReasoningRequest(pool_id="demo_pool", extraction=extraction_result, as_of=now),
        state_builder=build_merged_state,
    )
    safety_verdict = safety_agent_module.run(
        reasoning_proposal, pool_id="demo_pool", as_of=now,
        state_builder=build_merged_state,
    )

    # Persist regardless of verdict — a vetoed reading is still real data
    # that belongs in the trend; what changes is whether a chemical
    # recommendation accompanies it.
    stored_entry = add_reading(
        extraction_result.readings,
        source=extraction_result.source_type,
        read_at=now,
        diagnosis=reasoning_proposal.diagnosis,
        safety_verdict=safety_verdict.verdict,
    )

    result = {
        "extraction": {
            "source_type": extraction_result.source_type,
            "extraction_confidence": extraction_result.extraction_confidence,
            "readings": extraction_result.readings,
            "notes": extraction_result.notes,
        },
        "new_reading": {"read_at": now.isoformat(), **extraction_result.readings},
        "reasoning": {
            "diagnosis": reasoning_proposal.diagnosis,
            "root_cause_vs_symptom": reasoning_proposal.root_cause_vs_symptom,
            "proposed_action_type": reasoning_proposal.proposed_action_type,
            "instructions": reasoning_proposal.instructions,
            "confidence": reasoning_proposal.confidence,
            "retrieved_context_used": reasoning_proposal.retrieved_context_used,
        },
        "safety": {
            "verdict": safety_verdict.verdict,
            "reason": safety_verdict.reason,
            "safe_alternative_instructions": safety_verdict.safe_alternative_instructions,
            "checked_rules": safety_verdict.checked_rules,
        },
        "persisted": True,
        "stored_entry_added_at": stored_entry["added_to_store_at"],
    }

    # Build a recommendation-shaped view for the existing UI rendering path
    # (renderResult() in app.js expects recommendation.proposed_action) —
    # only populated when the Safety Agent actually approved, since a
    # vetoed proposal should never present as an actionable recommendation.
    if safety_verdict.verdict == "approved":
        action = {
            "type": reasoning_proposal.proposed_action_type,
            "product_category": reasoning_proposal.proposed_product_category,
            "instructions": reasoning_proposal.instructions,
        }
        if reasoning_proposal.proposed_product_category and \
           reasoning_proposal.proposed_product_category != "unknown":
            try:
                action["product_lookup"] = find_product_via_mcp(
                    product_category=reasoning_proposal.proposed_product_category
                )
            except Exception as e:
                action["product_lookup_error"] = str(e)
        result["recommendation"] = {
            "diagnosis": reasoning_proposal.diagnosis,
            "root_cause_vs_symptom": reasoning_proposal.root_cause_vs_symptom,
            "proposed_action": action,
            "confidence": reasoning_proposal.confidence,
            "retrieved_context_used": reasoning_proposal.retrieved_context_used,
        }
    else:
        result["recommendation"] = {
            "diagnosis": f"⛔ SAFETY AGENT VETO: {safety_verdict.reason}",
            "root_cause_vs_symptom": None,
            "proposed_action": {
                "type": "wait_and_retest",
                "instructions": safety_verdict.safe_alternative_instructions,
            },
            "confidence": 1.0,
            "retrieved_context_used": [],
        }

    result["history_length_used"] = len(build_merged_state().readings)

    return jsonify(result)


@app.route("/api/trend")
def get_trend():
    """
    Returns the FULL merged history (fixed case-study readings + everything
    persisted from live uploads) for the trend chart/table. This is what
    makes new uploads visibly change the trend view rather than
    disappearing into a response that's shown once and forgotten.
    """
    state = build_merged_state()
    added = get_all_added_readings()
    added_timestamps = {entry["read_at"] for entry in added}

    readings = []
    for r in state.readings:
        readings.append({
            "read_at": r.read_at.isoformat(),
            "source": r.source,
            "is_new": r.read_at.isoformat() in added_timestamps,
            "free_chlorine_ppm": r.free_chlorine_ppm,
            "total_chlorine_ppm": r.total_chlorine_ppm,
            "ph": r.ph,
            "total_alkalinity_ppm": r.total_alkalinity_ppm,
            "calcium_hardness_ppm": r.calcium_hardness_ppm,
            "cyanuric_acid_ppm": r.cyanuric_acid_ppm,
            "copper_ppm": r.copper_ppm,
            "phosphates_ppb": r.phosphates_ppb,
            "salt_ppm": r.salt_ppm,
        })

    # attach diagnosis/verdict metadata for the newly-added ones, so the
    # table can show what the system concluded about each upload
    added_meta = {e["read_at"]: e for e in added}
    for r in readings:
        if r["is_new"] and r["read_at"] in added_meta:
            r["diagnosis"] = added_meta[r["read_at"]].get("diagnosis", "")
            r["safety_verdict"] = added_meta[r["read_at"]].get("safety_verdict", "")

    return jsonify({"readings": readings, "ideal_ranges": IDEAL_RANGES,
                     "fixed_count": len(state.readings) - len(added),
                     "added_count": len(added)})


@app.route("/api/trend/reset", methods=["POST"])
def reset_trend():
    """Clears everything persisted from live uploads, back to just the
    original 7-reading case-study dataset. Used by the UI's 'Reset demo
    data' button so repeated rehearsals don't pollute the trend view."""
    clear_store()
    return jsonify({"reset": True})


@app.route("/api/analyze_demo", methods=["POST"])
def analyze_demo():
    """
    Fallback endpoint that skips the live Claude vision call (for demoing
    without an API key / network) and instead replays a specific point in
    the real timeline, so the reasoning engine + UI can still be shown live.
    """
    body = request.get_json(force=True) or {}
    scenario = body.get("scenario", "root_cause_detected")

    state = build_case_study_state()

    if scenario == "product_recommendation":
        as_of = state.readings[0].read_at
        state.readings = state.readings[:1]
    elif scenario == "early_no_pattern":
        as_of = state.readings[2].read_at
        state.readings = state.readings[:3]
    elif scenario == "root_cause_detected":
        as_of = state.readings[5].read_at
        state.readings = state.readings[:6]
    else:  # stabilized
        as_of = state.readings[-1].read_at + timedelta(hours=1)

    recommendation = recommend(state, as_of)
    recommendation = enrich_with_product_lookup(recommendation)
    latest = state.readings[-1]

    return jsonify({
        "extraction": {"source_type": "demo_replay", "extraction_confidence": 1.0},
        "new_reading": {
            "read_at": latest.read_at.isoformat(),
            "free_chlorine_ppm": latest.free_chlorine_ppm,
            "total_chlorine_ppm": latest.total_chlorine_ppm,
            "ph": latest.ph,
            "total_alkalinity_ppm": latest.total_alkalinity_ppm,
            "cyanuric_acid_ppm": latest.cyanuric_acid_ppm,
            "copper_ppm": latest.copper_ppm,
            "phosphates_ppb": latest.phosphates_ppb,
            "salt_ppm": latest.salt_ppm,
        },
        "recommendation": recommendation,
        "history_length_used": len(state.readings),
    })


def _trace_to_dict(trace) -> dict:
    """Serializes an OrchestrationTrace (agents/messages.py dataclasses)
    into JSON-safe dicts for the UI. Kept as an explicit function rather
    than a generic dataclass->dict dump so the field ordering matches what
    the UI expects, and so datetime objects get isoformat()'d."""
    from dataclasses import asdict

    extraction_dict = asdict(trace.extraction) if trace.extraction else None
    reasoning_dict = asdict(trace.reasoning)
    safety_dict = asdict(trace.safety)

    # forwarded_proposal / vetoed_proposal are themselves ReasoningProposal
    # dataclasses nested inside SafetyVerdict — asdict() already recurses
    # into them correctly, so no extra handling needed there.

    return {
        "extraction": extraction_dict,
        "reasoning": reasoning_dict,
        "safety": safety_dict,
        "completed_at": trace.completed_at.isoformat(),
    }


@app.route("/api/analyze_agents", methods=["POST"])
def analyze_agents():
    """
    Runs the FULL three-agent pipeline (Extraction -> Reasoning -> Safety)
    via agents/orchestrator.py, as opposed to /api/analyze_demo's direct
    call to reasoning_engine.recommend(). Two demo scenarios:

      - scenario='normal': a stable reading, Safety Agent approves
      - scenario='veto': agents/orchestrator.py's demo_veto_scenario() —
        a reading queried 15 minutes into a real 4-hour acid wait window.
        The Reasoning Agent (which no longer checks wait windows at all —
        that logic was removed from it in the multi-agent refactor)
        proposes a chemical addition anyway. The Safety Agent, checking
        independently, vetoes it before it would reach a human. This is
        the single clearest piece of evidence that the three agents have
        genuine, separately-enforced authority rather than being one
        function split into three files for the sake of a diagram.
    """
    from datetime import timedelta as _td

    body = request.get_json(force=True) or {}
    scenario = body.get("scenario", "normal")

    if scenario == "veto":
        trace = orchestrator.demo_veto_scenario()
    else:
        state_module = sys.modules.get("case_study_data") or __import__("case_study_data")
        state = build_case_study_state()
        readings = {
            "free_chlorine_ppm": 6.29, "total_chlorine_ppm": 6.29, "ph": 7.7,
            "total_alkalinity_ppm": 115, "cyanuric_acid_ppm": 48,
        }
        as_of = state.readings[-1].read_at + _td(hours=1)
        trace = orchestrator.orchestrate_from_known_reading(readings, "demo_pool", as_of)

    result = _trace_to_dict(trace)

    # Only enrich with a product lookup if the Safety Agent actually
    # approved — a vetoed proposal should never get a "here's where to buy
    # it" card, since the human is never being asked to act on it.
    if trace.safety.verdict == "approved" and trace.safety.forwarded_proposal:
        category = trace.safety.forwarded_proposal.proposed_product_category
        if category and category != "unknown":
            try:
                result["safety"]["forwarded_proposal"]["product_lookup"] = \
                    find_product_via_mcp(product_category=category)
            except Exception as e:
                result["safety"]["forwarded_proposal"]["product_lookup_error"] = str(e)

    return jsonify(result)


@app.route("/api/approve", methods=["POST"])
def approve_task():
    """
    Called when the user clicks "Approve & create task" in the UI. Dispatches
    a REAL notification through the MCP server's send_task_notification
    tool — this is the human-in-the-loop gate from README.md Section 4
    actually connected to an external-resource call, not just a UI state
    change with no backend effect.

    Note this endpoint is only reachable AFTER the human approval click —
    the reasoning engine and enrich_with_product_lookup never call
    send_notification_via_mcp themselves. That ordering is the actual
    enforcement of "human_in_the_loop: always true" from
    prompts/reasoning_prompt.md — approval gates the notification at the
    route level, not just in the UI.
    """
    body = request.get_json(force=True) or {}
    instructions = body.get("instructions", "No instructions provided.")

    try:
        result = send_notification_via_mcp(
            channel="sms",
            to="+1-704-555-0100",  # demo phone number, hardcoded for this capstone
            body=f"PoolAIQ (approved): {instructions}",
            task_id=body.get("task_id", ""),
        )
        return jsonify({"approved": True, "notification": result})
    except Exception as e:
        return jsonify({"approved": True, "notification_error": str(e)}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
