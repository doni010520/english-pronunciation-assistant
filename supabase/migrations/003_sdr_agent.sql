-- =============================================
-- SDR Agent tables
-- =============================================

-- Leads pipeline
CREATE TABLE IF NOT EXISTS sdr_leads (
    phone       TEXT PRIMARY KEY,
    name        TEXT,
    type        TEXT CHECK (type IN ('school_owner', 'coordinator', 'independent_teacher', 'other')),
    school_name TEXT,
    student_count INTEGER,
    main_pain   TEXT,
    source      TEXT,
    status      TEXT DEFAULT 'new' CHECK (status IN ('new', 'qualifying', 'interested', 'demo_scheduled', 'closed_won', 'closed_lost')),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- SDR conversation history (separada dos alunos)
CREATE TABLE IF NOT EXISTS sdr_conversation_history (
    id          BIGSERIAL PRIMARY KEY,
    phone       TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sdr_conv_phone_created
    ON sdr_conversation_history (phone, created_at DESC);

-- Demo calls agendadas
CREATE TABLE IF NOT EXISTS sdr_demo_calls (
    id              BIGSERIAL PRIMARY KEY,
    phone           TEXT NOT NULL,
    preferred_date  TEXT,
    notes           TEXT,
    status          TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'no_show', 'cancelled')),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Follow-ups agendados
CREATE TABLE IF NOT EXISTS sdr_followups (
    id          BIGSERIAL PRIMARY KEY,
    phone       TEXT NOT NULL,
    days        INTEGER NOT NULL DEFAULT 1,
    note        TEXT,
    status      TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
    fire_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Trigger para calcular fire_at automaticamente
CREATE OR REPLACE FUNCTION set_followup_fire_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fire_at := NEW.created_at + (NEW.days || ' days')::INTERVAL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_followup_fire_at ON sdr_followups;
CREATE TRIGGER trg_set_followup_fire_at
    BEFORE INSERT ON sdr_followups
    FOR EACH ROW
    EXECUTE FUNCTION set_followup_fire_at();

-- Updated_at trigger para sdr_leads
CREATE OR REPLACE FUNCTION update_sdr_leads_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sdr_leads_updated_at ON sdr_leads;
CREATE TRIGGER trg_sdr_leads_updated_at
    BEFORE UPDATE ON sdr_leads
    FOR EACH ROW
    EXECUTE FUNCTION update_sdr_leads_updated_at();
