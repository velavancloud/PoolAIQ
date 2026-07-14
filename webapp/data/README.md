# Data directory

`added_readings.json` (git-ignored — this is per-user, per-session demo
state, not project source) is created automatically the first time
`reading_store.py` runs. It holds every reading persisted from a live photo
upload, layered on top of the fixed dataset in
`../../prototype/case_study_data.py` (which is never modified).

To reset a demo back to the original 7-reading case study, either:
- Click "Reset demo data" in the UI (Section 04, trend panel), or
- Delete `added_readings.json` directly, or
- Run `python3 -c "from reading_store import clear_store; clear_store()"`
  from the `webapp/` directory
