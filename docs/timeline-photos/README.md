# Timeline Photo Index

Real photos/videos from the case study, dated and named by the pool owner. This
is the actual ground-truth visual dataset for testing PoolAIQ's Vision
Extraction Layer against known dates.

**Naming convention:** `YYYY-MM-DD_<description>.<ext>` — sortable by filename,
self-documenting content.

## Files

| Date | File | Content |
|---|---|---|
| 2026-05-24 | `2026-05-24_dirty-pool-clip1.mp4` | Video, dirty/cloudy pool, early crisis phase |
| 2026-05-24 | `2026-05-24_dirty-pool-clip2.mp4` | Video, dirty/cloudy pool, same day |
| 2026-05-29 | `2026-05-29_dirty-pool-clip.mp4` | Video, dirty/cloudy pool, 5 days later |
| 2026-06-17 | `2026-06-17_test-strip.jpg` | Home test strip reading |
| 2026-06-19 | `2026-06-19_test-strip.jpg` | Home test strip reading |
| 2026-06-20 | `2026-06-20_pool-clarity.jpg` | Pool water clarity check |
| 2026-06-20 | `2026-06-20_deep-end.jpg` | Deep end visibility check, same day |
| 2026-06-21 | `2026-06-21_test-strip.jpg` | Home test strip reading |
| 2026-06-24 | `2026-06-24_pool-clarity.jpg` | Pool water clarity check |
| 2026-06-28 | `2026-06-28_test-strip.jpg` | Home test strip reading |
| 2026-07-01 | `2026-07-01_pool-clarity.jpg` | Pool water clarity check |
| 2026-07-02 | `2026-07-02_pleatco-filter-delivery.jpeg` | New Pleatco filter cartridges arrive (equipment upgrade event) |
| 2026-07-03 | `2026-07-03_pool-clarity.jpg` | Pool water clarity check |
| 2026-07-04 | `2026-07-04_pool-clarity.jpg` | Pool water clarity check |
| 2026-07-05 | `2026-07-05_pool-clarity.jpg` | Pool water clarity check |
| 2026-07-13 | `2026-07-13_deep-end.jpg` | Deep end visibility, post-stabilization |

## Metadata note

None of the original files (webp, jpeg, or mp4) had usable embedded
`DateTimeOriginal`/`CreationTime` EXIF or container metadata — verified via
`exiftool` and `ffprobe` during ingestion (WhatsApp and most re-shared/exported
images strip this by default; the `.mp4` containers had only codec tags, no
timestamps). **All dates above are user-provided**, not machine-extracted.

This is itself a useful data point for the capstone: **a production version of
PoolAIQ's Vision Extraction Layer cannot rely on file metadata for
timestamping** and should default to using the upload/message timestamp from
the ingestion channel (SMS/app) as the source of truth, with EXIF as a
secondary signal only when present.

## Suggested use in the write-up

- Pair `2026-05-24` / `2026-05-29` videos with the "Day 0-1" crisis-phase
  narrative in `case-study-timeline.md`
- Pair `2026-06-17` through `2026-06-29` test strips with the pH/alkalinity
  swing narrative ("Day 10-14")
- `2026-07-02` filter delivery photo anchors the "Day 16-18 — Equipment
  factor" section
- `2026-07-13_deep-end.jpg` is the latest/most-recovered clarity photo — good
  closing image for a before/after comparison in the final presentation
