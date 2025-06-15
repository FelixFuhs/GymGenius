from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import uuid
import psycopg2
import psycopg2.extras

import engine.app as app

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/v1/predict/1rm/epley', methods=['POST'])
def predict_1rm_epley():
    data = request.get_json()
    if not data or 'weight' not in data or 'reps' not in data:
        return jsonify({"error": "Missing 'weight' or 'reps' in request body"}), 400
    try:
        weight = float(data['weight'])
        reps = int(data['reps'])
    except ValueError:
        return jsonify({"error": "Invalid 'weight' or 'reps' format. Must be numeric."}), 400
    if weight <= 0:
        return jsonify({"error": "'weight' must be positive."}), 400
    if reps < 1:
        return jsonify({"error": "'reps' must be 1 or greater for Epley prediction."}), 400

    estimated_1rm = app.extended_epley_1rm(weight, reps)
    return jsonify({
        "weight_input": weight,
        "reps_input": reps,
        "estimated_1rm_epley": estimated_1rm,
        "units": "same_as_input_weight"
    })


@analytics_bp.route('/v1/user/<uuid:user_id>/update-rir-bias', methods=['POST'])
def rir_bias_update_route(user_id):
    user_id_str = str(user_id)
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    actual_reps = data.get('actual_reps')
    predicted_reps = data.get('predicted_reps')
    learning_rate = data.get('learning_rate', 0.1)
    if actual_reps is None or predicted_reps is None:
        return jsonify(error="Missing 'actual_reps' or 'predicted_reps' in request body"), 400
    try:
        actual_reps = int(actual_reps)
        predicted_reps = int(predicted_reps)
        learning_rate = float(learning_rate)
    except ValueError:
        return jsonify(error="Invalid data type for reps or learning_rate"), 400

    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT rir_bias FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone()
            if not user_data_db:
                return jsonify(error="User not found"), 404
            current_rir_bias = float(user_data_db['rir_bias'])
            new_rir_bias = app.update_user_rir_bias(current_rir_bias, predicted_reps, actual_reps, learning_rate)
            cur.execute(
                "UPDATE users SET rir_bias = %s, updated_at = NOW() WHERE id = %s;",
                (new_rir_bias, user_id_str)
            )
            conn.commit()
            return jsonify(user_id=user_id_str, new_rir_bias=new_rir_bias), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error in update_rir_bias: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in update_rir_bias: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()


@analytics_bp.route('/v1/user/<uuid:user_id>/fatigue-status', methods=['GET'])
def fatigue_status_route(user_id):
    user_id_str = str(user_id)
    muscle_group = request.args.get('muscle_group')
    if not muscle_group:
        return jsonify(error="Missing 'muscle_group' query parameter"), 400
    muscle_group = muscle_group.lower()
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT recovery_multipliers FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone()
            if not user_data_db:
                return jsonify(error="User not found"), 404
            user_recovery_multiplier = 1.0
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {}
            if isinstance(recovery_multipliers_data, dict):
                user_recovery_multiplier = float(recovery_multipliers_data.get(muscle_group, 1.0))
            session_history_query = """
                SELECT ws.completed_at AS session_date, (ws.actual_weight * ws.actual_reps) AS stimulus
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s
                  AND e.main_target_muscle_group = %s
                  AND ws.completed_at IS NOT NULL
                  AND ws.actual_weight IS NOT NULL
                  AND ws.actual_reps IS NOT NULL
                ORDER BY ws.completed_at DESC
                LIMIT 50;
            """
            try:
                cur.execute(session_history_query, (user_id_str, muscle_group))
                raw_session_history = cur.fetchall()
            except psycopg2.Error as db_err:
                app.logger.error(f"Database error fetching session history: {db_err}")
                return jsonify(error=f"Error fetching session history for {muscle_group}. Check server logs and schema."), 500
            session_history_formatted = []
            for record in raw_session_history:
                if isinstance(record['session_date'], datetime) and isinstance(record['stimulus'], (float, int)):
                    session_history_formatted.append({
                        'session_date': record['session_date'],
                        'stimulus': float(record['stimulus'])
                    })
            current_fatigue = app.calculate_current_fatigue(
                muscle_group,
                session_history_formatted,
                app.DEFAULT_RECOVERY_TAU_MAP,
                user_recovery_multiplier
            )
            return jsonify(
                user_id=user_id_str,
                muscle_group=muscle_group,
                current_fatigue=current_fatigue,
                user_recovery_multiplier_applied=user_recovery_multiplier,
                session_records_found=len(session_history_formatted)
            ), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error in fatigue_status: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in fatigue_status: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()


