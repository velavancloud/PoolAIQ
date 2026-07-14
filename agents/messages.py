"""
PoolAIQ Multi-Agent System — Message Contracts

This file defines the ACTUAL handoff contract between agents — the thing
that makes this genuinely multi-agent rather than three functions in one
script with new docstrings. Each agent:
  - receives a typed message as its only input (no reaching into another
    agent's internal state)
  - returns a typed message as its only output
  - has no knowledge of which agent will consume its output, or how

This mirrors how a real multi-agent framework (e.g. agents communicating
over a message bus, or as separate MCP-connected processes) would define
its contracts, without requiring this capstone to stand up actual network
boundaries between three Python processes for a demo. The BOUNDARY is real
(see orchestrator.py for how strictly it's enforced — the Safety Agent
gets zero access to how the Reasoning Agent arrived at its output, only the
proposal itself); the transport is in-process for demo simplicity, and
that tradeoff is stated in README.md Section 3c rather than hidden.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ExtractionRequest:
    """Input to the Extraction Agent: raw photo bytes + media type."""
    image_bytes: bytes
    media_type: str
    requested_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExtractionResult:
    """
    Output of the Extraction Agent. This is the ENTIRE interface the
    Reasoning Agent sees — it never sees the photo, the vision model's raw
    response, or any extraction internals. If extraction_confidence is low,
    that's the only signal the Reasoning Agent gets; it cannot inspect why.
    """
    source_type: str
    extraction_confidence: float
    readings: dict                      # field_name -> value | None
    water_clarity_note: Optional[str] = None
    floor_visible: Optional[bool] = None
    uncertain_fields: list = field(default_factory=list)
    notes: str = ""
    agent: str = "extraction_agent"


@dataclass
class ReasoningRequest:
    """
    Input to the Reasoning Agent: an ExtractionResult (or a directly-supplied
    reading, for the demo-replay path that skips live extraction) plus the
    pool_id to look up history for. The Reasoning Agent does its own
    retrieval (RAG) and its own history lookup — it is not handed
    pre-fetched context by the orchestrator, because a real Reasoning Agent
    in a distributed system would be responsible for its own grounding.
    """
    pool_id: str
    extraction: Optional[ExtractionResult]
    as_of: datetime = field(default_factory=datetime.now)


@dataclass
class ReasoningProposal:
    """
    Output of the Reasoning Agent. Called a PROPOSAL, deliberately not a
    'recommendation' or 'decision' — it has no authority to act. This is
    the entire interface the Safety Agent sees. The Safety Agent does NOT
    get access to retrieved_context_used, the pool's full reading history,
    or any of the Reasoning Agent's internal state — only this proposal,
    exactly as a human reviewer approving a coworker's draft would only see
    the draft, not their scratch notes.
    """
    diagnosis: str
    root_cause_vs_symptom: Optional[str]
    proposed_action_type: str            # 'add_chemical','wait_and_retest', etc.
    proposed_product_category: Optional[str]
    proposed_amount: Optional[float]
    proposed_unit: Optional[str]
    instructions: str
    confidence: float
    retrieved_context_used: list = field(default_factory=list)
    agent: str = "reasoning_agent"


@dataclass
class SafetyVerdict:
    """
    Output of the Safety Agent — the final, authoritative word. Two possible
    outcomes:
      - APPROVED: proposal passes unchanged, forwarded for human approval
      - VETOED: proposal is blocked; safe_alternative replaces it entirely.
        The original proposal is preserved in vetoed_proposal for audit,
        but it is never sent to the human for approval — the Safety Agent's
        veto is not a suggestion, it's a hard stop.

    Notably: this agent uses ZERO LLM calls. Every check here is
    deterministic, mirroring reasoning_engine.py's hard-coded safety rules,
    per README.md Section 4 principle 1 ("human-in-the-loop is
    non-negotiable... hard-coded, not model-decided"). A Safety Agent built
    as an LLM call reviewing another LLM's output would be the same model
    grading its own homework — see README.md Section 3c for why that
    design was explicitly rejected.
    """
    verdict: str                         # 'approved' or 'vetoed'
    reason: str
    forwarded_proposal: Optional[ReasoningProposal]
    vetoed_proposal: Optional[ReasoningProposal] = None
    safe_alternative_instructions: Optional[str] = None
    agent: str = "safety_agent"
    checked_rules: list = field(default_factory=list)  # audit trail of which rules ran


@dataclass
class OrchestrationTrace:
    """
    The full record of a request's path through all three agents — this is
    what the UI renders to make the handoffs VISIBLE rather than just
    trusting that they happened. Each agent's raw message is preserved so
    a panel/reviewer can inspect exactly what crossed each boundary.
    """
    extraction: Optional[ExtractionResult]
    reasoning: ReasoningProposal
    safety: SafetyVerdict
    completed_at: datetime = field(default_factory=datetime.now)
