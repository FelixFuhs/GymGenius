import pytest
import json
import uuid
import datetime
from unittest.mock import patch, MagicMock, ANY # ANY is useful for some mock assertions

import psycopg2 # For explicitly raising psycopg2.Error in tests

# Import the Flask app from engine.app
from engine.app import app
# Assuming PlateauStatus is accessible for mocking detect_plateau results
from engine.progression import PlateauStatus

# --- Test Fixtures ---

@pytest.fixture
def client():
    """A test client for the app."""
    with app.app_context():
        app.config['TESTING'] = True
        # app.config['JWT_SECRET_KEY'] = 'test-secret-key' # Ensure this is consistent if not using app's default
        client = app.test_client()
        yield client

# --- Helper Functions ---

def generate_jwt_token(user_id, secret_key=None):
    """Generates a JWT token for a given user_id."""
    import jwt
    if secret_key is None:
        secret_key = app.config['JWT_SECRET_KEY']

    payload = {
        'user_id': str(user_id),
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

# --- Mock Data ---
MOCK_USER_ID = str(uuid.uuid4())
MOCK_OTHER_USER_ID = str(uuid.uuid4())
MOCK_EXERCISE_ID = str(uuid.uuid4())
MOCK_EXERCISE_NAME = "Test Bench Press"
MOCK_MUSCLE_GROUP = "chest"

# --- Test Cases for Plateau Analysis Endpoint ---

@patch('engine.app.generate_deload_protocol')
@patch('engine.app.detect_plateau')
@patch('engine.app.calculate_current_fatigue')
@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_success_no_plateau(
    mock_get_db_conn, mock_calc_fatigue, mock_detect_plateau, mock_gen_deload, client
):
    # Setup Mocks
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # DB Mocks
    mock_cursor.fetchone.side_effect = [
        {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': MOCK_MUSCLE_GROUP}, # Exercise details
        {'recovery_multipliers': {MOCK_MUSCLE_GROUP: 1.0}} # User recovery multipliers
    ]
    mock_cursor.fetchall.side_effect = [
        [{'estimated_1rm': 100.0 + i} for i in range(10)], # e1RM history (10 data points)
        [] # Session history for fatigue (empty for simplicity here)
    ]

    mock_calc_fatigue.return_value = 15.0 # Low fatigue
    mock_detect_plateau.return_value = {'plateauing': False, 'status': PlateauStatus.NO_PLATEAU, 'slope': 0.5}

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['exercise_name'] == MOCK_EXERCISE_NAME
    assert data['historical_data_points_count'] == 10
    assert data['plateau_analysis']['plateauing'] is False
    assert data['plateau_analysis']['status'] == PlateauStatus.NO_PLATEAU.name # Enum is serialized to name
    assert data['current_fatigue_score'] == 15.0
    assert data['deload_suggested'] is False
    assert data['deload_protocol'] is None
    mock_gen_deload.assert_not_called()
    mock_detect_plateau.assert_called_once()


@patch('engine.app.generate_deload_protocol')
@patch('engine.app.detect_plateau')
@patch('engine.app.calculate_current_fatigue')
@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_success_stagnation_with_deload(
    mock_get_db_conn, mock_calc_fatigue, mock_detect_plateau, mock_gen_deload, client
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.side_effect = [
        {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': MOCK_MUSCLE_GROUP},
        {'recovery_multipliers': {}}
    ]
    mock_cursor.fetchall.side_effect = [
        [{'estimated_1rm': 100.0} for _ in range(10)], # Stagnant e1RM history
        []
    ]

    mock_calc_fatigue.return_value = 40.0 # Moderate fatigue
    mock_detect_plateau.return_value = {'plateauing': True, 'status': PlateauStatus.STAGNATION, 'slope': 0.05}
    mock_gen_deload.return_value = [{'week': 1, 'instruction': 'Reduce volume by 20%'}]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['plateau_analysis']['plateauing'] is True
    assert data['plateau_analysis']['status'] == PlateauStatus.STAGNATION.name
    assert data['current_fatigue_score'] == 40.0
    assert data['deload_suggested'] is True
    assert len(data['deload_protocol']) == 1
    assert data['deload_protocol'][0]['instruction'] == 'Reduce volume by 20%'
    mock_gen_deload.assert_called_once_with(
        plateau_severity=0.5, # Expected for STAGNATION
        deload_duration_weeks=ANY, # or specific value if you want to be more precise
        recent_fatigue_score=40.0
    )

@patch('engine.app.generate_deload_protocol')
@patch('engine.app.detect_plateau')
@patch('engine.app.calculate_current_fatigue')
@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_success_regression_with_deload(
    mock_get_db_conn, mock_calc_fatigue, mock_detect_plateau, mock_gen_deload, client
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.side_effect = [
        {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': MOCK_MUSCLE_GROUP},
        {'recovery_multipliers': {}}
    ]
    mock_cursor.fetchall.side_effect = [
        [{'estimated_1rm': 100.0 - i} for i in range(10)], # Regressing e1RM history
        []
    ]

    mock_calc_fatigue.return_value = 60.0 # High fatigue
    mock_detect_plateau.return_value = {'plateauing': True, 'status': PlateauStatus.REGRESSION, 'slope': -0.5}
    mock_gen_deload.return_value = [{'week': 1, 'instruction': 'Reduce intensity significantly'}]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['plateau_analysis']['plateauing'] is True
    assert data['plateau_analysis']['status'] == PlateauStatus.REGRESSION.name
    assert data['deload_suggested'] is True
    assert data['deload_protocol'][0]['instruction'] == 'Reduce intensity significantly'
    mock_gen_deload.assert_called_once_with(
        plateau_severity=0.8, # Expected for REGRESSION
        deload_duration_weeks=ANY,
        recent_fatigue_score=60.0
    )

@patch('engine.app.get_db_connection') # Only need to mock DB for this one
def test_get_plateau_analysis_insufficient_data(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.return_value = {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': MOCK_MUSCLE_GROUP}
    mock_cursor.fetchall.return_value = [{'estimated_1rm': 100.0} for _ in range(3)] # Only 3 data points

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200 # Endpoint returns 200 with a message
    data = response.get_json()
    assert "Insufficient data for plateau analysis" in data['summary_message']
    assert data['historical_data_points_count'] == 3
    assert data['plateau_analysis'] is None
    assert data['deload_suggested'] is False

def test_get_plateau_analysis_unauthorized_missing_token(client):
    response = client.get(f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis')
    assert response.status_code == 401

def test_get_plateau_analysis_forbidden_wrong_user(client):
    token = generate_jwt_token(MOCK_OTHER_USER_ID) # Token for other user
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis', # Requesting for MOCK_USER_ID
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403

@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_exercise_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Simulate exercise not found

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert f"Exercise with ID {MOCK_EXERCISE_ID} not found" in response.get_json()['error']

@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_exercise_no_main_target_muscle_group(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': None}

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert f"is missing 'main_target_muscle_group'" in response.get_json()['error']

@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_db_error_exercise_fetch(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    # Simulate DB error when fetching exercise details
    mock_cursor.execute.side_effect = lambda query, params: psycopg2.Error("Simulated DB error") if "FROM exercises WHERE id = %s" in query else MagicMock()

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 500
    assert "Database operation failed" in response.get_json()['error']

@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_db_error_1rm_history_fetch(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # First call (exercise details) is fine
    mock_cursor.fetchone.return_value = {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': MOCK_MUSCLE_GROUP}
    # Second execute call (e1RM history) raises error
    def conditional_execute_effect(query, params):
        if "FROM estimated_1rm_history" in query:
            raise psycopg2.Error("Simulated DB error on e1RM fetch")
        return MagicMock() # Default for other execute calls
    mock_cursor.execute.side_effect = conditional_execute_effect

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 500
    assert "Database operation failed" in response.get_json()['error']


@patch('engine.app.get_db_connection')
def test_get_plateau_analysis_db_error_fatigue_calc_related_fetch(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # First execute (exercise details) and fetchall (e1RM history) are fine
    mock_cursor.fetchone.side_effect = [
        {'name': MOCK_EXERCISE_NAME, 'main_target_muscle_group': MOCK_MUSCLE_GROUP}, # Exercise details
        # No more fetchone needed until after the failing execute
    ]
    mock_cursor.fetchall.return_value = [{'estimated_1rm': 100.0 + i} for i in range(10)] # e1RM history

    # Third execute call (user recovery multipliers) raises error
    def conditional_execute_effect(query, params):
        if "FROM users WHERE id = %s" in query: # This is for recovery_multipliers
            raise psycopg2.Error("Simulated DB error on fatigue data fetch")
        return MagicMock()

    # Need to ensure the first execute for exercise details doesn't use this side_effect
    original_execute = mock_cursor.execute # Store original
    def side_effect_router(query, params=None): # Params might be None for some calls
        if "FROM exercises WHERE id = %s" in query:
            return original_execute(query, params)
        elif "FROM estimated_1rm_history" in query:
            return original_execute(query, params)
        elif "FROM users WHERE id = %s" in query:
            raise psycopg2.Error("Simulated DB error on fatigue data fetch")
        elif "FROM workout_sets ws" in query: # Could also fail here
             raise psycopg2.Error("Simulated DB error on fatigue data fetch")
        return original_execute(query,params)

    mock_cursor.execute.side_effect = side_effect_router

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/exercises/{MOCK_EXERCISE_ID}/plateau-analysis',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 500
    assert "Database operation failed" in response.get_json()['error']

if __name__ == '__main__':
    pytest.main()
