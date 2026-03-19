-- ============================================
-- English Pronunciation Assistant
-- Schema inicial para Supabase
-- ============================================

-- Tabela principal: usuarios e sessao ativa
CREATE TABLE users (
    phone           TEXT PRIMARY KEY,
    -- sessao ativa (reference_text NULL = sem sessao)
    reference_text  TEXT,
    attempt_number  INTEGER NOT NULL DEFAULT 0,
    previous_scores DOUBLE PRECISION[] NOT NULL DEFAULT '{}',
    -- controle de frases
    phrase_focus     TEXT NOT NULL DEFAULT 'general',
    phrase_index     INTEGER NOT NULL DEFAULT 0,
    -- preferencias
    level            TEXT NOT NULL DEFAULT 'intermediate',
    focus            TEXT NOT NULL DEFAULT 'general',
    -- timestamps
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Historico de tentativas (progresso de longo prazo)
CREATE TABLE session_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           TEXT NOT NULL REFERENCES users(phone),
    reference_text  TEXT NOT NULL,
    score           DOUBLE PRECISION NOT NULL,
    attempt_number  INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_session_history_phone ON session_history(phone);
CREATE INDEX idx_session_history_created ON session_history(created_at);

-- Funcao para stats de longo prazo (chamada via RPC)
CREATE OR REPLACE FUNCTION get_user_lifetime_stats(user_phone TEXT)
RETURNS TABLE(total BIGINT, avg_score DOUBLE PRECISION, best_score DOUBLE PRECISION)
LANGUAGE sql STABLE
AS $$
    SELECT
        count(*)::BIGINT AS total,
        coalesce(avg(score), 0) AS avg_score,
        coalesce(max(score), 0) AS best_score
    FROM session_history
    WHERE phone = user_phone;
$$;
