"""
PoolAIQ Reasoning Engine — Prototype (Phase 3-4 from README roadmap)

This is a deterministic, rule-based core with a trend-detection layer on top.
It demonstrates the central thesis of the project: a system with access to a
pool's FULL HISTORY catches problems that single-visit advice (like the retail
treatment plans in the case study) structurally cannot.

Run: python3 reasoning_engine.py
(Runs against the bundled case_study_data.py, replaying the real timeline.)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


IDEAL_RANGES = {
    "free_chlorine_ppm": (1, 4),
    "ph": (7.2, 7.8),
    "total_alkalinity_ppm": (80, 120),
    "calcium_hardness_ppm": (200, 400),
    "cyanuric_acid_ppm": (50, 100),
    "copper_ppm": (0, 0.2),
    "phosphates_ppb": (0, 100),
    "salt_ppm": (2700, 3400),
}


@dataclass
class Reading:
    read_at: datetime
    source: str
    free_chlorine_ppm: Optional[float] = None
    total_chlorine_ppm: Optional[float] = None
    ph: Optional[float] = None
    total_alkalinity_ppm: Optional[float] = None
    calcium_hardness_ppm: Optional[float] = None
    cyanuric_acid_ppm: Optional[float] = None
    copper_ppm: Optional[float] = None
    phosphates_ppb: Optional[float] = None
    salt_ppm: Optional[float] = None


@dataclass
class Addition:
    added_at: datetime
    product_category: str          # 'shock','acid','base','clarifier','stabilizer','metal_sequestrant'
    amount: float
    unit: str
    requires_wait_hours: float = 4.0


@dataclass
class PoolProfile:
    gallons: int
    sanitizer_type: str = "salt"
    has_waterfall_or_aeration: bool = False


@dataclass
class PoolState:
    profile: PoolProfile
    readings: list = field(default_factory=list)   # chronological
    additions: list = field(default_factory=list)  # chronological

    def latest_reading(self) -> Optional[Reading]:
        return self.readings[-1] if self.readings else None

    def readings_for(self, field_name: str, limit: int = 5):
        vals = [(r.read_at, getattr(r, field_name)) for r in self.readings if getattr(r, field_name) is not None]
        return vals[-limit:]

    def most_recent_addition(self, category: str) -> Optional[Addition]:
        matches = [a for a in self.additions if a.product_category == category]
        return matches[-1] if matches else None

    def active_wait_window(self, as_of: datetime) -> Optional[Addition]:
        """Return the most recent addition whose wait window hasn't elapsed yet, if any."""
        for a in reversed(self.additions):
            elapsed = (as_of - a.added_at).total_seconds() / 3600
            if elapsed < a.requires_wait_hours:
                return a
        return None


def out_of_range(field_name: str, value: float) -> Optional[str]:
    if field_name not in IDEAL_RANGES or value is None:
        return None
    low, high = IDEAL_RANGES[field_name]
    if value < low:
        return "low"
    if value > high:
        return "high"
    return None


def detect_recurring_correction_failure(state: PoolState, field_name: str, as_of: datetime) -> Optional[str]:
    """
    Core differentiator vs single-visit retail advice: look at this metric's
    history. If it has swung out-of-range -> corrected -> back out-of-range
    two or more times, flag it as a likely symptom of an unaddressed root cause
    rather than something to just correct again.
    """
    history = state.readings_for(field_name, limit=8)
    if len(history) < 3:
        return None

    # Don't flag a resolved pattern if the CURRENT reading is fine now.
    if out_of_range(field_name, history[-1][1]) is None:
        return None

    statuses = [out_of_range(field_name, v) for _, v in history]
    # Count transitions from "out of range" -> "in range" -> "out of range"
    swings = 0
    for i in range(1, len(statuses) - 1):
        prev, cur, nxt = statuses[i - 1], statuses[i], statuses[i + 1]
        if prev in ("low", "high") and cur is None and nxt in ("low", "high"):
            swings += 1
        # also catch low->high->low direct overcorrection swings
        if prev == "low" and cur == "high":
            swings += 1
        if prev == "high" and cur == "low":
            swings += 1

    if swings >= 2:
        return (
            f"'{field_name}' has swung out-of-range {swings} times across recent readings "
            f"despite correction attempts. This pattern usually means a different, "
            f"uncorrected variable is driving it back — not that the correction dose was wrong."
        )
    return None


def check_alkalinity_ph_coupling(state: PoolState) -> Optional[str]:
    """
    Encodes the actual root-cause finding from the case study: repeated pH
    corrections failing because Total Alkalinity was elevated and buffering
    pH back up. This is exactly the kind of cross-metric pattern a single
    retail visit cannot see, but a full history makes obvious.
    """
    ph_history = state.readings_for("ph", limit=6)
    alk_history = state.readings_for("total_alkalinity_ppm", limit=6)
    if len(ph_history) < 3 or len(alk_history) < 2:
        return None

    # Only fire if the CURRENT (most recent) pH reading is itself out of range —
    # otherwise we'd keep flagging a resolved historical pattern forever.
    latest_ph_status = out_of_range("ph", ph_history[-1][1])
    ph_swinging = latest_ph_status is not None and sum(
        1 for _, v in ph_history if out_of_range("ph", v)
    ) >= 2
    alk_high = out_of_range("total_alkalinity_ppm", alk_history[-1][1]) == "high"

    if ph_swinging and alk_high:
        return (
            "ROOT CAUSE PATTERN DETECTED: pH is unstable AND Total Alkalinity has been "
            "reading high. High alkalinity acts as a pH buffer, pulling pH back up regardless "
            "of how much acid is added. Recommend targeting alkalinity directly (pump-off "
            "'acid slug' method: single-spot application, no circulation for 30-60 min) rather "
            "than continuing to chase pH with walk-around acid dosing."
        )
    return None


