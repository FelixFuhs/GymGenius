import psycopg2
import os
import sys
from urllib.parse import urlparse # Add this import

# Database connection details
DATABASE_URL = os.getenv("DATABASE_URL")
DB_NAME_FALLBACK = os.getenv("POSTGRES_DB", "gymgenius")
DB_USER_FALLBACK = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD_FALLBACK = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST_FALLBACK = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT_FALLBACK = os.getenv("POSTGRES_PORT", "5432")

conn_params = {}
if DATABASE_URL:
    try:
        url = urlparse(DATABASE_URL)
        conn_params = {
            'dbname': url.path[1:],
            'user': url.username,
            'password': url.password,
            'host': url.hostname,
            'port': url.port
        }
        # Storing the connection method for logging
        _db_connection_method = f"DATABASE_URL to host '{url.hostname}'"
    except Exception as e:
        print(f"Warning: Could not parse DATABASE_URL ('{DATABASE_URL}'): {e}. Falling back to POSTGRES_* variables.")
        conn_params = { # Fallback to individual variables if DATABASE_URL parsing fails
            'dbname': DB_NAME_FALLBACK,
            'user': DB_USER_FALLBACK,
            'password': DB_PASSWORD_FALLBACK,
            'host': DB_HOST_FALLBACK,
            'port': DB_PORT_FALLBACK
        }
        _db_connection_method = f"POSTGRES_* variables to host '{DB_HOST_FALLBACK}'"
else:
    conn_params = {
        'dbname': DB_NAME_FALLBACK,
        'user': DB_USER_FALLBACK,
        'password': DB_PASSWORD_FALLBACK,
        'host': DB_HOST_FALLBACK,
        'port': DB_PORT_FALLBACK
    }
    _db_connection_method = f"POSTGRES_* variables to host '{DB_HOST_FALLBACK}'"


