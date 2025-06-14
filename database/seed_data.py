import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
import os
import sys

# Database connection details from environment variables
DB_NAME = os.getenv("POSTGRES_DB", "gymgenius")
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# Exercise data to be seeded
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
        "primary_muscles": {"hamstrings": 1.0, "glutes": 1.0, "lower_back": 0.8, "traps": 0.7}, # Multiple at 1.0
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
        "category": "squat",
        "equipment": "bodyweight",
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
        "equipment": "bodyweight",
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
    },
    {
        "name": "Incline Dumbbell Press",
        "category": "push",
        "equipment": "dumbbell",
        "difficulty": "intermediate",
        "primary_muscles": {"upper_chest": 1.0, "front_deltoids": 0.6, "triceps": 0.5},
        "secondary_muscles": {"side_deltoids": 0.2},
        "fatigue_rating": "medium",
        "technique_notes": "Lie on an incline bench (30-45 degrees). Press dumbbells up from chest level until arms are extended.",
        "common_mistakes": ["Flaring elbows too wide", "Not controlling the descent", "Bench angle too high (hits shoulders more)"],
        "video_url": "https://example.com/video/inclinedumbbellpress",
        "is_public": True,
    },
    {
        "name": "Decline Barbell Press",
        "category": "push",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "primary_muscles": {"lower_chest": 1.0, "triceps": 0.6, "front_deltoids": 0.3},
        "secondary_muscles": {},
        "fatigue_rating": "medium",
        "technique_notes": "Lie on a decline bench. Lower the barbell to your lower chest and press up.",
        "common_mistakes": ["Bouncing bar", "Too much arch", "Incorrect grip width"],
        "video_url": "https://example.com/video/declinebarbellpress",
        "is_public": True,
    },
    {
        "name": "Chest Dips",
        "category": "push",
        "equipment": "bodyweight",
        "difficulty": "intermediate",
        "primary_muscles": {"lower_chest": 0.9, "triceps": 0.7, "front_deltoids": 0.5},
        "secondary_muscles": {"core": 0.3},
        "fatigue_rating": "high",
        "technique_notes": "Lean forward slightly while performing dips on parallel bars to emphasize chest.",
        "common_mistakes": ["Not leaning forward (targets triceps more)", "Going too deep (shoulder impingement)", "Flaring elbows excessively"],
        "video_url": "https://example.com/video/chestdips",
        "is_public": True,
    },
    {
        "name": "Triceps Dips",
        "category": "push",
        "equipment": "bodyweight",
        "difficulty": "intermediate",
        "primary_muscles": {"triceps": 1.0, "front_deltoids": 0.4, "chest": 0.3},
        "secondary_muscles": {"core": 0.2},
        "fatigue_rating": "medium",
        "technique_notes": "Keep torso upright while performing dips on parallel bars or a bench to emphasize triceps.",
        "common_mistakes": ["Leaning forward too much (targets chest more)", "Shoulders rolling forward", "Not locking out"],
        "video_url": "https://example.com/video/tricepsdips",
        "is_public": True,
    },
    {
        "name": "Close-Grip Bench Press",
        "category": "push",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "primary_muscles": {"triceps": 1.0, "chest": 0.6, "front_deltoids": 0.4},
        "secondary_muscles": {},
        "fatigue_rating": "medium",
        "technique_notes": "Use a narrower grip (shoulder-width or slightly less). Lower bar to mid/lower chest. Keep elbows tucked.",
        "common_mistakes": ["Grip too narrow (wrist pain)", "Flaring elbows", "Bouncing bar"],
        "video_url": "https://example.com/video/closegripbench",
        "is_public": True,
    },
    {
        "name": "Push-ups",
        "category": "push",
        "equipment": "bodyweight",
        "difficulty": "beginner",
        "primary_muscles": {"chest": 0.8, "triceps": 0.6, "front_deltoids": 0.5, "core": 0.4},
        "secondary_muscles": {"serratus_anterior": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Hands shoulder-width apart, body straight. Lower chest towards floor, push back up.",
        "common_mistakes": ["Sagging hips", "Flaring elbows", "Head dropping"],
        "video_url": "https://example.com/video/pushups",
        "is_public": True,
    },
    {
        "name": "Lateral Raises",
        "category": "push", # Often debated, but involves pushing weight away from body laterally
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"side_deltoids": 1.0},
        "secondary_muscles": {"front_deltoids": 0.2, "rear_deltoids": 0.2, "traps": 0.1},
        "fatigue_rating": "low",
        "technique_notes": "Raise dumbbells out to the sides until arms are parallel to the floor. Slight bend in elbows.",
        "common_mistakes": ["Using momentum (swinging)", "Lifting too high (engages traps excessively)", "Elbows lower than wrists"],
        "video_url": "https://example.com/video/lateralraises",
        "is_public": True,
    },
    {
        "name": "Front Raises",
        "category": "push",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"front_deltoids": 1.0},
        "secondary_muscles": {"side_deltoids": 0.3, "upper_chest": 0.2},
        "fatigue_rating": "low",
        "technique_notes": "Raise dumbbells straight in front of you up to shoulder height.",
        "common_mistakes": ["Swinging the weight", "Leaning back", "Going above shoulder height"],
        "video_url": "https://example.com/video/frontraises",
        "is_public": True,
    },
    {
        "name": "Bent-Over Dumbbell Rows",
        "category": "pull",
        "equipment": "dumbbell",
        "difficulty": "intermediate",
        "primary_muscles": {"lats": 0.8, "rhomboids": 0.7, "mid_traps": 0.7, "rear_deltoids": 0.5},
        "secondary_muscles": {"biceps": 0.4, "lower_back": 0.3, "forearms": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Hinge at hips, back flat. Pull dumbbells towards your lower rib cage / hips.",
        "common_mistakes": ["Rounding back", "Using too much biceps", "Standing too upright"],
        "video_url": "https://example.com/video/bentoverdbrows",
        "is_public": True,
    },
    {
        "name": "Barbell Rows",
        "category": "pull",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "primary_muscles": {"lats": 0.9, "rhomboids": 0.8, "mid_traps": 0.8, "spinal_erectors": 0.6},
        "secondary_muscles": {"biceps": 0.5, "rear_deltoids": 0.4, "forearms": 0.4},
        "fatigue_rating": "high",
        "technique_notes": "Hinge at hips (around 45-degree angle), back flat. Pull barbell to lower chest / upper abdomen.",
        "common_mistakes": ["Rounding back (Pendlay row is an exception for starting position)", "Using too much momentum (body English)", "Pulling too high (to upper chest)"],
        "video_url": "https://example.com/video/barbellrows",
        "is_public": True,
    },
    {
        "name": "T-Bar Rows",
        "category": "pull",
        "equipment": "t-bar_row_machine", # or landmine setup
        "difficulty": "intermediate",
        "primary_muscles": {"mid_back": 1.0, "lats": 0.8, "rhomboids": 0.7}, # mid_back can be mix of traps/rhomboids
        "secondary_muscles": {"biceps": 0.5, "lower_back": 0.4, "rear_deltoids": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Keep back flat, chest up. Pull handles towards your chest, squeezing shoulder blades.",
        "common_mistakes": ["Rounding back", "Jerking the weight", "Not getting full stretch"],
        "video_url": "https://example.com/video/tbarrows",
        "is_public": True,
    },
    {
        "name": "Seated Cable Rows",
        "category": "pull",
        "equipment": "cable",
        "difficulty": "beginner",
        "primary_muscles": {"lats": 0.8, "rhomboids": 0.7, "mid_traps": 0.7},
        "secondary_muscles": {"biceps": 0.5, "rear_deltoids": 0.3, "forearms": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Sit with feet braced, back straight. Pull handle towards your abdomen, retracting scapula.",
        "common_mistakes": ["Leaning back excessively", "Rounding shoulders forward", "Using too much arm pull"],
        "video_url": "https://example.com/video/seatedcablerows",
        "is_public": True,
    },
    {
        "name": "Lat Pulldowns",
        "category": "pull",
        "equipment": "cable", # or lat pulldown machine
        "difficulty": "beginner",
        "primary_muscles": {"lats": 1.0, "biceps": 0.5, "rhomboids": 0.4},
        "secondary_muscles": {"rear_deltoids": 0.3, "mid_traps": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Grip bar wider than shoulder-width. Pull bar down to upper chest, squeezing lats.",
        "common_mistakes": ["Using momentum", "Leaning back too far", "Not controlling the eccentric"],
        "video_url": "https://example.com/video/latpulldowns",
        "is_public": True,
    },
    {
        "name": "Romanian Deadlifts (RDLs)",
        "category": "hinge",
        "equipment": "barbell", # or dumbbell
        "difficulty": "intermediate",
        "primary_muscles": {"hamstrings": 1.0, "glutes": 0.7, "spinal_erectors": 0.5},
        "secondary_muscles": {"traps": 0.3, "forearms": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Start from top (standing). Hinge at hips, keeping legs mostly straight (slight knee bend). Lower weight along legs until stretch in hamstrings, then return up.",
        "common_mistakes": ["Rounding back", "Bending knees too much (becomes a squat)", "Bar drifting away from legs"],
        "video_url": "https://example.com/video/rdls",
        "is_public": True,
    },
    {
        "name": "Good Mornings",
        "category": "hinge",
        "equipment": "barbell",
        "difficulty": "advanced",
        "primary_muscles": {"hamstrings": 0.9, "glutes": 0.6, "spinal_erectors": 0.8},
        "secondary_muscles": {"core": 0.4},
        "fatigue_rating": "medium",
        "technique_notes": "Bar on back like a squat. Hinge at hips, keeping back flat and slight knee bend. Lower torso towards parallel with floor.",
        "common_mistakes": ["Rounding back (very dangerous)", "Too much weight", "Knees too bent"],
        "video_url": "https://example.com/video/goodmornings",
        "is_public": True,
    },
    {
        "name": "Leg Press",
        "category": "squat", # compound leg movement
        "equipment": "leg_press_machine",
        "difficulty": "beginner",
        "primary_muscles": {"quadriceps": 1.0, "glutes": 0.7, "hamstrings": 0.4}, # Varies with foot position
        "secondary_muscles": {"adductors": 0.3, "calves": 0.1},
        "fatigue_rating": "medium",
        "technique_notes": "Place feet shoulder-width apart on platform. Lower weight until knees are around 90 degrees, push back up.",
        "common_mistakes": ["Rounding lower back (lifting hips off seat)", "Not using full range of motion", "Knees caving in"],
        "video_url": "https://example.com/video/legpress",
        "is_public": True,
    },
    {
        "name": "Hack Squats",
        "category": "squat",
        "equipment": "hack_squat_machine",
        "difficulty": "intermediate",
        "primary_muscles": {"quadriceps": 1.0, "glutes": 0.6}, # Often emphasizes quads
        "secondary_muscles": {"hamstrings": 0.3, "adductors": 0.2},
        "fatigue_rating": "high",
        "technique_notes": "Shoulders under pads, back against support. Squat down until thighs are parallel or below.",
        "common_mistakes": ["Knees tracking inward", "Not going deep enough", "Lifting heels"],
        "video_url": "https://example.com/video/hacksquats",
        "is_public": True,
    },
    {
        "name": "Front Squats",
        "category": "squat",
        "equipment": "barbell",
        "difficulty": "advanced",
        "primary_muscles": {"quadriceps": 1.0, "glutes": 0.7, "upper_back": 0.6, "core": 0.5},
        "secondary_muscles": {"hamstrings": 0.3, "adductors": 0.3},
        "fatigue_rating": "high",
        "technique_notes": "Bar rests on front deltoids, either cross-grip or clean grip. Keep elbows high, torso upright.",
        "common_mistakes": ["Elbows dropping (bar falls)", "Rounding upper back", "Not hitting depth"],
        "video_url": "https://example.com/video/frontsquats",
        "is_public": True,
    },
    {
        "name": "Bulgarian Split Squats",
        "category": "squat", # Unilateral
        "equipment": "dumbbell", # or barbell, bodyweight
        "difficulty": "intermediate",
        "primary_muscles": {"quadriceps": 0.9, "glutes": 0.9}, # Can be biased by torso lean/foot position
        "secondary_muscles": {"hamstrings": 0.4, "adductors": 0.3, "core_stability": 0.5},
        "fatigue_rating": "medium",
        "technique_notes": "Rear foot elevated on a bench. Lower until front thigh is near parallel to floor.",
        "common_mistakes": ["Front knee caving in", "Too much weight/loss of balance", "Pushing off back foot excessively"],
        "video_url": "https://example.com/video/bulgariansplitsquats",
        "is_public": True,
    },
    {
        "name": "Leg Extensions",
        "category": "isolation",
        "equipment": "leg_extension_machine",
        "difficulty": "beginner",
        "primary_muscles": {"quadriceps": 1.0},
        "secondary_muscles": {},
        "fatigue_rating": "low",
        "technique_notes": "Sit with shins under pad. Extend legs until straight, squeezing quads.",
        "common_mistakes": ["Using momentum", "Not controlling eccentric", "Hyperextending knees (for some)"],
        "video_url": "https://example.com/video/legextensions",
        "is_public": True,
    },
    {
        "name": "Leg Curls (Lying or Seated)",
        "category": "isolation",
        "equipment": "leg_curl_machine",
        "difficulty": "beginner",
        "primary_muscles": {"hamstrings": 1.0},
        "secondary_muscles": {"gastrocnemius": 0.2}, # esp. with plantarflexion
        "fatigue_rating": "low",
        "technique_notes": "Position self so knee joint aligns with machine pivot. Curl weight towards glutes.",
        "common_mistakes": ["Hips lifting off pad (lying)", "Not full range of motion", "Jerking the weight"],
        "video_url": "https://example.com/video/legcurls",
        "is_public": True,
    },
    {
        "name": "Glute Bridges / Hip Thrusts",
        "category": "hinge", # Hip extension dominant
        "equipment": "barbell", # or bodyweight, dumbbell
        "difficulty": "beginner", # bodyweight bridge
        "primary_muscles": {"glutes": 1.0, "hamstrings": 0.4},
        "secondary_muscles": {"lower_back": 0.2, "core": 0.3},
        "fatigue_rating": "medium", # with barbell
        "technique_notes": "Back on bench (hip thrust) or floor (bridge). Drive hips up by squeezing glutes until body forms straight line from shoulders to knees.",
        "common_mistakes": ["Hyperextending lower back", "Not achieving full hip extension", "Neck position (keep neutral or chin tucked slightly)"],
        "video_url": "https://example.com/video/hipthrusts",
        "is_public": True,
    },
    {
        "name": "Skullcrushers (Lying Triceps Extensions)",
        "category": "isolation",
        "equipment": "barbell", # EZ bar or dumbbells
        "difficulty": "intermediate",
        "primary_muscles": {"triceps": 1.0},
        "secondary_muscles": {"anconeus": 0.4},
        "fatigue_rating": "low",
        "technique_notes": "Lie on bench. Lower bar towards forehead/behind head by bending elbows. Extend back up.",
        "common_mistakes": ["Elbows flaring out excessively", "Using shoulders", "Not controlling eccentric (hitting head!)"],
        "video_url": "https://example.com/video/skullcrushers",
        "is_public": True,
    },
    {
        "name": "Overhead Dumbbell Triceps Extension",
        "category": "isolation",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"triceps_long_head": 1.0, "triceps_medial_lateral": 0.7},
        "secondary_muscles": {},
        "fatigue_rating": "low",
        "technique_notes": "Hold one dumbbell with both hands (or one in each hand). Extend overhead, lower behind head by bending elbows.",
        "common_mistakes": ["Elbows flaring wide", "Not getting full stretch", "Shoulder impingement if form is poor"],
        "video_url": "https://example.com/video/overheadtricepext",
        "is_public": True,
    },
    {
        "name": "Hammer Curls",
        "category": "isolation",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"brachialis": 0.8, "biceps_brachii": 0.6, "brachioradialis": 0.7}, # Targets brachialis and brachioradialis more
        "secondary_muscles": {"forearm_flexors": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Hold dumbbells with palms facing each other (neutral grip). Curl up, keeping palms neutral.",
        "common_mistakes": ["Swinging", "Palms supinating (turning up)", "Elbows moving too much"],
        "video_url": "https://example.com/video/hammercurls",
        "is_public": True,
    },
    {
        "name": "Concentration Curls",
        "category": "isolation",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "primary_muscles": {"biceps_brachii_peak": 1.0}, # Often cited for peak contraction
        "secondary_muscles": {"brachialis": 0.4},
        "fatigue_rating": "low",
        "technique_notes": "Sit with elbow braced against inner thigh. Curl dumbbell up towards shoulder, focusing on bicep contraction.",
        "common_mistakes": ["Lifting elbow off thigh", "Swinging body", "Not focusing on squeeze"],
        "video_url": "https://example.com/video/concentrationcurls",
        "is_public": True,
    },
    {
        "name": "Reverse Curls",
        "category": "isolation",
        "equipment": "barbell", # or EZ bar, dumbbells
        "difficulty": "intermediate",
        "primary_muscles": {"brachioradialis": 0.9, "brachialis": 0.7, "forearm_extensors": 0.5},
        "secondary_muscles": {"biceps": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Use an overhand grip (pronated). Curl bar up towards shoulders.",
        "common_mistakes": ["Wrists breaking (flexing/extending excessively)", "Too much weight", "Using momentum"],
        "video_url": "https://example.com/video/reversecurls",
        "is_public": True,
    },
    {
        "name": "Wrist Curls",
        "category": "isolation",
        "equipment": "dumbbell", # or barbell
        "difficulty": "beginner",
        "primary_muscles": {"forearm_flexors": 1.0},
        "secondary_muscles": {},
        "fatigue_rating": "very_low",
        "technique_notes": "Rest forearms on bench or thighs, palms up. Curl wrists up.",
        "common_mistakes": ["Using too much arm movement", "Not isolating wrists", "Too much weight"],
        "video_url": "https://example.com/video/wristcurls",
        "is_public": True,
    },
    {
        "name": "Reverse Wrist Curls",
        "category": "isolation",
        "equipment": "dumbbell", # or barbell
        "difficulty": "beginner",
        "primary_muscles": {"forearm_extensors": 1.0},
        "secondary_muscles": {},
        "fatigue_rating": "very_low",
        "technique_notes": "Rest forearms on bench or thighs, palms down. Extend wrists up.",
        "common_mistakes": ["Using too much arm movement", "Not isolating wrists", "Too much weight"],
        "video_url": "https://example.com/video/reversewristcurls",
        "is_public": True,
    },
    {
        "name": "Plank",
        "category": "core",
        "equipment": "bodyweight",
        "difficulty": "beginner",
        "primary_muscles": {"rectus_abdominis": 0.8, "transverse_abdominis": 1.0, "obliques": 0.6},
        "secondary_muscles": {"glutes": 0.3, "quads": 0.2, "spinal_erectors": 0.2},
        "fatigue_rating": "low", # per set, can be high if held long
        "technique_notes": "Hold body in a straight line from head to heels, supported on forearms and toes. Engage core.",
        "common_mistakes": ["Hips sagging", "Hips too high", "Holding breath"],
        "video_url": "https://example.com/video/plank",
        "is_public": True,
    },
    {
        "name": "Crunches",
        "category": "core",
        "equipment": "bodyweight",
        "difficulty": "beginner",
        "primary_muscles": {"rectus_abdominis": 1.0},
        "secondary_muscles": {"obliques": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Lie on back, knees bent. Curl upper body towards knees by contracting abs. Lower back remains on floor.",
        "common_mistakes": ["Pulling on neck", "Lifting lower back too much", "Using momentum"],
        "video_url": "https://example.com/video/crunches",
        "is_public": True,
    },
    {
        "name": "Russian Twists",
        "category": "core",
        "equipment": "bodyweight", # or medicine_ball, plate
        "difficulty": "beginner",
        "primary_muscles": {"obliques": 1.0, "rectus_abdominis": 0.5},
        "secondary_muscles": {"hip_flexors": 0.3, "lower_back_stabilizers": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Sit leaning back slightly, feet off floor (optional). Twist torso from side to side.",
        "common_mistakes": ["Moving only arms, not torso", "Rounding back", "Too fast/jerky"],
        "video_url": "https://example.com/video/russiantwists",
        "is_public": True,
    },
    {
        "name": "Leg Raises (Lying or Hanging)",
        "category": "core",
        "equipment": "bodyweight", # or dip_station for hanging
        "difficulty": "intermediate",
        "primary_muscles": {"lower_abdominals": 1.0, "hip_flexors": 0.7}, # Lower abs is part of rectus abdominis
        "secondary_muscles": {"obliques": 0.3},
        "fatigue_rating": "medium",
        "technique_notes": "Lie flat or hang from bar. Raise legs towards ceiling (or parallel for hanging), keeping them straight or slightly bent. Control descent.",
        "common_mistakes": ["Lower back arching excessively (lying)", "Swinging (hanging)", "Using momentum"],
        "video_url": "https://example.com/video/legraises",
        "is_public": True,
    },
    {
        "name": "Cable Woodchoppers",
        "category": "core",
        "equipment": "cable",
        "difficulty": "intermediate",
        "primary_muscles": {"obliques": 1.0, "rectus_abdominis": 0.5, "serratus_anterior": 0.4},
        "secondary_muscles": {"shoulders": 0.3, "glutes_stabilizers": 0.3},
        "fatigue_rating": "low",
        "technique_notes": "Stand sideways to cable machine. Pull handle diagonally across body (high-to-low or low-to-high). Pivot feet, rotate torso.",
        "common_mistakes": ["Using arms only", "Not enough rotation", "Too much weight"],
        "video_url": "https://example.com/video/cablewoodchoppers",
        "is_public": True,
    },
    {
        "name": "Shrugs",
        "category": "isolation", # Or accessory pull
        "equipment": "barbell", # or dumbbell, machine
        "difficulty": "beginner",
        "primary_muscles": {"upper_traps": 1.0, "mid_traps": 0.3},
        "secondary_muscles": {"levator_scapulae": 0.4, "forearms": 0.2},
        "fatigue_rating": "low",
        "technique_notes": "Hold weight(s) at sides. Elevate shoulders straight up towards ears. Squeeze at top, lower slowly.",
        "common_mistakes": ["Rolling shoulders forward/backward", "Using biceps", "Not full range of motion"],
        "video_url": "https://example.com/video/shrugs",
        "is_public": True,
    },
    {
        "name": "Seated Calf Raises",
        "category": "isolation",
        "equipment": "seated_calf_raise_machine", # or dumbbell on knees
        "difficulty": "beginner",
        "primary_muscles": {"soleus": 1.0}, # Primarily targets soleus due to knee flexion
        "secondary_muscles": {"gastrocnemius": 0.2},
        "fatigue_rating": "low",
        "technique_notes": "Sit with knees bent at 90 degrees, pads on thighs. Push up with balls of feet.",
        "common_mistakes": ["Bouncing", "Partial reps", "Too much weight limiting ROM"],
        "video_url": "https://example.com/video/seatedcalfraises",
        "is_public": True,
    },
    {
        "name": "Farmer's Walk",
        "category": "loaded_carry", # Could be considered full body / core / grip
        "equipment": "dumbbell", # or kettlebell, farmer_walk_handles
        "difficulty": "intermediate",
        "primary_muscles": {"forearms_grip": 1.0, "traps": 0.8, "core_stabilizers": 0.7, "shoulders_stabilizers": 0.6},
        "secondary_muscles": {"quads": 0.4, "glutes": 0.4, "calves": 0.3},
        "fatigue_rating": "high",
        "technique_notes": "Hold heavy weights at sides. Walk for distance or time, maintaining upright posture, tight core.",
        "common_mistakes": ["Poor posture (slouching)", "Dropping weights too early", "Uneven steps"],
        "video_url": "https://example.com/video/farmerswalk",
        "is_public": True,
    },
    {
        "name": "Clean and Jerk",
        "category": "olympic_lift",
        "equipment": "barbell",
        "difficulty": "expert",
        "primary_muscles": {"glutes": 0.9, "quadriceps": 0.9, "hamstrings": 0.8, "shoulders": 0.7, "traps": 0.7, "triceps": 0.6, "core": 0.8}, # Full body
        "secondary_muscles": {"calves": 0.5, "lower_back": 0.6, "forearms": 0.4},
        "fatigue_rating": "very_high",
        "technique_notes": "Complex lift: clean phase (floor to shoulders), jerk phase (shoulders to overhead). Requires coaching.",
        "common_mistakes": ["Numerous; incorrect bar path", "Poor timing", "Lack of mobility", "Early arm pull"],
        "video_url": "https://example.com/video/cleanandjerk",
        "is_public": False, # Often requires specialized coaching
    },
    {
        "name": "Snatch",
        "category": "olympic_lift",
        "equipment": "barbell",
        "difficulty": "expert",
        "primary_muscles": {"glutes": 0.9, "quadriceps": 0.8, "hamstrings": 0.8, "shoulders": 0.8, "traps": 0.9, "upper_back": 0.7, "core": 0.8}, # Full body
        "secondary_muscles": {"calves": 0.5, "lower_back": 0.7, "forearms": 0.5},
        "fatigue_rating": "very_high",
        "technique_notes": "Complex lift: pull bar from floor to overhead in one continuous motion. Requires coaching.",
        "common_mistakes": ["Numerous; incorrect bar path", "Poor timing", "Lack of mobility", "Jumping forward/backward"],
        "video_url": "https://example.com/video/snatch",
        "is_public": False, # Often requires specialized coaching
    },
    {
        "name": "Kettlebell Swings",
        "category": "hinge", # Ballistic hip hinge
        "equipment": "kettlebell",
        "difficulty": "intermediate",
        "primary_muscles": {"glutes": 1.0, "hamstrings": 0.8, "core_anti_flexion": 0.7, "spinal_erectors": 0.6},
        "secondary_muscles": {"shoulders_stabilizers": 0.4, "grip": 0.5, "lats_for_control": 0.3},
        "fatigue_rating": "high", # Can be metabolically demanding
        "technique_notes": "Hinge at hips, swing kettlebell forward to chest height using hip thrust. Keep arms relaxed.",
        "common_mistakes": ["Squatting instead of hinging", "Using arms to lift bell", "Overextending back at top"],
        "video_url": "https://example.com/video/kettlebellswings",
        "is_public": True,
    }
]

def get_main_target_muscle(primary_muscles_dict):
    """
    Determines the main target muscle group from the primary_muscles dictionary.
    Chooses the muscle with the highest involvement. If multiple are equally high,
    it picks the first one encountered.
    """
    if not primary_muscles_dict:
        return None

    # Find the muscle with the maximum value
    # Sort by value descending, then by key alphabetically for tie-breaking (optional but good for consistency)
    # For this simple case, max value is enough, first encountered with max value.
    main_muscle = None
    max_value = -1.0
    for muscle, value in primary_muscles_dict.items():
        if isinstance(value, (float, int)) and value > max_value:
            max_value = value
            main_muscle = muscle
    return main_muscle

def seed_exercises():
    """Connects to the PostgreSQL database and seeds the exercises table."""
    conn = None
    inserted_count = 0
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        print(f"Successfully connected to database '{DB_NAME}' on host '{DB_HOST}' for seeding.")

        # Prepare data by adding main_target_muscle_group
        for exercise_data in EXERCISES_DATA:
            primary_muscles = exercise_data.get("primary_muscles", {})
            exercise_data["main_target_muscle_group"] = get_main_target_muscle(primary_muscles)

        with conn.cursor() as cur:
            insert_query = sql.SQL("""
                INSERT INTO exercises (
                    name, category, equipment, difficulty, primary_muscles,
                    secondary_muscles, main_target_muscle_group,
                    fatigue_rating, technique_notes,
                    common_mistakes, video_url, is_public, created_at
                ) VALUES (
                    %(name)s, %(category)s, %(equipment)s, %(difficulty)s, %(primary_muscles)s,
                    %(secondary_muscles)s, %(main_target_muscle_group)s,
                    %(fatigue_rating)s, %(technique_notes)s,
                    %(common_mistakes)s, %(video_url)s, %(is_public)s, CURRENT_TIMESTAMP
                ) ON CONFLICT (name) DO UPDATE SET
                    category = EXCLUDED.category,
                    equipment = EXCLUDED.equipment,
                    difficulty = EXCLUDED.difficulty,
                    primary_muscles = EXCLUDED.primary_muscles,
                    secondary_muscles = EXCLUDED.secondary_muscles,
                    main_target_muscle_group = EXCLUDED.main_target_muscle_group,
                    fatigue_rating = EXCLUDED.fatigue_rating,
                    technique_notes = EXCLUDED.technique_notes,
                    common_mistakes = EXCLUDED.common_mistakes,
                    video_url = EXCLUDED.video_url,
                    is_public = EXCLUDED.is_public;
            """)
            # Using ON CONFLICT (name) DO UPDATE to ensure existing records are updated if script is run again.

            for exercise in EXERCISES_DATA:
                if exercise["main_target_muscle_group"] is None:
                    print(f"Warning: Could not determine main_target_muscle_group for {exercise['name']}, skipping this field for it or defaulting.")
                    # Depending on DB schema, None might not be allowed if column is NOT NULL without default
                    # For now, it will be passed as None.

                try:
                    cur.execute(insert_query, {
                        "name": exercise["name"],
                        "category": exercise["category"],
                        "equipment": exercise["equipment"],
                        "difficulty": exercise["difficulty"],
                        "primary_muscles": Json(exercise["primary_muscles"]),
                        "secondary_muscles": Json(exercise.get("secondary_muscles", {})), # Ensure it's a dict
                        "main_target_muscle_group": exercise["main_target_muscle_group"],
                        "fatigue_rating": exercise["fatigue_rating"],
                        "technique_notes": exercise["technique_notes"],
                        "common_mistakes": exercise["common_mistakes"],
                        "video_url": exercise["video_url"],
                        "is_public": exercise["is_public"]
                    })
                    # rowcount for INSERT ON CONFLICT DO UPDATE returns:
                    # 0 if no insert or update (row existed and was identical to EXCLUDED) - this is rare with JSONB
                    # 1 if insert occurred
                    # 1 if update occurred (PostgreSQL specific, other DBs might say 2 for update)
                    if cur.rowcount > 0 : # This will count both inserts and updates as "processed"
                        inserted_count +=1 # Renaming to processed_count might be clearer
                except psycopg2.Error as e:
                    print(f"Error processing exercise {exercise['name']}: {e}")
                    conn.rollback()

        conn.commit()
        if inserted_count > 0:
            print(f"Successfully processed (inserted or updated) {inserted_count} exercises in the 'exercises' table.")
        else:
            # This case might be hit if all exercises existed and were identical, or if rowcount behavior is subtle.
            print("No exercises were newly inserted or updated. They might already exist and match the seed data.")

    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        print(f"Please ensure PostgreSQL is running and accessible on {DB_HOST}:{DB_PORT}, "
              f"and that database '{DB_NAME}' exists with user '{DB_USER}' having appropriate permissions.")
        sys.exit(1)
    except psycopg2.Error as e:
        print(f"Error during database operation: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("Database connection closed after seeding.")

if __name__ == "__main__":
    print("Attempting to seed exercises data with main_target_muscle_group...")
    seed_exercises()
    print("Seeding script finished.")
