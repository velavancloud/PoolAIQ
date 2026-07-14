"""
Reasoning Agent

Scope: given an extraction result and a pool_id, look up that pool's own
history, run RAG retrieval, run the deterministic pattern-detection rules,
and produce a PROPOSAL. This agent has real authority to reason, but zero
authority to act — its output is a ReasoningProposal, not an approved task.

This agent does NOT enforce the hard safety rules (wait windows, chemical
mixing conflicts) itself — those live in the Safety Agent, deliberately
separated so a bug or drift in the Reasoning Agent's logic cannot silently
also disable the safety check. (In the pre-multi-agent version of this
codebase, reasoning_engine.py's recommend() did both jobs in one function —
see README.md Section 3c for why splitting this was a genuine improvement,
not just restructuring for its own sake.)
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prototype"))

from messages import ReasoningRequest, ReasoningProposal  # noqa: E402
from reasoning_engine import (  # noqa: E402
    PoolState, Reading, IDEAL_RANGES, out_of_range,
    check_alkalinity_ph_coupling, detect_recurring_correction_failure,
    build_retrieval_index, build_query_from_state, _category_for,
    _format_citations,
)
from case_study_data import build_case_study_state  # noqa: E402


def _reading_from_extraction(extraction, as_of: datetime) -> Reading:
    r = extraction.readings if extraction else {}
    return Reading(
        read_at=as_of,
        source=extraction.source_type if extraction else "unknown",
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


def run(request: ReasoningRequest, state_builder=None) -> ReasoningProposal:
    """
    The agent's single entry point. NOTE: this function deliberately does
    NOT call reasoning_engine.recommend() — that function's hard safety
    gate (active_wait_window check) has been factored OUT into the Safety
    Agent for the multi-agent version, so this function only runs the
    diagnosis/pattern-detection half. See safety_agent.py for the other
    half, and orchestrator.py for how they're recombined.

    state_builder: optional callable returning a fresh PoolState, standing
    in for "look up this pool_id's history." Defaults to the fixed
    case-study dataset (build_case_study_state) — every existing call site
    and test keeps working unchanged. The webapp's merged_state.py passes
    build_merged_state instead, so live-uploaded readings that have been
    persisted are included in what this agent reasons over, without this
    agent needing to know anything about JSON files or persistence — it
    just calls whatever builder it's given, exactly like a real
    pool_id-keyed lookup would.
    """
    builder = state_builder or build_case_study_state
    state = builder()  # stands in for a pool_id-keyed lookup
    new_reading = _reading_from_extraction(request.extraction, request.as_of)
    state.readings.append(new_reading)
    state.readings.sort(key=lambda r: r.read_at)

    latest = state.readings[-1]

    # RAG retrieval — this agent's own responsibility, not injected.
    index = build_retrieval_index(state)
    query = build_query_from_state(state)
    retrieved = index.retrieve(query, k_kb=3, k_history=3)
    citations = _format_citations(retrieved)

    # Root-cause / trend detection (the actual thesis logic)
    alk_ph_pattern = check_alkalinity_ph_coupling(state)
    if alk_ph_pattern:
        kb_support = next((c for c in retrieved.get("knowledge_base", [])
                            if c.id == "kb_alk_ph_coupling"), None)
        diagnosis = alk_ph_pattern
        if kb_support:
            diagnosis += f" (Supported by general chemistry reference: {kb_support.text})"
        return ReasoningProposal(
            diagnosis=diagnosis,
            root_cause_vs_symptom="root_cause",
            proposed_action_type="equipment_or_technique_change",
            proposed_product_category=None,
            proposed_amount=None,
            proposed_unit=None,
            instructions="Turn pump OFF. Pour muriatic acid in ONE spot (not walking around). "
                         "Let sit undisturbed 30-60 min to offgas CO2 and lower alkalinity "
                         "specifically. Then resume circulation.",
            confidence=0.85,
            retrieved_context_used=citations,
        )

    for field_name in ("free_chlorine_ppm", "ph", "total_alkalinity_ppm", "cyanuric_acid_ppm"):
        val = getattr(latest, field_name)
        if val is None:
            continue
        recurrence = detect_recurring_correction_failure(state, field_name, request.as_of)
        if recurrence:
            return ReasoningProposal(
                diagnosis=recurrence,
                root_cause_vs_symptom="flagged_as_recurring_symptom",
                proposed_action_type="wait_and_retest",
                proposed_product_category=None,
                proposed_amount=None,
                proposed_unit=None,
                instructions="Do not re-correct yet. Investigate upstream cause "
                             "(check coupled metrics, equipment state, aeration sources) "
                             "before dosing again.",
                confidence=0.7,
                retrieved_context_used=citations,
            )

    for field_name, (low, high) in IDEAL_RANGES.items():
        val = getattr(latest, field_name, None)
        if val is None:
            continue
        status = out_of_range(field_name, val)
        if status:
            return ReasoningProposal(
                diagnosis=f"{field_name} reading {val} is {status} (ideal {low}-{high}).",
                root_cause_vs_symptom="symptom_level_only",
                proposed_action_type="add_chemical",
                proposed_product_category=_category_for(field_name, status),
                proposed_amount=None,
                proposed_unit=None,
                instructions=f"Correct {field_name} toward ideal range. Use conservative "
                             f"dose and retest before continuing.",
                confidence=0.6,
                retrieved_context_used=citations,
            )

    return ReasoningProposal(
        diagnosis="All tracked metrics within ideal range.",
        root_cause_vs_symptom=None,
        proposed_action_type="no_action",
        proposed_product_category=None,
        proposed_amount=None,
        proposed_unit=None,
        instructions="Continue weekly maintenance cadence.",
        confidence=0.95,
        retrieved_context_used=citations,
    )