# SQL commands to create tables and indexes
SQL_COMMANDS = """
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    birth_date DATE,
    gender VARCHAR(20),
    sex TEXT, -- New column for sex
    equipment_type TEXT DEFAULT 'barbell', -- New column for equipment type
    goal_slider DECIMAL(3,2) DEFAULT 0.5,
    experience_level VARCHAR(20) DEFAULT 'intermediate',
    unit_system VARCHAR(10) DEFAULT 'metric',
    available_plates JSONB DEFAULT '{"kg": [1.25, 2.5, 5, 10, 20]}',
    rir_bias DECIMAL(3,1) DEFAULT 2.0,
    recovery_multipliers JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User Refresh Tokens Table
CREATE TABLE IF NOT EXISTS user_refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Exercises Table
CREATE TABLE IF NOT EXISTS exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(50),
    equipment VARCHAR(50),
    difficulty VARCHAR(20),
    primary_muscles JSONB NOT NULL,
    secondary_muscles JSONB,
    main_target_muscle_group VARCHAR(100), -- New column for fatigue endpoint simplification
    fatigue_rating VARCHAR(20),
    technique_notes TEXT,
    common_mistakes TEXT[],
    video_url VARCHAR(500),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Workout Plans Table
CREATE TABLE IF NOT EXISTS workout_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    days_per_week INTEGER,
    plan_length_weeks INTEGER,
    goal_focus DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Plan Days Table
CREATE TABLE IF NOT EXISTS plan_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES workout_plans(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    name VARCHAR(100),
    UNIQUE(plan_id, day_number)
);

-- Plan Exercises Table
CREATE TABLE IF NOT EXISTS plan_exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_day_id UUID REFERENCES plan_days(id) ON DELETE CASCADE,
    exercise_id UUID REFERENCES exercises(id) ON DELETE RESTRICT,
    order_index INTEGER NOT NULL,
    sets INTEGER NOT NULL,
    rep_range_low INTEGER,
    rep_range_high INTEGER,
    target_rir INTEGER,
    rest_seconds INTEGER,
    notes TEXT,
    UNIQUE(plan_day_id, order_index)
);

-- Plan Metrics Table to store aggregated plan volume and frequency
CREATE TABLE IF NOT EXISTS plan_metrics (
    plan_id UUID PRIMARY KEY REFERENCES workout_plans(id) ON DELETE CASCADE,
    total_volume INTEGER DEFAULT 0,
    muscle_group_frequency JSONB DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Workouts Table (Log of actual workout sessions)
CREATE TABLE IF NOT EXISTS workouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    plan_day_id UUID REFERENCES plan_days(id) ON DELETE SET NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    session_rpe INTEGER CHECK (session_rpe BETWEEN 1 AND 10),
    fatigue_level INTEGER CHECK (fatigue_level BETWEEN 1 AND 10),
    sleep_hours DECIMAL(3,1),
    stress_level INTEGER CHECK (stress_level BETWEEN 1 AND 10),
    notes TEXT
);

-- Workout Sets Table (Log of actual sets performed)
CREATE TABLE IF NOT EXISTS workout_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_id UUID REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_id UUID REFERENCES exercises(id) ON DELETE RESTRICT,
    set_number INTEGER NOT NULL,
    recommended_weight DECIMAL(7,2),
    recommended_reps INTEGER,
    recommended_rir INTEGER,
    confidence_score DECIMAL(3,2),
    actual_weight DECIMAL(7,2),
    actual_reps INTEGER,
    actual_rir INTEGER,
    rest_before_seconds INTEGER,
    completed_at TIMESTAMP WITH TIME ZONE,
    form_rating INTEGER CHECK (form_rating BETWEEN 1 AND 5),
    notes TEXT,
    mti INTEGER, -- New column for MTI
    UNIQUE(workout_id, exercise_id, set_number)
);

-- Mesocycles Table
CREATE TABLE IF NOT EXISTS mesocycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phase TEXT NOT NULL, -- e.g., 'accumulation', 'intensification', 'deload'
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    week_number INTEGER NOT NULL DEFAULT 1
);

-- Estimated 1RM History Table
CREATE TABLE IF NOT EXISTS estimated_1rm_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID REFERENCES exercises(id) ON DELETE CASCADE,
    estimated_1rm DECIMAL(7,2) NOT NULL,
    calculation_method VARCHAR(50),
    confidence DECIMAL(3,2),
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Muscle Recovery Patterns Table
CREATE TABLE IF NOT EXISTS muscle_recovery_patterns (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    muscle_group VARCHAR(50) NOT NULL,
    recovery_tau_hours DECIMAL(5,1),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, muscle_group)
);

-- Plateau Events Table
CREATE TABLE IF NOT EXISTS plateau_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    exercise_id UUID REFERENCES exercises(id) ON DELETE CASCADE,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    plateau_duration_days INTEGER,
    protocol_applied VARCHAR(50),
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_exercises_created_by ON exercises(created_by);
-- idx_exercises_name is implicitly created by UNIQUE constraint on name
CREATE INDEX IF NOT EXISTS idx_workout_plans_user_id ON workout_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_plan_days_plan_id ON plan_days(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_exercises_plan_day_id ON plan_exercises(plan_day_id);
CREATE INDEX IF NOT EXISTS idx_plan_exercises_exercise_id ON plan_exercises(exercise_id);
CREATE INDEX IF NOT EXISTS idx_plan_metrics_plan_id ON plan_metrics(plan_id);
CREATE INDEX IF NOT EXISTS idx_workouts_user_id_started_at ON workouts(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workout_sets_workout_id ON workout_sets(workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise_id_completed_at ON workout_sets(exercise_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_1rm_history_user_exercise_date ON estimated_1rm_history(user_id, exercise_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_muscle_recovery_user_muscle_group ON muscle_recovery_patterns(user_id, muscle_group);
CREATE INDEX IF NOT EXISTS idx_plateau_events_user_exercise ON plateau_events(user_id, exercise_id);
CREATE INDEX IF NOT EXISTS idx_exercises_main_target_muscle_group ON exercises(main_target_muscle_group); -- Index for the new column
CREATE INDEX IF NOT EXISTS idx_user_refresh_tokens_user_id ON user_refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_user_refresh_tokens_token ON user_refresh_tokens(token); -- Explicit index for the unique token
CREATE INDEX IF NOT EXISTS idx_mesocycles_user_id_start_date ON mesocycles(user_id, start_date DESC); -- Index for mesocycles table

-- Trigger function to update 'updated_at' columns
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with 'updated_at'
CREATE TRIGGER set_timestamp_users
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

CREATE TRIGGER set_timestamp_workout_plans
BEFORE UPDATE ON workout_plans
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

CREATE TRIGGER set_timestamp_plan_metrics
BEFORE UPDATE ON plan_metrics
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();
"""

def create_schema():
    conn = None
    try:
        # Use the globally defined conn_params
        print(f"Attempting to connect using {_db_connection_method}.")
        conn = psycopg2.connect(**conn_params)
        # Use conn_params to report which database and host we connected to
        print(f"Successfully connected to database '{conn_params.get('dbname')}' on host '{conn_params.get('host')}'.")
        with conn.cursor() as cur:
            cur.execute(SQL_COMMANDS)
            print("Schema creation commands executed.")
        conn.commit()
        print("Schema created successfully (or already existed).")
    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database using method '{_db_connection_method}': {e}")
        # Generic advice part
        print(f"Please ensure PostgreSQL is running and accessible, "
              f"and that the target database exists with appropriate permissions.")
        sys.exit(1)
    except psycopg2.Error as e:
        print(f"Error during database operation (using '{_db_connection_method}'): {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    print("Attempting to create/update database schema...")
    create_schema()
    print("Script finished.")
