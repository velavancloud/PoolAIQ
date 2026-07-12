# Case Study: 18,000-Gallon Salt Pool Recovery Timeline

This is the real sequence of events that motivated PoolAIQ. Dates are approximate, reconstructed from photo timestamps and conversation flow. Names/location redacted.

## Pool Profile
- 18,000 gallons (retail store records showed conflicting 17,000 — a recurring source of dosing error)
- Pebble finish, salt chlorine generator, waterfall feature
- Sand/cartridge filter (later upgraded from generic "Pool Pure" to Pleatco cartridges)
- Two-story multiport valve + separate skimmer/main-drain diverter (non-standard config, added confusion around "vacuum to waste")

## Day 0 — Initial cloudy water report
- Water described as murky green/teal, no floor visibility even in shallow steps
- No baseline chemistry known
- 📹 See `timeline-photos/2026-05-24_dirty-pool-clip1.mp4` and `...clip2.mp4`

## Day 0-1 — First interventions (uncoordinated)
- Added liquid clarifier (brand A) — no effect after 6 hrs
- Added flocculant ("Sink to Clear") — required vacuum-to-waste, but no clear waste port initially identified (later found: garden-hose spigot bypass)
- Discovered pump could not vacuum-to-waste through the multiport valve; used bypass spigot instead
- **Failure mode:** two different clarifying products applied within 24 hrs without a chemistry baseline

## Day 2 — First home water test
- Total/Free chlorine: very low
- pH: ~7.8
- Hardness: ~500 (elevated)
- **Root cause hypothesis surfaces late:** low chlorine → algae/particulate not being controlled regardless of clarifier used
- 📹 `timeline-photos/2026-05-29_dirty-pool-clip.mp4` — water still visibly cloudy 5 days into the crisis

## Day 2-4 — Shock campaign #1
- 6 lbs granular shock added in two doses over 2 days
- 8 gallons liquid chlorine added for breakpoint chlorination (targeting high combined chlorine)
- **Success:** combined chlorine dropped from 6.86 ppm to near 0 — this was the single most effective intervention in the entire timeline

## Day 5-10 — Retail visits begin (Leslie's)
- First professional test reveals: Copper 0.5 ppm (previously unknown/undetected), Phosphates 232 ppb, CYA collapsing to 12-25 ppm
- Treatment plan issued: metals removal → shock → clarifier → CYA → phosphates (5-step sequence)
- **Failure mode:** each retail visit generated a *new* treatment plan without reference to what was mid-progress from the last visit. Products recommended (No Metal, Stain & Scale Remove, Power Powder Plus, Ultra Bright Advanced, Instant Conditioner Plus, NoPhos) totaled 6+ distinct chemicals across ~10 days.

## Day 10-14 — CYA and pH instability
- CYA raised from 12 → 50 ppm (successful, stayed stable rest of timeline)
- pH swung: 7.4 → 6.7 (over-corrected with acid) → 8.0 (soda ash overcorrection) → 7.2-7.4 (small-dose correction) → 8.0 again (recurred)
- **Root cause identified (day ~14, via reasoning not retail advice):** Total Alkalinity was elevated (115-240 range) acting as a pH buffer, causing pH to drift back up regardless of acid dosing. This pattern was invisible in any single retail visit but obvious across the time series.
- 📸 Home test strips across this window: `timeline-photos/2026-06-17_test-strip.jpg`,
  `2026-06-19_test-strip.jpg`, `2026-06-21_test-strip.jpg`, `2026-06-28_test-strip.jpg`
  — these form the actual data series the alkalinity/pH coupling pattern was
  detected from (see `prototype/reasoning_engine.py`'s
  `check_alkalinity_ph_coupling()` for the encoded logic)
- 📸 Clarity checks in parallel: `2026-06-20_pool-clarity.jpg`, `2026-06-20_deep-end.jpg`,
  `2026-06-24_pool-clarity.jpg`, `2026-07-01_pool-clarity.jpg`

## Day 14-16 — Alkalinity-targeted correction
- Switched from "walk-around" acid dosing (for pH) to "acid slug" method (pump off, single-spot application, let sit 30-60 min) — specifically targets alkalinity via CO2 offgassing
- Alkalinity dropped from 240+ → 115 (within ideal range) over ~2 applications
- **Turning point:** once alkalinity stabilized, pH held without further intervention

## Day 16-18 — Equipment factor
- Filter cartridges upgraded from generic to Pleatco (higher micron rating)
- 📸 `timeline-photos/2026-07-02_pleatco-filter-delivery.jpeg` — new filter arrival
- Filter pressure baseline established (10 PSI clean) for future pressure-based cleaning cadence (vs. blind calendar-based cleaning)
- Salt generator "Very Low Salt" error investigated — determined to be sensor lag after fresh salt addition, not a hardware fault; salt cell itself ruled out as root cause
- 📸 Clarity trend continues to improve: `2026-07-03_pool-clarity.jpg`,
  `2026-07-04_pool-clarity.jpg`, `2026-07-05_pool-clarity.jpg`

## Day 18-20 — Final stabilization
- Free/Total chlorine converged (6.29/6.29 — zero combined chlorine, best reading of entire timeline)
- Alkalinity: 115 (in range)
- CYA: 48 (in range)
- Copper: 0 ppm (fully resolved)
- Iron: 0 ppm
- Salt: 3223 ppm (in range)
- Water Test Quality Score (retail metric): 70%, up from 50% two visits prior
- Only remaining flag: Phosphates 114 ppb (elevated but explicitly deprioritized by retail advisor, confirmed sound given chlorine was finally holding)
- Chlorine intentionally over-shocked from super-chlorinate cycle; corrected with small-dose neutralizer (3 oz) rather than full product dose, verified before swim
- 📸 `timeline-photos/2026-07-13_deep-end.jpg` — best post-recovery deep-end
  visibility shot in the whole dataset; good before/after closing image

## Key Takeaways (encoded into PoolAIQ's reasoning rules)

1. **The visible symptom (cloudy water) had a hidden root cause (alkalinity buffering pH) that took ~2 weeks to identify manually.** A system with full history could have surfaced this pattern in days by correlating repeated pH corrections against a stable/rising alkalinity trend.
2. **Retail advice, taken alone, is not wrong — it's incomplete.** Each individual recommendation was chemically sound. The failure was sequencing and lack of continuity across visits.
3. **The single highest-leverage action (breakpoint chlorination) happened early and worked immediately** — but its benefit was partially undone by subsequent uncoordinated pH swings. A system enforcing "stabilize one variable before touching the next" would have preserved that win.
4. **Human skepticism of automated/retail advice was itself a valuable signal** ("I don't trust them," "their recommendation is to sell product") — PoolAIQ should treat user pushback as a prompt to explain *reasoning*, not just re-assert a recommendation.
5. **Equipment questions (salt cell, filter brand, pressure gauge) were treated as separate from chemistry — but they're part of the same system.** PoolAIQ's data model must include equipment state alongside chemical readings.
