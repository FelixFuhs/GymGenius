import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json

# Placeholder for database connection details
DB_NAME = "projectvision"
DB_USER = "user"
DB_PASSWORD = "password"
DB_HOST = "localhost"
DB_PORT = "5432"

# Exercise data to be seeded
# Note: This data assumes the 'exercises' table has been updated to include:
# category VARCHAR(100), equipment VARCHAR(100), difficulty VARCHAR(50),
# primary_muscles JSONB, secondary_muscles JSONB, fatigue_rating VARCHAR(50),
# technique_notes TEXT, common_mistakes TEXT[], video_url VARCHAR(255), is_public BOOLEAN
EXERCISES_DATA = [
    {
        "name": "Barbell Bench Press",
        "category": "push",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "primary_muscles": {"chest": 1.0, "triceps": 0.6, "front_deltoids": 0.5},
        "secondary_muscles": {"side_deltoids": 0.2, "biceps_short_head": 0.1},
        "fatigue_rating": "high",
        "technique_notes": "Lie flat on a bench, grip the barbell slightly wider than shoulder-width. Lower the bar to your mid-chest and push back up.",
        "common_mistakes": ["Flaring elbows too much", "Bouncing the bar off the chest", "Not retracting scapula"],
        "video_url": "https://example.com/video/benchpress",
        "is_public": True,
    },
    {
        "name": "Barbell Squat",
        "category": "squat",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "primary_muscles": {"quadriceps": 1.0, "glutes": 0.8, "adductors": 0.5},
        "secondary_muscles": {"hamstrings": 0.4, "calves": 0.2, "lower_back": 0.3},
        "fatigue_rating": "high",
        "technique_notes": "Place the barbell on your upper back. Squat down until your hips are parallel to or below your knees, keeping your chest up and back straight.",
        "common_mistakes": ["Knees caving in", "Rounding the lower back", "Not squatting deep enough"],
        "video_url": "https://example.com/video/squat",
        "is_public": True,
    },
    {
        "name": "Deadlift",
        "category": "hinge",
        "equipment": "barbell",
        "difficulty": "advanced",
        "primary_muscles": {"hamstrings": 1.0, "glutes": 1.0, "lower_back": 0.8, "traps": 0.7},
        "secondary_muscles": {"quadriceps": 0.5, "forearms": 0.6, "lats": 0.4},
        "fatigue_rating": "high",
        "technique_notes": "Stand with mid-foot under the barbell. Hinge at the hips with a flat back, grip the bar. Lift by extending hips and knees.",
        "common_mistakes": ["Rounding the back", "Jerking the weight up", "Hips shooting up too fast"],
        "video_url": "https://example.com/video/deadlift",
        "is_public": True,
    },
    {
        "name": "Overhead Press",
        "category": "push",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "primary_muscles": {"front_deltoids": 1.0, "side_deltoids": 0.7, "triceps": 0.6},
        "secondary_muscles": {"upper_chest": 0.3, "traps": 0.4, "core": 0.5},
        "fatigue_rating": "medium",
        "technique_notes": "Start with the barbell at shoulder height. Press the bar overhead until arms are fully extended. Keep core tight.",
        "common_mistakes": ["Leaning back too much", "Using leg drive (unless push press)", "Not controlling the descent"],
        "video_url": "https://example.com/video/ohp",
        "is_public": True,
    },
    {
        "name": "Pull-ups",
        "category": "pull",
        "equipment": "bodyweight",
        "difficulty": "intermediate",
        "primary_muscles": {"lats": 1.0, "biceps_long_head": 0.7, "rhomboids": 0.6},
        "secondary_muscles": {"forearms": 0.5, "rear_deltoids": 0.4, "traps_lower": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Hang from a pull-up bar with an overhand grip. Pull your body up until your chin is over the bar. Lower with control.",
        "common_mistakes": ["Using momentum (kipping)", "Not achieving full range of motion", "Shoulders shrugging up"],
        "video_url": "https://example.com/video/pullups",
        "is_public": True,
    },
    {
        "name": "Dumbbell Rows",
        "category": "pull",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"lats": 0.9, "rhomboids": 0.7, "mid_traps": 0.6},
        "secondary_muscles": {"biceps": 0.5, "rear_deltoids": 0.4, "forearms": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Support one knee and hand on a bench. Hold a dumbbell in the other hand, arm extended. Pull the dumbbell towards your hip, squeezing your back.",
        "common_mistakes": ["Rounding the back", "Using too much bicep", "Twisting the torso"],
        "video_url": "https://example.com/video/dbrows",
        "is_public": True,
    },
    {
        "name": "Lunges",
        "category": "squat", # Could also be unilateral or other categories depending on system
        "equipment": "bodyweight", # Can be done with dumbbells/barbell too
        "difficulty": "beginner",
        "primary_muscles": {"quadriceps": 0.9, "glutes": 0.8},
        "secondary_muscles": {"hamstrings": 0.5, "calves": 0.2, "adductors": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Step forward with one leg, lowering your hips until both knees are bent at a 90-degree angle. Push back to the starting position.",
        "common_mistakes": ["Front knee going past the toe", "Not keeping torso upright", "Pushing off the back foot too much"],
        "video_url": "https://example.com/video/lunges",
        "is_public": True,
    },
    {
        "name": "Bicep Curls",
        "category": "isolation",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"biceps_brachii": 1.0},
        "secondary_muscles": {"brachialis": 0.5, "forearm_flexors": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Stand or sit holding dumbbells with an underhand grip. Curl the weights up towards your shoulders, keeping elbows stable. Lower with control.",
        "common_mistakes": ["Swinging the body", "Elbows moving forward/backward too much", "Not using full range of motion"],
        "video_url": "https://example.com/video/bicepcurls",
        "is_public": True,
    },
    {
        "name": "Triceps Pushdowns",
        "category": "isolation",
        "equipment": "cable",
        "difficulty": "beginner",
        "primary_muscles": {"triceps_brachii": 1.0},
        "secondary_muscles": {"anconeus": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Attach a bar or rope to a high cable pulley. Grip the attachment, keep elbows close to your body, and extend your arms downwards.",
        "common_mistakes": ["Elbows flaring out", "Using shoulders to push down", "Partial range of motion"],
        "video_url": "https://example.com/video/tricepspushdowns",
        "is_public": True,
    },
    {
        "name": "Calf Raises",
        "category": "isolation",
        "equipment": "bodyweight", # Can be machine/dumbbell
        "difficulty": "beginner",
        "primary_muscles": {"gastrocnemius": 1.0, "soleus": 0.8},
        "secondary_muscles": {},
        "fatigue_rating": "low",
        "technique_notes": "Stand with the balls of your feet on an elevated surface. Lower your heels as far as comfortable, then push up onto your toes.",
        "common_mistakes": ["Bouncing", "Not using full range of motion", "Leaning forward too much"],
        "video_url": "https://example.com/video/calfraises",
        "is_public": True,
    },
    {
        "name": "Face Pulls",
        "category": "pull",
        "equipment": "cable",
        "difficulty": "beginner",
        "primary_muscles": {"rear_deltoids": 1.0, "rhomboids": 0.7, "mid_traps": 0.6},
        "secondary_muscles": {"rotator_cuff": 0.5},
        "fatigue_rating": "low",
        "technique_notes": "Set cable to chest height with a rope attachment. Pull the rope towards your face, aiming for external rotation at the shoulder. Squeeze shoulder blades.",
        "common_mistakes": ["Using too much weight", "Turning it into a row", "Not focusing on external rotation"],
        "video_url": "https://example.com/video/facepulls",
        "is_public": True,
    }
]

def seed_exercises():
    """Connects to the PostgreSQL database and seeds the exercises table."""
    conn = None
    inserted_count = 0
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        print(f"Successfully connected to database '{DB_NAME}' as user '{DB_USER}' for seeding.")

        with conn.cursor() as cur:
            # Insert data into the exercises table
            # This query assumes the table 'exercises' has the specified columns
            insert_query = sql.SQL("""
                INSERT INTO exercises (
                    name, category, equipment, difficulty, primary_muscles,
                    secondary_muscles, fatigue_rating, technique_notes,
                    common_mistakes, video_url, is_public
                ) VALUES (
                    %(name)s, %(category)s, %(equipment)s, %(difficulty)s, %(primary_muscles)s,
                    %(secondary_muscles)s, %(fatigue_rating)s, %(technique_notes)s,
                    %(common_mistakes)s, %(video_url)s, %(is_public)s
                ) ON CONFLICT (name) DO NOTHING;
            """)
            # ON CONFLICT (name) DO NOTHING ensures that if an exercise with the same name already exists, it's skipped.

            for exercise in EXERCISES_DATA:
                try:
                    cur.execute(insert_query, {
                        "name": exercise["name"],
                        "category": exercise["category"],
                        "equipment": exercise["equipment"],
                        "difficulty": exercise["difficulty"],
                        "primary_muscles": Json(exercise["primary_muscles"]), # Use Json adapter for JSONB
                        "secondary_muscles": Json(exercise["secondary_muscles"]), # Use Json adapter for JSONB
                        "fatigue_rating": exercise["fatigue_rating"],
                        "technique_notes": exercise["technique_notes"],
                        "common_mistakes": exercise["common_mistakes"], # psycopg2 handles Python list to TEXT[]
                        "video_url": exercise["video_url"],
                        "is_public": exercise["is_public"]
                    })
                    if cur.rowcount > 0:
                        inserted_count +=1
                except psycopg2.Error as e:
                    print(f"Error inserting exercise {exercise['name']}: {e}")
                    conn.rollback() # Rollback this specific transaction if problematic, or handle differently
                    # For this script, we might choose to continue with other exercises

        # Commit the changes
        conn.commit()
        if inserted_count > 0:
            print(f"Successfully inserted {inserted_count} new exercises into the 'exercises' table.")
        else:
            print("No new exercises were inserted. They might already exist in the table.")

    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        print("Please ensure PostgreSQL is running and connection details are correct.")
        print("Also, ensure the 'exercises' table schema matches the data structure in this script.")
    except psycopg2.Error as e:
        print(f"Error during database operation: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed after seeding.")

if __name__ == "__main__":
    print("Attempting to seed exercises data...")
    seed_exercises()
    print("Seeding script finished.")
"""
