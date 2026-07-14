"""
Safety Agent

Scope: the FINAL, AUTHORITATIVE check before any proposal reaches a human
for approval. This agent can VETO the Reasoning Agent's proposal outright
and substitute a safe alternative — it is not advisory, and its decision
is not subject to override by the Reasoning Agent or by re-running the
pipeline with different phrasing.

DESIGN DECISION, stated explicitly: this agent uses ZERO LLM calls. Every
check here is a deterministic Python function. This was a deliberate
rejection of the more obvious "add a third LLM call that reviews the
second LLM call's output" design, for a specific reason: an LLM checking
another LLM's safety is still fundamentally the same class of system
checking itself, just with extra steps and extra latency. It can still be
prompt-injected, still be inconsistent across runs, and still rationalize
around a check if asked the right way. A pool chemistry safety gate
(the wait-window rule, the metals-and-clarifier-same-day rule) should not
have a probability of firing — it should always fire when its condition
is met, every time, verifiably.

This mirrors and REPLACES reasoning_engine.py's active_wait_window check —
that logic now lives here instead, so a change to the Reasoning Agent's
prompt or rules can never accidentally also weaken this gate, because they
are now different files with different authors' worth of review surface.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prototype"))

from messages import ReasoningProposal, SafetyVerdict  # noqa: E402
from reasoning_engine import PoolState, Addition  # noqa: E402
from case_study_data import build_case_study_state  # noqa: E402


# ---------------------------------------------------------------------------
# Individual deterministic rules. Each returns None (no violation) or a
# string reason (violation found). Kept as small, independently-testable
# functions rather than one large conditional, so each rule can be unit
# tested and audited on its own.
# ---------------------------------------------------------------------------

def _rule_active_wait_window(state: PoolState, as_of: datetime) -> str | None:
    """Ported directly from reasoning_engine.py's active_wait_window, with
    the same bugfix (0 <= elapsed check) already applied there."""
    for a in reversed(state.additions):
        elapsed = (as_of - a.added_at).total_seconds() / 3600
        if 0 <= elapsed < a.requires_wait_hours:
            remaining = a.requires_wait_hours - elapsed
            return (
                f"Active wait window: a {a.product_category} addition "
                f"({a.amount}{a.unit}) at {a.added_at.strftime('%I:%M %p')} "
                f"requires {remaining:.1f} more hour(s) before any new "
                f"chemical addition."
            )
    return None


def _rule_metal_clarifier_same_day(state: PoolState, proposal: ReasoningProposal,
                                    as_of: datetime) -> str | None:
    """No metal sequestrant + clarifier on the same calendar day, per
    kb_metal_clarifier_conflict in the RAG knowledge base — encoded here as
    a hard rule too, not just a retrievable fact, because this specific
    conflict caused real damage risk in the source case study."""
    if proposal.proposed_product_category not in ("clarifier", "metal_sequestrant"):
        return None
    opposite = "metal_sequestrant" if proposal.proposed_product_category == "clarifier" else "clarifier"
    for a in state.additions:
        if a.product_category == opposite and a.added_at.date() == as_of.date():
            return (
                f"A {opposite} was added earlier today ({a.added_at.strftime('%I:%M %p')}). "
                f"Adding {proposal.proposed_product_category} the same day risks releasing "
                f"sequestered metal ions back into solution (see kb_metal_clarifier_conflict)."
            )
    return None


def _rule_max_single_dose(proposal: ReasoningProposal, gallons: int) -> str | None:
    """Placeholder for a manufacturer-max-dose check. Currently a no-op
    (proposals from the Reasoning Agent don't yet compute exact doses — see
    reasoning_engine.py's instructions field, which says 'use conservative
    dose' rather than a number) but the rule slot exists so this is where
    it plugs in once dose-calculation is built, rather than needing new
    architecture later."""
    return None


RULES = [
    ("active_wait_window", _rule_active_wait_window),
    ("metal_clarifier_same_day", _rule_metal_clarifier_same_day),
    ("max_single_dose", _rule_max_single_dose),
]


def run(proposal: ReasoningProposal, pool_id: str, as_of: datetime = None) -> SafetyVerdict:
    """
    The agent's single entry point. Takes a ReasoningProposal (and enough
    context to re-check state independently — pool_id, as_of), returns a
    SafetyVerdict. This is the ONLY function anything outside this module
    should call.

    Note this agent re-fetches pool state itself rather than trusting
    anything the Reasoning Agent might have passed along about state — if
    the Reasoning Agent were compromised, buggy, or simply lagging on stale
    data, the Safety Agent's own independent lookup is what actually
    protects the user, not shared trust in upstream correctness.
    """
    as_of = as_of or datetime.now()
    state = build_case_study_state()  # stands in for the same pool_id-keyed lookup

    checked = []
    for rule_name, rule_fn in RULES:
        checked.append(rule_name)
        if rule_fn is _rule_active_wait_window:
            violation = rule_fn(state, as_of)
        elif rule_fn is _rule_metal_clarifier_same_day:
            violation = rule_fn(state, proposal, as_of)
        else:
            violation = rule_fn(proposal, state.profile.gallons)

        if violation:
            return SafetyVerdict(
                verdict="vetoed",
                reason=violation,
                forwarded_proposal=None,
                vetoed_proposal=proposal,
                safe_alternative_instructions=(
                    f"No new chemical additions. {violation} Retest after the wait "
                    f"period before requesting a new recommendation."
                ),
                checked_rules=checked,
            )

    return SafetyVerdict(
        verdict="approved",
        reason="No safety rule violations detected.",
        forwarded_proposal=proposal,
        checked_rules=checked,
    )
