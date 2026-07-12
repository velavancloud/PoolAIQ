-- PoolAIQ Data Model
-- Designed to support: time-series retrieval, RAG grounding, safety-rule checks,
-- and task/notification generation.

CREATE TABLE pools (
    pool_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id            UUID NOT NULL REFERENCES users(user_id),
    gallons             INTEGER NOT NULL,             -- fixed, user-confirmed; never inferred per-visit
    surface_type        TEXT,                          -- e.g. 'pebble', 'plaster', 'vinyl', 'fiberglass'
    surface_install_date DATE,                          -- new plaster/pebble leaches calcium for ~1-2 yrs
    sanitizer_type       TEXT NOT NULL,                 -- 'salt', 'chlorine_tablet', 'bromine', etc.
    has_waterfall_or_aeration BOOLEAN DEFAULT FALSE,
    filter_type          TEXT,                          -- 'cartridge', 'sand', 'DE'
    filter_brand         TEXT,
    filter_clean_psi_baseline NUMERIC,                  -- established baseline for pressure-based cleaning
    location             TEXT,                          -- for weather/season context in reasoning
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chemical_readings (
    reading_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id             UUID NOT NULL REFERENCES pools(pool_id),
    source               TEXT NOT NULL,                 -- 'home_strip', 'retail_test', 'manual_entry'
    source_photo_url     TEXT,                           -- raw upload, for audit/re-extraction
    extraction_confidence NUMERIC,                       -- 0-1, from vision extraction layer
    free_chlorine_ppm    NUMERIC,
    total_chlorine_ppm   NUMERIC,
    ph                   NUMERIC,
    total_alkalinity_ppm NUMERIC,
    calcium_hardness_ppm NUMERIC,
    cyanuric_acid_ppm    NUMERIC,
    copper_ppm           NUMERIC,
    iron_ppm             NUMERIC,
    phosphates_ppb       NUMERIC,
    salt_ppm             NUMERIC,
    water_clarity_note    TEXT,                          -- free text or derived from photo ('hazy', 'clear', 'floor_visible')
    read_at              TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chemical_additions (
    addition_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id              UUID NOT NULL REFERENCES pools(pool_id),
    product_name          TEXT NOT NULL,                -- e.g. 'Leslie''s Power Powder Plus'
    product_category      TEXT NOT NULL,                -- 'shock','acid','base','clarifier','stabilizer',
                                                          -- 'metal_sequestrant','phosphate_remover','flocculant','salt'
    amount                NUMERIC NOT NULL,
    unit                  TEXT NOT NULL,                 -- 'oz','lbs','gal'
    added_at              TIMESTAMPTZ NOT NULL,
    recommended_by         TEXT,                          -- 'poolcopilot','retail_store','user_independent'
    task_id                UUID REFERENCES tasks(task_id), -- link back to the task that generated this, if any
    created_at             TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE equipment_events (
    event_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id                UUID NOT NULL REFERENCES pools(pool_id),
    event_type              TEXT NOT NULL,                -- 'filter_cleaned','filter_replaced','salt_cell_error',
                                                            -- 'salt_cell_cleaned','pump_setting_changed', etc.
    detail                  TEXT,
    pressure_psi_at_event    NUMERIC,
    occurred_at              TIMESTAMPTZ NOT NULL,
    created_at               TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tasks (
    task_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id                  UUID NOT NULL REFERENCES pools(pool_id),
    generated_by_recommendation_id UUID,                  -- links to the reasoning engine output that created it
    instruction               TEXT NOT NULL,               -- exact human-readable instruction
    product_name               TEXT,
    amount                     NUMERIC,
    unit                        TEXT,
    requires_wait_before_next   INTERVAL,                   -- e.g. '4 hours'
    depends_on_task_id           UUID REFERENCES tasks(task_id), -- sequencing
    status                       TEXT NOT NULL DEFAULT 'pending', -- 'pending','notified','completed','skipped'
    scheduled_for                 TIMESTAMPTZ,
    completed_at                   TIMESTAMPTZ,
    human_approved                 BOOLEAN DEFAULT FALSE,      -- hard gate before notification fires
    approved_by                     TEXT,                       -- 'owner','licensed_pro'
    created_at                      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE recommendations (
    recommendation_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id                     UUID NOT NULL REFERENCES pools(pool_id),
    triggered_by_reading_id      UUID REFERENCES chemical_readings(reading_id),
    diagnosis                    TEXT NOT NULL,               -- root-cause explanation, human-readable
    proposed_action                TEXT NOT NULL,
    confidence                     NUMERIC,                     -- 0-1
    safety_flags                    JSONB,                       -- e.g. {"conflicts_with_pending_task": true}
    retrieved_context_summary        TEXT,                        -- what history/KB was used (for explainability)
    status                            TEXT DEFAULT 'pending_review',  -- 'pending_review','approved','rejected','superseded'
    created_at                        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE notifications (
    notification_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id                       UUID NOT NULL REFERENCES tasks(task_id),
    channel                        TEXT NOT NULL,               -- 'sms','push'
    sent_at                         TIMESTAMPTZ,
    acknowledged_at                  TIMESTAMPTZ,
    created_at                        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE maintenance_schedules (
    schedule_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id                        UUID NOT NULL REFERENCES pools(pool_id),
    activated_at                     TIMESTAMPTZ,                 -- when pool graduated from 'recovery' to 'maintenance'
    cadence                          TEXT NOT NULL,               -- e.g. 'weekly'
    checklist                         JSONB NOT NULL,              -- e.g. ["test strip","visual clarity check","filter pressure check"]
    active                             BOOLEAN DEFAULT TRUE,
    created_at                         TIMESTAMPTZ DEFAULT now()
);

-- Indexes for the access patterns that matter most: time-series lookups per pool
CREATE INDEX idx_readings_pool_time ON chemical_readings (pool_id, read_at DESC);
CREATE INDEX idx_additions_pool_time ON chemical_additions (pool_id, added_at DESC);
CREATE INDEX idx_tasks_pool_status ON tasks (pool_id, status);
