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
    Core demo endpoint: accepts an uploaded photo, extracts readings via
    Claude vision, merges into the real case-study history, and runs the
    actual reasoning engine — demonstrating the full pipeline live.
    """
    if "photo" not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400

    file = request.files["photo"]
    image_bytes = file.read()
    media_type = file.content_type or "image/jpeg"

    try:
        extraction = extract_reading_from_photo(image_bytes, media_type)
    except Exception as e:
        return jsonify({"error": f"Vision extraction failed: {str(e)}"}), 500

    readings_data = extraction.get("readings", {})
    now = datetime.now()
    new_reading = Reading(
        read_at=now,
        source=extraction.get("source_type", "home_strip"),
        free_chlorine_ppm=readings_data.get("free_chlorine_ppm"),
        total_chlorine_ppm=readings_data.get("total_chlorine_ppm"),
        ph=readings_data.get("ph"),
        total_alkalinity_ppm=readings_data.get("total_alkalinity_ppm"),
        calcium_hardness_ppm=readings_data.get("calcium_hardness_ppm"),
        cyanuric_acid_ppm=readings_data.get("cyanuric_acid_ppm"),
        copper_ppm=readings_data.get("copper_ppm"),
        phosphates_ppb=readings_data.get("phosphates_ppb"),
        salt_ppm=readings_data.get("salt_ppm"),
    )

    # THE KEY DEMONSTRATION: load the real historical state, append the new
    # reading, and reason over the FULL timeline — not the new reading alone.
    state = build_case_study_state()
    state.readings.append(new_reading)

    recommendation = recommend(state, now)

    return jsonify({
        "extraction": extraction,
        "new_reading": {
            "read_at": now.isoformat(),
            **readings_data,
        },
        "recommendation": recommendation,
        "history_length_used": len(state.readings),
    })


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

    if scenario == "early_no_pattern":
        as_of = state.readings[2].read_at
        state.readings = state.readings[:3]
    elif scenario == "root_cause_detected":
        as_of = state.readings[5].read_at
        state.readings = state.readings[:6]
    else:  # stabilized
        as_of = state.readings[-1].read_at + timedelta(hours=1)

    recommendation = recommend(state, as_of)
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
