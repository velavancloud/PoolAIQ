"""
Extraction Agent

Scope: turn a photo into structured readings. Nothing else. This agent has
no knowledge of pool history, no knowledge of chemistry rules, and no
authority to recommend anything — it produces an ExtractionResult and its
job ends there.

Uses the actual prompts/extraction_prompt.md system prompt (same file the
webapp already used before this refactor — not duplicated).
"""

import os
import json
import base64
import sys

sys.path.insert(0, os.path.dirname(__file__))
from messages import ExtractionRequest, ExtractionResult  # noqa: E402

EXTRACTION_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "extraction_prompt.md"
)


def _load_system_prompt() -> str:
    with open(EXTRACTION_PROMPT_PATH) as f:
        content = f.read()
    start = content.find("```") + 3
    end = content.find("```", start)
    return content[start:end].strip()


def run(request: ExtractionRequest) -> ExtractionResult:
    """
    The agent's single entry point. Takes an ExtractionRequest, returns an
    ExtractionResult. This function signature IS the agent boundary — the
    orchestrator never reaches past this call into how extraction works
    internally.
    """
    import anthropic

    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt()
    b64_image = base64.b64encode(request.image_bytes).decode("utf-8")

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
                            "media_type": request.media_type,
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
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    parsed = json.loads(text)

    return ExtractionResult(
        source_type=parsed.get("source_type", "home_strip"),
        extraction_confidence=parsed.get("extraction_confidence", 0.5),
        readings=parsed.get("readings", {}),
        water_clarity_note=parsed.get("water_clarity_note"),
        floor_visible=parsed.get("floor_visible"),
        uncertain_fields=parsed.get("uncertain_fields", []),
        notes=parsed.get("notes", ""),
    )


def run_from_known_reading(readings_dict: dict, source_type: str = "demo_replay") -> ExtractionResult:
    """
    Used by the demo-replay path (scenarios that skip live vision extraction).
    Still returns a proper ExtractionResult so downstream agents see an
    identically-shaped message regardless of whether extraction was live or
    replayed — the Reasoning Agent cannot tell the difference, which is the
    point: the boundary is enforced by the message type, not by which code
    path produced it.
    """
    return ExtractionResult(
        source_type=source_type,
        extraction_confidence=1.0,
        readings=readings_dict,
        notes="Replayed from real case-study timeline, not live vision extraction.",
    )