@analytics_bp.route('/v1/user/<uuid:user_id>/exercise/<uuid:exercise_id>/recommend-set-parameters', methods=['GET'])
def recommend_set_parameters_route(user_id, exercise_id):
    user_id_str = str(user_id)
    exercise_id_str = str(exercise_id)
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT goal_slider, rir_bias, recovery_multipliers FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone()
            if not user_data_db:
                return jsonify(error="User not found"), 404
            goal_slider = float(user_data_db['goal_slider'])
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {}
            cur.execute("SELECT name, main_target_muscle_group FROM exercises WHERE id = %s;", (exercise_id_str,))
            exercise_data_db = cur.fetchone()
            if not exercise_data_db:
                return jsonify(error="Exercise not found"), 404
            exercise_name = exercise_data_db['name']
            main_target_muscle_group = exercise_data_db['main_target_muscle_group']
            if not main_target_muscle_group:
                return jsonify(error=f"Exercise '{exercise_name}' is missing 'main_target_muscle_group'."), 500
            cur.execute(
                """
                SELECT estimated_1rm FROM estimated_1rm_history
                WHERE user_id = %s AND exercise_id = %s
                ORDER BY calculated_at DESC
                LIMIT 1;
                """,
                (user_id_str, exercise_id_str)
            )
            e1rm_data = cur.fetchone()
            estimated_1rm = 50.0
            e1rm_source = "default"
            if e1rm_data:
                estimated_1rm = float(e1rm_data['estimated_1rm'])
                e1rm_source = "history"
            user_recovery_multiplier = 1.0
            if isinstance(recovery_multipliers_data, dict):
                user_recovery_multiplier = float(recovery_multipliers_data.get(main_target_muscle_group, 1.0))
            session_history_query = """
                SELECT ws.completed_at AS session_date, (ws.actual_weight * ws.actual_reps) AS stimulus
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s AND e.main_target_muscle_group = %s
                  AND ws.completed_at IS NOT NULL AND ws.actual_weight IS NOT NULL AND ws.actual_reps IS NOT NULL
                ORDER BY ws.completed_at DESC LIMIT 50;
            """
            cur.execute(session_history_query, (user_id_str, main_target_muscle_group))
            raw_session_history = cur.fetchall()
            session_history_formatted = []
            for record in raw_session_history:
                if isinstance(record['session_date'], datetime) and isinstance(record['stimulus'], (float, int)):
                    session_history_formatted.append({
                        'session_date': record['session_date'],
                        'stimulus': float(record['stimulus'])
                    })
            current_fatigue = app.calculate_current_fatigue(
                main_target_muscle_group,
                session_history_formatted,
                app.DEFAULT_RECOVERY_TAU_MAP,
                user_recovery_multiplier
            )
            load_percentage_of_1rm = 0.60 + 0.35 * goal_slider
            target_rir_ideal = int(round(2.5 - 1.5 * goal_slider))
            rep_high_float = 6.0 + 6.0 * (1.0 - goal_slider)
            rep_high = int(round(rep_high_float))
            rep_low = int(round(max(1.0, rep_high_float - 4.0)))
            base_recommended_weight = estimated_1rm * load_percentage_of_1rm
            fatigue_adjustment_factor = (float(current_fatigue) / 10.0) * 0.01
            fatigue_adjustment_factor = min(fatigue_adjustment_factor, 0.5)
            weight_reduction_due_to_fatigue = base_recommended_weight * fatigue_adjustment_factor
            adjusted_weight = base_recommended_weight - weight_reduction_due_to_fatigue
            final_rounded_weight = round(adjusted_weight * 2) / 2.0
            goal_slider_desc = "hypertrophy" if goal_slider < 0.34 else "strength" if goal_slider > 0.66 else "blend"
            explanation = (
                f"Est. 1RM ({e1rm_source}): {estimated_1rm:.1f}kg. "
                f"Goal ('{goal_slider_desc}', slider: {goal_slider:.2f}): target {load_percentage_of_1rm*100:.0f}% of 1RM. "
                f"Base weight: {base_recommended_weight:.1f}kg. "
                f"Fatigue on '{main_target_muscle_group}' ({current_fatigue:.1f} pts): applied -{weight_reduction_due_to_fatigue:.1f}kg reduction. "
                f"Final Recommendation: {final_rounded_weight:.1f}kg for {rep_low}-{rep_high} reps @ RIR ~{target_rir_ideal}."
            )
            return jsonify({
                "user_id": user_id_str,
                "exercise_id": exercise_id_str,
                "exercise_name": exercise_name,
                "estimated_1rm_kg": round(estimated_1rm, 2),
                "e1rm_source": e1rm_source,
                "goal_slider": round(goal_slider, 2),
                "main_target_muscle_group": main_target_muscle_group,
                "current_fatigue": round(current_fatigue, 2),
                "recommended_weight_kg": final_rounded_weight,
                "target_reps_low": rep_low,
                "target_reps_high": rep_high,
                "target_rir": target_rir_ideal,
                "explanation": explanation
            }), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error in recommend_set_parameters: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in recommend_set_parameters: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()


