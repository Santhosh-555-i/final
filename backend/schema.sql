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

-- 3. Person Clusters Table
CREATE TABLE IF NOT EXISTS person_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    thumbnail_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_person_clusters_event_id ON person_clusters(event_id);

-- 4. Face Embeddings Table
CREATE TABLE IF NOT EXISTS face_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    cluster_id UUID REFERENCES person_clusters(id) ON DELETE SET NULL,
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

-- 5. Share Tokens Table
CREATE TABLE IF NOT EXISTS share_tokens (
    token VARCHAR(255) PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    photo_ids_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_share_tokens_event_id ON share_tokens(event_id);

-- 6. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID,
    action VARCHAR(255) NOT NULL,
    details_json JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_event_id ON audit_logs(event_id);

-- 7. Event Settings Table
CREATE TABLE IF NOT EXISTS event_settings (
    event_id UUID PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    similarity_threshold FLOAT DEFAULT 0.35,
    retention_days INTEGER DEFAULT 90,
    selfie_search_enabled INTEGER DEFAULT 1,
    downloads_enabled INTEGER DEFAULT 1
);

-- 8. Sync Jobs Table
CREATE TABLE IF NOT EXISTS sync_jobs (
    id UUID PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Storage Bucket setup (Optional SQL initialization)
INSERT INTO storage.buckets (id, name, public) 
VALUES ('photos', 'photos', true) 
ON CONFLICT (id) DO NOTHING;

-- Allow public read access to photos bucket
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'Public Access Photos' AND tablename = 'objects'
    ) THEN
        CREATE POLICY "Public Access Photos" ON storage.objects FOR SELECT USING (bucket_id = 'photos');
    END IF;
END $$;
