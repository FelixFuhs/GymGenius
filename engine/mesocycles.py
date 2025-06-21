import uuid
from datetime import date, timedelta
import psycopg2 # For type hinting cursor

PHASE_ACCUMULATION = 'accumulation'
PHASE_INTENSIFICATION = 'intensification'
PHASE_DELOAD = 'deload'
PHASE_DURATIONS = {
    PHASE_ACCUMULATION: 3,
    PHASE_INTENSIFICATION: 3,
    PHASE_DELOAD: 1,
}
PHASE_ORDER = [PHASE_ACCUMULATION, PHASE_INTENSIFICATION, PHASE_DELOAD]

def _get_next_phase_details(current_phase: str, current_phase_start_date: date) -> tuple[str, date]:
    """ Calculates the next phase and its natural start date. """
    if current_phase == PHASE_ACCUMULATION:
        next_phase = PHASE_INTENSIFICATION
        next_phase_natural_start_date = current_phase_start_date + timedelta(weeks=PHASE_DURATIONS[PHASE_ACCUMULATION])
    elif current_phase == PHASE_INTENSIFICATION:
        next_phase = PHASE_DELOAD
        next_phase_natural_start_date = current_phase_start_date + timedelta(weeks=PHASE_DURATIONS[PHASE_INTENSIFICATION])
    elif current_phase == PHASE_DELOAD:
        next_phase = PHASE_ACCUMULATION # Loop back
        next_phase_natural_start_date = current_phase_start_date + timedelta(weeks=PHASE_DURATIONS[PHASE_DELOAD])
    else: # Should not happen
        next_phase = PHASE_ACCUMULATION
        next_phase_natural_start_date = current_phase_start_date
    return next_phase, next_phase_natural_start_date


def get_or_create_current_mesocycle(db_cursor: 'psycopg2.extensions.cursor', user_id: str, current_date: date) -> dict:
    db_cursor.execute(
        "SELECT id, user_id, phase, start_date, week_number FROM mesocycles "
        "WHERE user_id = %s ORDER BY start_date DESC, id DESC LIMIT 1",
        (user_id,)
    )
    meso = db_cursor.fetchone()

    if not meso:
        new_phase = PHASE_ACCUMULATION
        new_week_number = 1
        new_start_date = current_date
        meso_id = str(uuid.uuid4())
        db_cursor.execute(
            "INSERT INTO mesocycles (id, user_id, phase, start_date, week_number) VALUES (%s, %s, %s, %s, %s)",
            (meso_id, user_id, new_phase, new_start_date, new_week_number)
        )
        return {'id': meso_id, 'user_id': user_id, 'phase': new_phase, 'week_number': new_week_number, 'start_date': new_start_date}

    current_db_phase = meso['phase']
    current_db_week_number = meso['week_number']
    current_db_phase_start_date = meso['start_date']

    weeks_passed_since_db_phase_start = (current_date - current_db_phase_start_date).days // 7
    effective_week_for_db_phase = weeks_passed_since_db_phase_start + 1

    # Initialize final_ values with the current state from DB
    final_phase = current_db_phase
    final_week_in_phase = current_db_week_number
    final_phase_start_date = current_db_phase_start_date

    # Initialize loop variables based on current DB state and effective week
    loop_current_phase = current_db_phase
    loop_effective_week = effective_week_for_db_phase
    loop_phase_start_date = current_db_phase_start_date # This is the start_date of the phase currently being evaluated in the loop

    needs_db_action = False

    while True:
        current_phase_duration = PHASE_DURATIONS.get(loop_current_phase, 1)

        if loop_effective_week > current_phase_duration:
            needs_db_action = True

            previous_loop_phase_for_check = loop_current_phase # Store before overwrite for D->A check

            next_phase, next_phase_natural_start = _get_next_phase_details(loop_current_phase, loop_phase_start_date)

            weeks_passed_into_new_phase = (current_date - next_phase_natural_start).days // 7
            if weeks_passed_into_new_phase < 0:
                final_phase = loop_current_phase
                final_week_in_phase = loop_effective_week
                # final_phase_start_date remains loop_phase_start_date (start of the phase that's not yet fully completed)
                # No, it should be loop_phase_start_date, which is the start of the current phase in the loop
                final_phase_start_date = loop_phase_start_date

                if final_week_in_phase != meso['week_number'] or \
                   final_phase != meso['phase'] or \
                   final_phase_start_date != meso['start_date']:
                     needs_db_action = True
                break

            loop_phase_start_date = next_phase_natural_start
            final_phase = next_phase
            final_week_in_phase = weeks_passed_into_new_phase + 1

            if previous_loop_phase_for_check == PHASE_DELOAD and final_phase == PHASE_ACCUMULATION:
                new_meso_id = str(uuid.uuid4())
                db_cursor.execute(
                    "INSERT INTO mesocycles (id, user_id, phase, start_date, week_number) VALUES (%s, %s, %s, %s, %s)",
                    (new_meso_id, user_id, final_phase, loop_phase_start_date, final_week_in_phase) # Use loop_phase_start_date
                )
                return { # Return constructed dict with the correct values used in INSERT
                    'id': new_meso_id, 'user_id': user_id, 'phase': final_phase,
                    'start_date': loop_phase_start_date,
                    'week_number': final_week_in_phase
                }

            loop_current_phase = final_phase
            loop_effective_week = final_week_in_phase
        else:
            # No more phase transitions needed for this step
            final_phase = loop_current_phase
            final_week_in_phase = loop_effective_week
            final_phase_start_date = loop_phase_start_date # This is the start date of the true current phase
            if final_week_in_phase != meso['week_number'] or \
               final_phase != meso['phase'] or \
               final_phase_start_date != meso['start_date']: # Compare with original meso's start_date
                needs_db_action = True
            break

    if needs_db_action:
        db_cursor.execute(
            "UPDATE mesocycles SET phase = %s, week_number = %s, start_date = %s WHERE id = %s",
            (final_phase, final_week_in_phase, final_phase_start_date, meso['id'])
        )
        return {'id': meso['id'], 'user_id': user_id, 'phase': final_phase,
                'week_number': final_week_in_phase, 'start_date': final_phase_start_date}
    else:
        return meso