@analytics_bp.route('/v1/users/<uuid:user_id>/exercises/<uuid:exercise_id>/plateau-analysis', methods=['GET'])
@app.jwt_required
def get_plateau_analysis(user_id, exercise_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        app.logger.warning(f"Forbidden attempt to access plateau analysis for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only access your own data."), 403

    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT name, main_target_muscle_group FROM exercises WHERE id = %s;", (str(exercise_id),))
            exercise_data = cur.fetchone()
            if not exercise_data:
                return jsonify(error=f"Exercise with ID {exercise_id} not found."), 404
            if not exercise_data['main_target_muscle_group']:
                return jsonify(error=f"Exercise '{exercise_data['name']}' (ID: {exercise_id}) is missing 'main_target_muscle_group' which is required for analysis."), 404
            exercise_name = exercise_data['name']
            main_target_muscle_group = exercise_data['main_target_muscle_group']
            cur.execute(
                """
                SELECT estimated_1rm, calculated_at FROM estimated_1rm_history
                WHERE user_id = %s AND exercise_id = %s
                ORDER BY calculated_at ASC;
                """,
                (str(user_id), str(exercise_id))
            )
            e1rm_history_records = cur.fetchall()
            historical_e1rms = [float(record['estimated_1rm']) for record in e1rm_history_records]
            MIN_DATA_POINTS_FOR_PLATEAU = 7
            if len(historical_e1rms) < MIN_DATA_POINTS_FOR_PLATEAU:
                return jsonify({
                    "user_id": str(user_id),
                    "exercise_id": str(exercise_id),
                    "exercise_name": exercise_name,
                    "main_target_muscle_group": main_target_muscle_group,
                    "historical_data_points_count": len(historical_e1rms),
                    "plateau_analysis": None,
                    "current_fatigue_score": None,
                    "deload_suggested": False,
                    "deload_protocol": None,
                    "summary_message": f"Insufficient data for plateau analysis. Need at least {MIN_DATA_POINTS_FOR_PLATEAU} e1RM records."
                }), 200
            cur.execute("SELECT recovery_multipliers FROM users WHERE id = %s;", (str(user_id),))
            user_data_db = cur.fetchone()
            if not user_data_db:
                app.logger.error(f"User data not found for user {user_id} despite passing JWT check.")
                return jsonify(error="User data inconsistency."), 500
            user_recovery_multiplier = 1.0
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {}
            if isinstance(recovery_multipliers_data, dict):
                user_recovery_multiplier = float(recovery_multipliers_data.get(main_target_muscle_group, 1.0))
            session_history_query = """
                SELECT ws.completed_at AS session_date, (ws.actual_weight * ws.actual_reps) AS stimulus
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s AND e.main_target_muscle_group = %s
                  AND ws.completed_at IS NOT NULL AND ws.actual_weight IS NOT NULL AND ws.actual_reps IS NOT NULL
                ORDER BY ws.completed_at DESC LIMIT 50;
            """
            cur.execute(session_history_query, (str(user_id), main_target_muscle_group))
            raw_session_history = cur.fetchall()
            session_history_formatted = []
            for record in raw_session_history:
                if isinstance(record['session_date'], datetime) and isinstance(record['stimulus'], (float, int)):
                    session_history_formatted.append({
                        'session_date': record['session_date'],
                        'stimulus': float(record['stimulus'])
                    })
            current_fatigue_score = app.calculate_current_fatigue(
                main_target_muscle_group,
                session_history_formatted,
                app.DEFAULT_RECOVERY_TAU_MAP,
                user_recovery_multiplier
            )
            current_fatigue_score = round(current_fatigue_score, 2)
            plateau_min_duration = max(3, MIN_DATA_POINTS_FOR_PLATEAU - 2)
            plateau_result = app.detect_plateau(values=historical_e1rms, min_duration=plateau_min_duration)
            deload_suggested = False
            deload_protocol = None
            summary_message = f"Analysis complete for {exercise_name}."
            if plateau_result['plateauing']:
                deload_suggested = True
                plateau_severity = 0.0
                if plateau_result['status'] == app.PlateauStatus.REGRESSION:
                    plateau_severity = 0.8
                    summary_message = f"Regression detected for {exercise_name}. A deload is recommended."
                elif plateau_result['status'] == app.PlateauStatus.STAGNATION:
                    plateau_severity = 0.5
                    summary_message = f"Stagnation detected for {exercise_name}. Consider a deload."
                elif plateau_result['status'] in [app.PlateauStatus.REGRESSION_WARNING, app.PlateauStatus.STAGNATION_WARNING]:
                    plateau_severity = 0.3
                    summary_message = f"Warning of potential {plateau_result['status'].name.lower().replace('_warning','')} for {exercise_name}."
                    if plateau_severity < 0.4:
                        deload_suggested = False
                if deload_suggested:
                    deload_duration_weeks = 1
                    if plateau_severity >= 0.7:
                        deload_duration_weeks = 2
                    deload_protocol = app.generate_deload_protocol(
                        plateau_severity=plateau_severity,
                        deload_duration_weeks=deload_duration_weeks,
                        recent_fatigue_score=current_fatigue_score
                    )
            else:
                summary_message = f"No significant plateau detected for {exercise_name} based on the last {len(historical_e1rms)} records."
            return jsonify({
                "user_id": str(user_id),
                "exercise_id": str(exercise_id),
                "exercise_name": exercise_name,
                "main_target_muscle_group": main_target_muscle_group,
                "historical_data_points_count": len(historical_e1rms),
                "plateau_analysis": plateau_result,
                "current_fatigue_score": current_fatigue_score,
                "deload_suggested": deload_suggested,
                "deload_protocol": deload_protocol,
                "summary_message": summary_message
            }), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error during plateau analysis for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="Database operation failed during analysis."), 500
    except Exception as e:
        app.logger.error(f"Unexpected error during plateau analysis for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred during analysis."), 500
    finally:
        if conn:
            conn.close()
