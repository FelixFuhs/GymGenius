# engine/constants.py

SEX_MULTIPLIERS = {
    'male': 1.0,
    'female': 0.7,
    'other': 0.85,
    'unknown': 0.85  # Default for unspecified or other non-binary genders
}

# Placeholder for EXERCISE_DEFAULT_1RM - this might be defined elsewhere
# or loaded from a file/DB, but for now, to make it clear where it would be
# if centralized. For the purpose of this task, we assume it's available
# where needed in analytics.py
EXERCISE_DEFAULT_1RM = {
    "bench_press": {
        "beginner": 40, # kg
        "intermediate": 70,
        "advanced": 100
    },
    "squat": {
        "beginner": 50,
        "intermediate": 90,
        "advanced": 130
    },
    "deadlift": {
        "beginner": 60,
        "intermediate": 100,
        "advanced": 150
    }
    # ... other exercises
}

PLATEAU_EVENT_NOTIFICATION_COOLDOWN_WEEKS = 3
