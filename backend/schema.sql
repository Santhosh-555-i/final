-- EventLens Database Schema for Supabase (PostgreSQL + pgvector)

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Events Table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    event_code VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    is_protected BOOLEAN DEFAULT FALSE,
    drive_link TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_code ON events(event_code);

-- 2. Photos Table
CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    thumbnail_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_photos_event_id ON photos(event_id);

-- 3. Face Embeddings Table
CREATE TABLE IF NOT EXISTS face_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    embedding vector(512) NOT NULL,
    bounding_box JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_face_embeddings_event_id ON face_embeddings(event_id);

-- Cosine Distance HNSW Index for ultra-fast vector search
CREATE INDEX IF NOT EXISTS idx_face_embeddings_vector 
ON face_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- RPC Function for Cosine Similarity Search
CREATE OR REPLACE FUNCTION match_face_embeddings(
    target_event_id UUID,
    query_embedding vector(512),
    match_threshold FLOAT DEFAULT 0.55,
    match_count INT DEFAULT 50
)
RETURNS TABLE (
    photo_id UUID,
    similarity FLOAT,
    bounding_box JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        fe.photo_id,
        1 - (fe.embedding <=> query_embedding) AS similarity,
        fe.bounding_box
    FROM face_embeddings fe
    WHERE fe.event_id = target_event_id
      AND 1 - (fe.embedding <=> query_embedding) >= match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;
