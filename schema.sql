-- Represents JWTs that have been revoked.
CREATE TABLE IF NOT EXISTS jwt_blocklist (
    jti TEXT PRIMARY KEY,
    revoked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Stores information about workouts shared publicly.
CREATE TABLE IF NOT EXISTS shared_workouts (
    id UUID PRIMARY KEY,
    workout_id UUID NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    slug CHAR(10) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Represents user accounts and their associated information.
-- Assuming the users table is created elsewhere, these are alterations.
-- If this schema.sql is used for initial setup, a full CREATE TABLE users would be here.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS rir_bias_lr NUMERIC(4,3) NOT NULL DEFAULT 0.100,
    ADD COLUMN IF NOT EXISTS rir_bias_error_ema NUMERIC(6,3) NOT NULL DEFAULT 0.000;

-- Assuming the workouts table is created elsewhere, this is an alteration.
ALTER TABLE workouts
    ADD COLUMN IF NOT EXISTS hrv_ms NUMERIC(6,1) NULL;

-- Placeholder for the actual CREATE TABLE users statement if it were to be managed here.
-- For the purpose of this task, we are adding columns to an assumed existing 'users' table.
-- If 'users' table is defined in this file for a fresh setup, it should be like:
/*
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    birth_date DATE,
    gender TEXT,
    unit_system TEXT NOT NULL DEFAULT 'metric', -- 'metric' or 'imperial'
    experience_level TEXT NOT NULL DEFAULT 'beginner', -- 'beginner', 'intermediate', 'advanced'
    goal_slider REAL NOT NULL DEFAULT 0.5, -- 0 (strength) to 1 (hypertrophy)
    available_plates JSONB, -- e.g., {"kg": [25,20,10,5,2.5,1.25], "lb": [45,35,25,10,5,2.5]}

    -- RIR Bias fields
    rir_bias NUMERIC(4,3) NOT NULL DEFAULT 0.0, -- Existing field, assuming it's (4,3) or similar
    rir_bias_lr NUMERIC(4,3) NOT NULL DEFAULT 0.100, -- Learning rate for RIR bias
    rir_bias_error_ema NUMERIC(6,3) NOT NULL DEFAULT 0.000, -- Exponential Moving Average of RIR bias error

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workouts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_day_id UUID NULL REFERENCES plan_days(id) ON DELETE SET NULL, -- Assuming plan_days table
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE NULL,
    fatigue_level NUMERIC(3,1) NULL, -- e.g., 7.5
    sleep_hours NUMERIC(4,2) NULL, -- e.g., 7.75
    stress_level NUMERIC(3,1) NULL, -- e.g., 6.0
    hrv_ms NUMERIC(6,1) NULL, -- Heart Rate Variability in milliseconds
    notes TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
*/
