"""
A small, hand-curated knowledge base of GENERAL pool chemistry facts —
deliberately distinct from this pool's own history (chemical_readings /
chemical_additions), which lives in case_study_data.py.

RAG retrieves from BOTH corpora separately:
  - this pool's own history (primary signal — what actually happened here)
  - this general knowledge base (secondary signal — domain facts that
    explain WHY a pattern matters)

This is intentionally small (~15 entries) and honestly documented as a seed
corpus, not a production knowledge base. See README.md Section 3a for the
stated limitation. In a production system this would be sourced from
manufacturer technical bulletins (Leslie's/Hayward/Pentair), CPO
(Certified Pool Operator) training material, and structured extraction from
product label instructions — not hand-written like this.
"""

from dataclasses import dataclass


@dataclass
class KBEntry:
    id: str
    category: str          # 'chemistry_coupling','safety','equipment','dosing'
    text: str


KNOWLEDGE_BASE = [
    KBEntry(
        id="kb_alk_ph_coupling",
        category="chemistry_coupling",
        text="Total Alkalinity acts as a buffer for pH. When alkalinity is "
             "elevated (above ~120 ppm), pH will resist downward correction "
             "and tend to drift back up over 24-72 hours even after acid is "
             "added, because the buffering capacity keeps neutralizing the "
             "acid's effect. Correcting alkalinity first, then pH, is more "
             "stable than repeatedly re-dosing acid for pH alone.",
    ),
    KBEntry(
        id="kb_acid_slug_method",
        category="dosing",
        text="The 'acid slug' method — pouring muriatic acid into a single "
             "spot with the pump OFF and letting it sit undisturbed for "
             "30-60 minutes before resuming circulation — targets Total "
             "Alkalinity specifically, via localized CO2 offgassing. This "
             "differs from the standard 'walk-around' acid dosing method "
             "(pump running, acid poured while walking the perimeter), "
             "which primarily affects pH with a smaller alkalinity effect.",
    ),
    KBEntry(
        id="kb_breakpoint_chlorination",
        category="dosing",
        text="Breakpoint chlorination requires raising free chlorine to "
             "roughly 10x the combined chlorine (chloramine) level to fully "
             "oxidize and eliminate combined chlorine. Doses below this "
             "threshold are consumed by the existing combined chlorine "
             "without net free chlorine gain, which can look like 'the "
             "shock isn't working' when actually the dose was simply too "
             "small to cross the breakpoint threshold.",
    ),
    KBEntry(
        id="kb_cya_sunlight_protection",
        category="chemistry_coupling",
        text="Cyanuric acid (CYA/stabilizer) protects free chlorine from "
             "UV degradation. Without adequate CYA (below ~30 ppm), direct "
             "sunlight can destroy 90%+ of free chlorine within a few hours, "
             "making it appear that chlorine is being 'consumed' by demand "
             "when it is actually being destroyed by sun exposure before it "
             "can act as a sanitizer.",
    ),
    KBEntry(
        id="kb_cya_max_range",
        category="dosing",
        text="CYA above 100 ppm causes 'chlorine lock' — high stabilizer "
             "concentration reduces the effective killing power of a given "
             "free chlorine ppm reading, meaning the same free chlorine "
             "number sanitizes less effectively as CYA rises. CYA should not "
             "be corrected upward repeatedly without checking current level "
             "first, since it cannot be lowered except by dilution/draining.",
    ),
    KBEntry(
        id="kb_copper_source",
        category="chemistry_coupling",
        text="Elevated copper (above 0.2 ppm) in pool water most commonly "
             "originates from copper-based algaecides, corroding copper "
             "heat-exchanger equipment, or source water with high copper "
             "content. Copper causes green/blue-green staining and tinted "
             "water, and must be sequestered (metal sequestrant) or removed "
             "before shock treatment, since oxidizing copper via chlorine "
             "shock can precipitate it out as visible staining on pool "
             "surfaces rather than removing it from the water.",
    ),
    KBEntry(
        id="kb_metal_clarifier_conflict",
        category="safety",
        text="Metal sequestrant/stain-removal products and clarifiers should "
             "not be added on the same day. Sequestrants work by binding "
             "dissolved metals in solution; clarifiers work by coagulating "
             "fine particles for filtration. Combined, the clarifier can "
             "coagulate the metal-sequestrant complex before it has fully "
             "sequestered the metal, releasing free metal ions back into "
             "solution and re-triggering staining risk.",
    ),
    KBEntry(
        id="kb_salt_cell_scale",
        category="equipment",
        text="Salt chlorine generator cells can develop calcium scale "
             "buildup on their plates when Calcium Hardness is elevated "
             "(above ~400 ppm), which insulates the plates and reduces "
             "chlorine production efficiency even when salt level itself "
             "reads correctly. Visual inspection of the cell plates for "
             "white/crusty deposits is the direct diagnostic; a 'low "
             "chlorine output' symptom with normal salt readings should "
             "prompt a cell inspection before assuming a chemistry-only "
             "cause.",
    ),
    KBEntry(
        id="kb_salt_sensor_lag",
        category="equipment",
        text="Salt chlorine generators typically report salt level via a "
             "conductivity sensor that requires the added salt to be fully "
             "dissolved and circulated (commonly 24-48 hours) before the "
             "reading stabilizes. A 'low salt' error immediately after "
             "adding salt is expected sensor lag, not necessarily a true "
             "low-salt or hardware-fault condition, and should not "
             "immediately prompt adding more salt.",
    ),
    KBEntry(
        id="kb_filter_pressure_cleaning",
        category="equipment",
        text="Filter cleaning should be triggered by pressure rise above the "
             "clean baseline (typically 8-10 PSI above baseline), not by a "
             "fixed calendar schedule. Cleaning too early (before pressure "
             "rises) wastes the filter's current debris-capturing capacity; "
             "cleaning too late (after excessive pressure rise) reduces flow "
             "rate and circulation effectiveness, which itself can "
             "contribute to cloudy water.",
    ),
    KBEntry(
        id="kb_phosphates_algae_fuel",
        category="chemistry_coupling",
        text="Phosphates function as a nutrient source for algae growth but "
             "do not themselves cause algae — algae requires both a viable "
             "spore/organism present AND inadequate sanitizer (free "
             "chlorine) to control it. In a pool with properly maintained "
             "free chlorine (1-4 ppm) and adequate CYA protection, elevated "
             "phosphates alone are unlikely to trigger a bloom, which is why "
             "phosphate remediation is often deprioritized until chlorine "
             "and CYA are first stabilized.",
    ),
    KBEntry(
        id="kb_waterfall_aeration_ph",
        category="chemistry_coupling",
        text="Waterfall or fountain features that aerate pool water increase "
             "the rate of CO2 offgassing, which raises pH over time — "
             "opposite to the acid-slug method's intentional use of the same "
             "mechanism. A pool with a frequently-running waterfall may show "
             "persistent upward pH drift independent of any chemical "
             "addition, and reducing waterfall runtime is a valid lever "
             "alongside (not instead of) acid dosing.",
    ),
    KBEntry(
        id="kb_wait_windows_chemical_mixing",
        category="safety",
        text="A minimum 4-hour wait window between most sequential chemical "
             "additions (e.g., acid then shock, or shock then clarifier) "
             "allows the first product to fully react and distribute before "
             "introducing a second product. Adding chemicals back-to-back "
             "without this window risks localized concentrated reactions "
             "(e.g., chlorine gas release from acid + chlorine contact) and "
             "makes it impossible to attribute a subsequent reading change "
             "to a specific cause.",
    ),
    KBEntry(
        id="kb_calcium_hardness_scale",
        category="chemistry_coupling",
        text="Calcium Hardness above the ideal range (200-400 ppm) "
             "increases scale formation risk on pool surfaces and equipment, "
             "including salt cell plates and heater elements, but does not "
             "directly cause cloudy water on its own — it becomes a clarity "
             "issue primarily in combination with high pH and high "
             "alkalinity, where calcium carbonate can precipitate out of "
             "solution as fine white particulate, appearing as persistent "
             "haze that clarifiers alone cannot resolve.",
    ),
    KBEntry(
        id="kb_pleatco_cartridge_micron",
        category="equipment",
        text="Cartridge filter micron rating determines the smallest "
             "particle size the filter can capture; generic/budget cartridge "
             "brands commonly use a coarser pleated media (loosely spaced "
             "pleats, lower effective micron rating) than name-brand "
             "replacements, meaning two cartridges of identical physical "
             "size and nominal fit can have meaningfully different real-world "
             "filtration effectiveness on fine suspended particulate.",
    ),
]


def get_all_entries() -> list:
    return KNOWLEDGE_BASE


if __name__ == "__main__":
    print(f"Knowledge base: {len(KNOWLEDGE_BASE)} entries")
    for e in KNOWLEDGE_BASE:
        print(f"  [{e.category}] {e.id}")
