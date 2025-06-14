import psycopg2
from psycopg2 import sql

# Placeholder for database connection details
DB_NAME = "projectvision"
DB_USER = "user"
DB_PASSWORD = "password"
DB_HOST = "localhost"
DB_PORT = "5432"

# SQL commands to create tables and indexes
SQL_COMMANDS = """
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exercises (
    exercise_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    muscle_group VARCHAR(255),
    equipment VARCHAR(255),
    difficulty_level VARCHAR(50),
    media_url VARCHAR(255), -- URL to image or video
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workout_plans (
    plan_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    goal VARCHAR(255), -- e.g., strength, hypertrophy, endurance
    skill_level VARCHAR(50), -- e.g., beginner, intermediate, advanced
    duration_weeks INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plan_days (
    day_id SERIAL PRIMARY KEY,
    plan_id INTEGER REFERENCES workout_plans(plan_id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL, -- 1 for Monday, 7 for Sunday
    name VARCHAR(255), -- e.g., "Chest Day", "Leg Day"
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (plan_id, day_of_week)
);

CREATE TABLE IF NOT EXISTS plan_exercises (
    plan_exercise_id SERIAL PRIMARY KEY,
    day_id INTEGER REFERENCES plan_days(day_id) ON DELETE CASCADE,
    exercise_id INTEGER REFERENCES exercises(exercise_id) ON DELETE RESTRICT,
    sets INTEGER,
    reps_min INTEGER,
    reps_max INTEGER,
    rest_seconds INTEGER,
    notes TEXT,
    sequence_order INTEGER, -- Order of exercise within the day
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workouts (
    workout_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES workout_plans(plan_id) ON DELETE SET NULL, -- Can be null if not following a plan
    day_id INTEGER REFERENCES plan_days(day_id) ON DELETE SET NULL, -- Can be null if not tied to a specific plan day
    name VARCHAR(255), -- e.g., "Morning Lift"
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    notes TEXT, -- User's notes about the workout
    mood VARCHAR(50),
    perceived_exertion INTEGER, -- RPE scale 1-10
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workout_sets (
    set_id SERIAL PRIMARY KEY,
    workout_id INTEGER REFERENCES workouts(workout_id) ON DELETE CASCADE,
    plan_exercise_id INTEGER REFERENCES plan_exercises(plan_exercise_id) ON DELETE SET NULL, -- Link to planned exercise if any
    exercise_id INTEGER REFERENCES exercises(exercise_id) ON DELETE RESTRICT, -- Actual exercise performed
    sequence_order INTEGER, -- Order of the set in the workout for that exercise
    weight_kg NUMERIC(6,2),
    reps INTEGER,
    rest_seconds INTEGER,
    notes TEXT,
    set_type VARCHAR(50), -- e.g., warm-up, working, drop-set, failure
    perceived_exertion INTEGER, -- RPE for this specific set
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS estimated_1rm_history (
    e1rm_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    exercise_id INTEGER REFERENCES exercises(exercise_id) ON DELETE CASCADE,
    e1rm_value NUMERIC(7,2) NOT NULL,
    calculation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    workout_set_id INTEGER REFERENCES workout_sets(set_id) ON DELETE SET NULL, -- Optional: link to the set used for calculation
    formula_used VARCHAR(50), -- e.g., Epley, Brzycki
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, exercise_id, calculation_date)
);

CREATE TABLE IF NOT EXISTS muscle_recovery_patterns (
    recovery_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    muscle_group VARCHAR(255) NOT NULL,
    last_trained_date TIMESTAMP WITH TIME ZONE,
    estimated_recovery_days INTEGER,
    recovery_status VARCHAR(50), -- e.g., recovering, recovered, needs_attention
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, muscle_group)
);

CREATE TABLE IF NOT EXISTS plateau_events (
    plateau_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    exercise_id INTEGER REFERENCES exercises(exercise_id) ON DELETE CASCADE,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE, -- Null if plateau is ongoing
    description TEXT, -- e.g., "Stuck at 100kg bench for 3 weeks"
    potential_causes TEXT, -- e.g., "Overtraining, poor nutrition, lack of sleep"
    strategies_tried TEXT,
    status VARCHAR(50) DEFAULT 'active', -- e.g., active, resolved
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_workout_plans_user_id ON workout_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_plan_days_plan_id ON plan_days(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_exercises_day_id ON plan_exercises(day_id);
CREATE INDEX IF NOT EXISTS idx_plan_exercises_exercise_id ON plan_exercises(exercise_id);
CREATE INDEX IF NOT EXISTS idx_workouts_user_id ON workouts(user_id);
CREATE INDEX IF NOT EXISTS idx_workouts_plan_id ON workouts(plan_id);
CREATE INDEX IF NOT EXISTS idx_workouts_day_id ON workouts(day_id);
CREATE INDEX IF NOT EXISTS idx_workout_sets_workout_id ON workout_sets(workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise_id ON workout_sets(exercise_id);
CREATE INDEX IF NOT EXISTS idx_e1rm_history_user_id_exercise_id ON estimated_1rm_history(user_id, exercise_id);
CREATE INDEX IF NOT EXISTS idx_muscle_recovery_user_id_muscle_group ON muscle_recovery_patterns(user_id, muscle_group);
CREATE INDEX IF NOT EXISTS idx_plateau_events_user_id_exercise_id ON plateau_events(user_id, exercise_id);
"""

def create_schema():
    """Connects to the PostgreSQL database and creates the schema."""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        print(f"Successfully connected to database '{DB_NAME}' as user '{DB_USER}'.")

        with conn.cursor() as cur:
            # Execute the SQL commands
            cur.execute(SQL_COMMANDS)
            print("Schema creation commands executed.")

        # Commit the changes
        conn.commit()
        print("Schema created successfully (or already existed).")

    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        print("Please ensure PostgreSQL is running and connection details are correct.")
    except psycopg2.Error as e:
        print(f"Error during database operation: {e}")
        if conn:
            conn.rollback() # Rollback changes if any error occurs
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    print("Attempting to create database schema...")
    create_schema()
    print("Script finished.")
"""
