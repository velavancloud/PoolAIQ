"""
Orchestrator

Coordinates the three agents in strict sequence: Extraction -> Reasoning ->
Safety. This is the only file in the system that knows all three agents
exist — each agent only knows the message types it receives and returns
(see messages.py), never the identity or internals of the agent upstream
or downstream of it.

WHY THIS IS A REAL BOUNDARY, NOT JUST RENAMED FUNCTION CALLS:

1. Each agent is called through its module-level run() function only —
   never through a shared object, shared class, or shared mutable state.
2. Each agent's output is a frozen dataclass (messages.py) — the
   orchestrator cannot reach into an agent's internals, only read what
   that agent chose to put in its output message.
3. The Safety Agent CANNOT be bypassed: orchestrate() always calls it
   after the Reasoning Agent, unconditionally, and its verdict is what
   determines what (if anything) reaches the human-approval step. There
   is no code path where a ReasoningProposal reaches the UI without
   passing through safety_agent.run() first.
4. The Safety Agent independently re-fetches pool state rather than
   trusting anything passed to it about state — demonstrated concretely
   in demo_veto_scenario() below, where the Safety Agent vetoes a
   proposal the Reasoning Agent had no way to know was unsafe (the
   Reasoning Agent doesn't even LOOK at wait-windows anymore — that
   check was deliberately removed from it in this refactor).

HONEST LIMITATION: all three agents currently run as in-process Python
function calls within one Python process, not as separate OS processes or
network services communicating over a message bus / MCP. The MESSAGE
CONTRACT is real and strictly enforced (see above), but the TRANSPORT is
not distributed. See README.md Section 3c for why this is the right
tradeoff for a capstone demo and what would change for a production
multi-process deployment (likely: each agent behind its own MCP server,
using the same messages.py dataclasses serialized to JSON across that
boundary — the contract wouldn't need to change, only the transport).
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from messages import (  # noqa: E402
    ExtractionRequest, ExtractionResult, ReasoningRequest, OrchestrationTrace,
)
import extraction_agent  # noqa: E402
import reasoning_agent  # noqa: E402
import safety_agent  # noqa: E402


def orchestrate_from_photo(image_bytes: bytes, media_type: str, pool_id: str,
                            as_of: datetime = None, state_builder=None) -> OrchestrationTrace:
    """Full live pipeline: photo -> Extraction Agent -> Reasoning Agent ->
    Safety Agent -> trace. Used by the /api/analyze route.

    state_builder: forwarded to both reasoning_agent.run() and
    safety_agent.run() unchanged — see reasoning_agent.py's docstring for
    what this enables (the webapp injecting build_merged_state so live
    persisted readings are included)."""
    as_of = as_of or datetime.now()

    extraction_result = extraction_agent.run(
        ExtractionRequest(image_bytes=image_bytes, media_type=media_type)
    )

    reasoning_proposal = reasoning_agent.run(
        ReasoningRequest(pool_id=pool_id, extraction=extraction_result, as_of=as_of),
        state_builder=state_builder,
    )

    safety_verdict = safety_agent.run(reasoning_proposal, pool_id=pool_id, as_of=as_of,
                                       state_builder=state_builder)

    return OrchestrationTrace(
        extraction=extraction_result,
        reasoning=reasoning_proposal,
        safety=safety_verdict,
    )


def orchestrate_from_known_reading(readings_dict: dict, pool_id: str,
                                    as_of: datetime, source_type: str = "demo_replay",
                                    state_builder=None) -> OrchestrationTrace:
    """
    Same pipeline, but skips the Extraction Agent's live vision call —
    used by the demo-replay scenarios. Still produces a proper
    ExtractionResult (via extraction_agent.run_from_known_reading) so the
    Reasoning Agent receives an identically-shaped message either way; it
    cannot tell whether extraction was live or replayed.
    """
    extraction_result = extraction_agent.run_from_known_reading(readings_dict, source_type)

    reasoning_proposal = reasoning_agent.run(
        ReasoningRequest(pool_id=pool_id, extraction=extraction_result, as_of=as_of),
        state_builder=state_builder,
    )

    safety_verdict = safety_agent.run(reasoning_proposal, pool_id=pool_id, as_of=as_of,
                                       state_builder=state_builder)

    return OrchestrationTrace(
        extraction=extraction_result,
        reasoning=reasoning_proposal,
        safety=safety_verdict,
    )


def demo_veto_scenario() -> OrchestrationTrace:
    """
    Constructs a case specifically designed to demonstrate the Safety
    Agent's veto authority live: a reading that the Reasoning Agent would
    happily propose a chemical addition for, queried at a timestamp that
    falls inside an active wait window the Reasoning Agent never checks
    for (that logic was deliberately removed from reasoning_agent.py in
    this refactor — it now lives ONLY in safety_agent.py).

    This proves the separation is doing real work: if the Safety Agent
    were deleted or bypassed, this exact case would incorrectly reach a
    human for approval 15 minutes into a 4-hour acid wait window.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prototype"))
    from case_study_data import build_case_study_state

    state = build_case_study_state()
    # Use the real June 30 acid addition (18:45) as our wait-window trigger,
    # and query 15 minutes later — well inside its 4-hour window.
    acid_addition = next(a for a in state.additions if a.product_category == "acid")
    as_of = acid_addition.added_at + timedelta(minutes=15)

    # A reading with low free chlorine — the Reasoning Agent will propose
    # "add shock" here with no awareness that it's 15 min after an acid dose.
    readings = {
        "free_chlorine_ppm": 0.3,
        "ph": 7.3,
        "total_alkalinity_ppm": 100,
        "cyanuric_acid_ppm": 50,
    }

    return orchestrate_from_known_reading(
        readings, pool_id="demo_pool", as_of=as_of, source_type="demo_veto_case"
    )


if __name__ == "__main__":
    import json
    from dataclasses import asdict

    print("=" * 70)
    print("DEMO 1: Normal flow — Safety Agent approves")
    print("=" * 70)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prototype"))
    from case_study_data import build_case_study_state
    state = build_case_study_state()
    readings = {
        "free_chlorine_ppm": 6.29, "total_chlorine_ppm": 6.29, "ph": 7.7,
        "total_alkalinity_ppm": 115, "cyanuric_acid_ppm": 48,
    }
    as_of = state.readings[-1].read_at + timedelta(hours=1)
    trace = orchestrate_from_known_reading(readings, "demo_pool", as_of)
    print(f"Reasoning Agent proposed: {trace.reasoning.instructions}")
    print(f"Safety Agent verdict: {trace.safety.verdict}")
    print(f"Checked rules: {trace.safety.checked_rules}")

    print()
    print("=" * 70)
    print("DEMO 2: Veto scenario — Safety Agent BLOCKS the Reasoning Agent")
    print("=" * 70)
    trace = demo_veto_scenario()
    print(f"Reasoning Agent proposed: {trace.reasoning.instructions}")
    print(f"Reasoning Agent's proposed_action_type: {trace.reasoning.proposed_action_type}")
    print(f"Safety Agent verdict: {trace.safety.verdict}")
    print(f"Safety Agent reason: {trace.safety.reason}")
    print(f"Safe alternative given to human instead: {trace.safety.safe_alternative_instructions}")
    print()
    print("^ Note: the Reasoning Agent's proposal (add shock) was never")
    print("  shown to the human. The Safety Agent's independent check")
    print("  caught what the Reasoning Agent had no mechanism to see.")
