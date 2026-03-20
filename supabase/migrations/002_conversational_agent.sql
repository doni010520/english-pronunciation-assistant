-- ============================================
-- English Pronunciation Assistant
-- Migration 002: Agente conversacional + RAG
-- ============================================

-- Habilitar pgvector para embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- Configurações do agente (singleton)
-- ============================================
CREATE TABLE agent_settings (
    id          INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    agent_name  TEXT NOT NULL DEFAULT 'Emma',
    personality TEXT NOT NULL DEFAULT 'friendly, patient, encouraging',
    system_prompt TEXT NOT NULL DEFAULT '',
    language    TEXT NOT NULL DEFAULT 'pt-BR',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO agent_settings (system_prompt) VALUES (
    'You are {agent_name}, an English pronunciation tutor for Brazilian Portuguese speakers.
Personality: {personality}

You help students practice English pronunciation via WhatsApp. You speak Portuguese with students but teach English pronunciation.

When the student wants to practice, use the give_practice_phrase tool.
When they ask about their progress, use the show_progress tool.
When they want to change difficulty, use the set_level tool.
When they want to focus on specific sounds, use the set_focus tool.

Be conversational, friendly, and encouraging. Keep messages short for WhatsApp (max 5 lines).
Never use slash commands. Act like a real human tutor.'
);

-- ============================================
-- Histórico de conversas por usuário
-- ============================================
CREATE TABLE conversation_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone       TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversation_history_phone ON conversation_history(phone);
CREATE INDEX idx_conversation_history_created ON conversation_history(created_at);

-- ============================================
-- Documentos de conhecimento (RAG)
-- ============================================
CREATE TABLE knowledge_documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename    TEXT NOT NULL,
    filetype    TEXT NOT NULL,
    file_size   INTEGER,
    chunk_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- Chunks com embeddings (RAG)
-- ============================================
CREATE TABLE knowledge_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding   vector(1536),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_knowledge_chunks_document ON knowledge_chunks(document_id);

-- ============================================
-- Função RPC para busca semântica
-- ============================================
CREATE OR REPLACE FUNCTION match_knowledge_chunks(
    query_embedding vector(1536),
    match_threshold DOUBLE PRECISION DEFAULT 0.7,
    match_count INTEGER DEFAULT 5
)
RETURNS TABLE(id UUID, content TEXT, similarity DOUBLE PRECISION, document_id UUID)
LANGUAGE sql STABLE
AS $$
    SELECT
        kc.id,
        kc.content,
        1 - (kc.embedding <=> query_embedding) AS similarity,
        kc.document_id
    FROM knowledge_chunks kc
    WHERE 1 - (kc.embedding <=> query_embedding) > match_threshold
    ORDER BY kc.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ============================================
-- Adicionar push_name na tabela users
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS push_name TEXT DEFAULT '';
