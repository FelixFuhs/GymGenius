CREATE TABLE IF NOT EXISTS volume_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week DATE NOT NULL,
    muscle_group VARCHAR(50) NOT NULL,
    total_volume DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_volume_summaries_user_week ON volume_summaries(user_id, week);
