"""
Server-side inference tool.

Distinct from agents/extraction_agent.py's vision call, which is made by
the WEBAPP using the webapp's own ANTHROPIC_API_KEY. This module lets the
MCP SERVER itself make a Claude call, using ITS OWN configured key
(config.py's anthropic_api_key) — useful for any MCP client that wants a
reasoning/summarization capability without needing its own Anthropic
credentials, or for scenarios where the caller (e.g. a lightweight script,
a non-Python client) shouldn't have direct model access at all, only
access to this specific, scoped tool.

This is intentionally NOT a general-purpose "ask Claude anything" proxy.
The tool's scope is narrow and specific: summarize/explain a pool chemistry
reading in plain language, grounded in the same knowledge base entries
used by prototype/rag/knowledge_base.py where relevant. A general proxy
would defeat the purpose of having a scoped MCP tool boundary at all — see
README.md Section 3b's discussion of why tool boundaries should be
narrow and specific, not general delegation.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import config  # noqa: E402


PLAIN_LANGUAGE_SYSTEM_PROMPT = """You are a pool chemistry explainer tool, called via MCP.
Your ONLY job: given a set of pool water readings, explain in 2-4 plain-English
sentences what's notable about them, for a non-expert pool owner.

Rules:
- No chemical dosing instructions or product recommendations — that is
  explicitly out of scope for this tool (dosing decisions go through
  PoolAIQ's Reasoning Agent + Safety Agent, not through this explainer).
- Do not invent numbers not present in the input.
- If everything is in range, say so plainly and briefly — do not manufacture
  concern where none exists.
- Keep it to 2-4 sentences. This is a summary, not a report.
"""


def reason_about_reading(readings: dict) -> dict:
    """
    Calls Claude (using config.anthropic_api_key) to produce a plain-
    language explanation of a set of readings. Returns a dict rather than
    raising on missing config, so the calling tool function in server.py
    can return a clean JSON error to the MCP client instead of a stack
    trace crossing the protocol boundary.
    """
    if not config.anthropic_api_key:
        return {
            "error": "Server-side inference is not configured. Set "
                     "ANTHROPIC_API_KEY in the MCP server's environment "
                     "to enable the reason_about_reading tool."
        }

    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    readings_text = ", ".join(
        f"{k}={v}" for k, v in readings.items() if v is not None
    )
    if not readings_text:
        return {"error": "No non-null readings provided."}

    try:
        response = client.messages.create(
            model=config.inference_model,
            max_tokens=300,
            system=PLAIN_LANGUAGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Readings: {readings_text}"}],
        )
        explanation = response.content[0].text.strip()
        return {
            "explanation": explanation,
            "model_used": config.inference_model,
            "readings_echoed": readings,
        }
    except Exception as e:
        return {"error": f"Inference call failed: {str(e)}"}


if __name__ == "__main__":
    if not config.anthropic_api_key:
        print("ANTHROPIC_API_KEY not set — this test will show the clean error path.")
    result = reason_about_reading({"ph": 8.0, "total_alkalinity_ppm": 180, "free_chlorine_ppm": 0.3})
    print(json.dumps(result, indent=2))