def recommend(state: PoolState, as_of: datetime) -> dict:
    """Main entry point. Returns a recommendation dict matching the reasoning_prompt.md output shape."""

    latest = state.latest_reading()
    if latest is None:
        return {"proposed_action": {"type": "no_action"}, "diagnosis": "No readings yet."}

    # --- HARD SAFETY RULES FIRST (non-negotiable, independent of any pattern detection) ---
    active_wait = state.active_wait_window(as_of)
    if active_wait:
        remaining = active_wait.requires_wait_hours - (as_of - active_wait.added_at).total_seconds() / 3600
        return {
            "diagnosis": f"A {active_wait.product_category} addition is still within its "
                         f"required wait window ({active_wait.amount}{active_wait.unit} added "
                         f"{active_wait.added_at.strftime('%I:%M %p')}).",
            "root_cause_vs_symptom": None,
            "proposed_action": {
                "type": "wait_and_retest",
                "instructions": f"No new additions. Wait {remaining:.1f} more hour(s), then retest.",
                "retest_at": (active_wait.added_at + timedelta(hours=active_wait.requires_wait_hours)).isoformat(),
            },
            "confidence": 1.0,
            "requires_human_approval": True,
            "safety_gate_triggered": True,
        }

    # --- ROOT CAUSE / TREND DETECTION (the actual thesis of this project) ---
    alk_ph_pattern = check_alkalinity_ph_coupling(state)
    if alk_ph_pattern:
        return {
            "diagnosis": alk_ph_pattern,
            "root_cause_vs_symptom": "root_cause",
            "proposed_action": {
                "type": "equipment_or_technique_change",
                "instructions": "Turn pump OFF. Pour muriatic acid in ONE spot (not walking around). "
                                 "Let sit undisturbed 30-60 min to offgas CO2 and lower alkalinity "
                                 "specifically. Then resume circulation.",
            },
            "confidence": 0.85,
            "requires_human_approval": True,
        }

    for field_name in ("free_chlorine_ppm", "ph", "total_alkalinity_ppm", "cyanuric_acid_ppm"):
        val = getattr(latest, field_name)
        if val is None:
            continue
        recurrence = detect_recurring_correction_failure(state, field_name, as_of)
        if recurrence:
            return {
                "diagnosis": recurrence,
                "root_cause_vs_symptom": "flagged_as_recurring_symptom",
                "proposed_action": {
                    "type": "wait_and_retest",
                    "instructions": "Do not re-correct yet. Investigate upstream cause "
                                     "(check coupled metrics, equipment state, aeration sources) "
                                     "before dosing again.",
                },
                "confidence": 0.7,
                "requires_human_approval": True,
            }

    # --- STANDARD SINGLE-METRIC CHECK (fallback, same as any retail advisor would do) ---
    for field_name, (low, high) in IDEAL_RANGES.items():
        val = getattr(latest, field_name, None)
        if val is None:
            continue
        status = out_of_range(field_name, val)
        if status:
            return {
                "diagnosis": f"{field_name} reading {val} is {status} (ideal {low}-{high}).",
                "root_cause_vs_symptom": "symptom_level_only",
                "proposed_action": {
                    "type": "add_chemical",
                    "product_category": _category_for(field_name, status),
                    "instructions": f"Correct {field_name} toward ideal range. Use conservative "
                                     f"dose and retest before continuing.",
                },
                "confidence": 0.6,
                "requires_human_approval": True,
            }

    return {
        "diagnosis": "All tracked metrics within ideal range.",
        "root_cause_vs_symptom": None,
        "proposed_action": {"type": "no_action", "instructions": "Continue weekly maintenance cadence."},
        "confidence": 0.95,
        "requires_human_approval": False,
    }


def _category_for(field_name: str, status: str) -> str:
    mapping = {
        ("ph", "low"): "base",
        ("ph", "high"): "acid",
        ("total_alkalinity_ppm", "high"): "acid",
        ("total_alkalinity_ppm", "low"): "base",
        ("free_chlorine_ppm", "low"): "shock",
        ("cyanuric_acid_ppm", "low"): "stabilizer",
        ("copper_ppm", "high"): "metal_sequestrant",
        ("phosphates_ppb", "high"): "phosphate_remover",
    }
    return mapping.get((field_name, status), "unknown")


if __name__ == "__main__":
    from case_study_data import build_case_study_state

    state = build_case_study_state()
    as_of = state.readings[-1].read_at + timedelta(hours=1)

    result = recommend(state, as_of)
    import json
    print(json.dumps(result, indent=2, default=str))
