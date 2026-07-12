# Failure Mode Catalog → System Features

Each row: an observed real-world failure → the PoolAIQ feature designed to prevent it.

| # | Failure Mode | Observed Instance | Preventing Feature |
|---|---|---|---|
| 1 | **No memory across visits** | Each Leslie's test generated an independent treatment plan, unaware of chemicals added days earlier | Persistent Pool State Store; every recommendation call is grounded in full history via RAG |
| 2 | **Chemical whiplash** | 6+ distinct products added within ~10 days, several with overlapping/conflicting purposes | "One variable at a time" enforcement rule in Reasoning Engine — blocks new chemical suggestions while a prior treatment's wait-window is still active |
| 3 | **Symptom-chasing instead of root cause** | pH corrected repeatedly without noticing alkalinity was the actual driver | Trend-detection pass in Reasoning Engine: flags when a corrected metric recurs to the same failure state ≥2 times, prompts root-cause analysis over stable/upstream variable |
| 4 | **Pool size discrepancy causing dosing error** | Retail records said 17,000 gal; actual pool was 18,000 gal | Pool profile is a fixed, user-confirmed field; all dosing calculations reference the stored profile value, never a per-visit re-entry |
| 5 | **Unclear vacuum-to-waste path** | Multiport valve config was non-standard; required trial-and-error to find the bypass spigot | Equipment onboarding flow captures filter/valve type + photos once; system references this for any future filtration/vacuum guidance instead of re-diagnosing |
| 6 | **Timing violations** | Products combined same-day that manufacturer instructions said required 4-72 hr separation | Hard-coded (non-LLM) safety rule table checked before any task is created — independent of reasoning layer's output, cannot be overridden by generative reasoning |
| 7 | **Ambiguous "wait and see" vs "act now"** | Uncertainty about whether to shock during daylight vs dusk, whether pH swing needed immediate correction | Reasoning Engine explicitly supports "no action, retest in N hours" as a first-class recommended task type, not just a fallback |
| 8 | **Equipment vs chemistry treated as separate problems** | Salt cell error, filter brand, pressure gauge questions handled in isolated side-conversations | Unified Pool State Store includes equipment_events table alongside chemical_readings — both are retrieved together for reasoning |
| 9 | **Overcorrection from big-bang dosing** | Soda ash dose swung pH from 6.7 to 8.0 | Recommendation Engine biases toward conservative/incremental doses when a metric is being actively corrected (vs. one-shot "get to target" math), with explicit "retest before continuing" checkpoints |
| 10 | **User distrust of generic advice, no escalation path** | "I don't trust Leslie's" — no way to get a second opinion grounded in the pool's own history | Human-in-the-loop approval step allows user to request "explain your reasoning" before accepting a task, with prior evidence cited inline |
| 11 | **No structured record of what was tried** | Reconstructing the timeline required re-reading dozens of freeform chat messages | Every photo/reading/action is logged as a structured, timestamped event from day one — timeline view is a queryable artifact, not a reconstruction exercise |
| 12 | **Manual re-photographing of the same printouts across visits** | Leslie's printouts re-uploaded and manually re-parsed by a human (Claude) each time | Vision Extraction Layer runs automatically on any uploaded photo, structured output written directly to Pool State Store |
