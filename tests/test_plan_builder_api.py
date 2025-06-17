import pytest
import uuid
from unittest.mock import patch, MagicMock

# Import the Flask app from engine.app
# Ensure that engine/app.py can be imported. This might require adjusting PYTHONPATH or project structure.
# For this example, assuming 'engine' is a package and app.py is in it.
from engine.app import app

# --- Test Fixtures ---

@pytest.fixture
def client():
    """A test client for the app."""
    with app.app_context(): # Ensure app context is active for tests
        app.config['TESTING'] = True
        # Use a fixed JWT secret for testing if your app.config['JWT_SECRET_KEY'] is dynamic
        # app.config['JWT_SECRET_KEY'] = 'test-secret-key'
        client = app.test_client()
        yield client

# --- Helper Functions ---

def generate_jwt_token(user_id, secret_key=None):
    """Generates a JWT token for a given user_id."""
    import jwt
    import datetime
    if secret_key is None:
        secret_key = app.config['JWT_SECRET_KEY'] # Use app's configured key

    payload = {
        'user_id': str(user_id),
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

# --- Mock Data ---
MOCK_USER_ID = str(uuid.uuid4())
MOCK_OTHER_USER_ID = str(uuid.uuid4())
MOCK_PLAN_ID = str(uuid.uuid4())
MOCK_DAY_ID = str(uuid.uuid4())
MOCK_EXERCISE_ID_DB = str(uuid.uuid4()) # An exercise ID that exists in the mocked DB
MOCK_PLAN_EXERCISE_ID = str(uuid.uuid4())


# --- Test Cases for Workout Plan Endpoints ---

@patch('engine.app.get_db_connection')
def test_create_workout_plan_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock DB returning the new plan
    mock_plan_data = {
        'id': MOCK_PLAN_ID,
        'user_id': MOCK_USER_ID,
        'name': 'My New Plan',
        'days_per_week': 3,
        'plan_length_weeks': 4,
        'goal_focus': 'hypertrophy',
        'created_at': '2023-01-01T10:00:00Z',
        'updated_at': '2023-01-01T10:00:00Z'
    }
    mock_cursor.fetchone.side_effect = [
        mock_plan_data,
        {'main_target_muscle_group': 'chest'}
    ]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'name': 'My New Plan',
            'days_per_week': 3,
            'plan_length_weeks': 4,
            'goal_focus': 'hypertrophy',
            'days': [
                {
                    'day_number': 1,
                    'name': 'Day 1',
                    'exercises': [
                        {'exercise_id': MOCK_EXERCISE_ID_DB, 'sets': 5}
                    ]
                }
            ]
        }
    )

    assert response.status_code == 201
    response_data = response.get_json()
    assert response_data['name'] == 'My New Plan'
    assert response_data['user_id'] == MOCK_USER_ID
    assert response_data['total_volume'] == 5
    assert response_data['muscle_group_frequency']['chest'] == 1
    assert any('plan_metrics' in str(c.args[0]) for c in mock_cursor.execute.call_args_list)

@patch('engine.app.get_db_connection')
def test_create_workout_plan_unauthorized_no_token(mock_get_db_conn, client):
    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans',
        json={'name': 'My New Plan'}
    )
    assert response.status_code == 401
    assert 'token is missing' in response.get_json()['message'].lower()

@patch('engine.app.get_db_connection')
def test_create_workout_plan_forbidden_wrong_user(mock_get_db_conn, client):
    token = generate_jwt_token(MOCK_OTHER_USER_ID) # Token for a different user
    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans', # Path for MOCK_USER_ID
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'My New Plan'}
    )
    assert response.status_code == 403
    assert 'only create plans for your own profile' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_create_workout_plan_bad_request_missing_name(mock_get_db_conn, client):
    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans',
        headers={'Authorization': f'Bearer {token}'},
        json={'days_per_week': 3} # Missing 'name'
    )
    assert response.status_code == 400
    assert 'missing required field: name' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_get_workout_plans_for_user_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_plans_list = [
        {'id': MOCK_PLAN_ID, 'user_id': MOCK_USER_ID, 'name': 'Plan 1'},
        {'id': str(uuid.uuid4()), 'user_id': MOCK_USER_ID, 'name': 'Plan 2'}
    ]
    mock_cursor.fetchall.return_value = mock_plans_list

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/users/{MOCK_USER_ID}/plans',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    response_data = response.get_json()
    assert len(response_data) == 2
    assert response_data[0]['name'] == 'Plan 1'

@patch('engine.app.get_db_connection')
def test_get_specific_workout_plan_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_plan_details = {
        'id': MOCK_PLAN_ID,
        'user_id': uuid.UUID(MOCK_USER_ID), # Ensure UUID type for comparison in endpoint
        'name': 'Detailed Plan',
        'days': [] # Simplified, real endpoint populates this
    }
    # Simulate multiple fetchone/fetchall calls for plan, days, exercises
    mock_cursor.fetchone.side_effect = [
        mock_plan_details, # First call for the plan itself
        # Potentially more if days/exercises were deeply mocked here
    ]
    mock_cursor.fetchall.side_effect = [
        [], # For plan_days
        # Potentially more if exercises were fetched per day
    ]


    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['name'] == 'Detailed Plan'
    assert response_data['id'] == MOCK_PLAN_ID
    # In a more detailed test, assert structure of 'days' and their 'exercises'

@patch('engine.app.get_db_connection')
def test_get_specific_workout_plan_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Plan not found

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/plans/{str(uuid.uuid4())}', # Non-existent plan ID
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert 'plan not found' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_get_specific_workout_plan_forbidden(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Plan exists but belongs to MOCK_OTHER_USER_ID
    mock_plan_details = {'id': MOCK_PLAN_ID, 'user_id': uuid.UUID(MOCK_OTHER_USER_ID), 'name': 'Other User Plan'}
    mock_cursor.fetchone.return_value = mock_plan_details

    token = generate_jwt_token(MOCK_USER_ID) # Current user is MOCK_USER_ID
    response = client.get(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403
    assert 'you do not own this plan' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_update_workout_plan_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock fetching owner and then the updated plan
    mock_owner_check = {'user_id': uuid.UUID(MOCK_USER_ID)}
    updated_plan_data = {'id': MOCK_PLAN_ID, 'user_id': MOCK_USER_ID, 'name': 'Updated Plan Name'}
    mock_cursor.fetchone.side_effect = [mock_owner_check, updated_plan_data]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Updated Plan Name'}
    )
    assert response.status_code == 200
    assert response.get_json()['name'] == 'Updated Plan Name'

@patch('engine.app.get_db_connection')
def test_update_workout_plan_with_structure_change_updates_metrics(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock fetching owner
    mock_owner_check = {'user_id': uuid.UUID(MOCK_USER_ID)}
    # Mock exercise details for metric calculation
    mock_exercise_detail_leg = {'main_target_muscle_group': 'Legs'}
    mock_exercise_detail_chest = {'main_target_muscle_group': 'Chest'}

    # Mock return values for various execute calls:
    # 1. Ownership check
    # 2. Updated plan data (after workout_plans table update)
    # 3. Exercise detail for 'Legs' exercise (during metrics calculation)
    # 4. Exercise detail for 'Chest' exercise (during metrics calculation)
    # 5. Final fetch of updated plan for response (SELECT * from workout_plans)
    # 6. Fetch plan_days for response
    # 7. Fetch plan_exercises for day 1
    # 8. Fetch plan_exercises for day 2 (if any)
    # 9. Fetch metrics for response
    updated_plan_base_data = {'id': MOCK_PLAN_ID, 'user_id': MOCK_USER_ID, 'name': 'Updated Plan Structure'}

    mock_cursor.fetchone.side_effect = [
        mock_owner_check,          # Initial ownership check
        updated_plan_base_data,    # Result of UPDATE workout_plans ... RETURNING *
        mock_exercise_detail_leg,  # For metrics: exercise_id_1 (Squat)
        mock_exercise_detail_chest,# For metrics: exercise_id_2 (Bench Press)
        updated_plan_base_data,    # For rebuilding response: SELECT * from workout_plans
        {'total_volume': 7, 'muscle_group_frequency': {'Legs': 1, 'Chest': 1}} # For rebuilding response: SELECT from plan_metrics
    ]
    # Mock fetchall for plan days and exercises when rebuilding response
    mock_cursor.fetchall.side_effect = [
        [ # Plan days for response
            {'id': 'new_day_id_1', 'plan_id': MOCK_PLAN_ID, 'day_number': 1, 'name': 'New Day 1'},
        ],
        [ # Plan exercises for new_day_id_1 for response
            {'exercise_id': 'exercise_id_1', 'exercise_name': 'Squat', 'sets': 4},
            {'exercise_id': 'exercise_id_2', 'exercise_name': 'Bench Press', 'sets': 3}
        ]
    ]


    token = generate_jwt_token(MOCK_USER_ID)
    updated_plan_payload = {
        'name': 'Updated Plan Structure', # Optional: can also update name
        'days': [
            {
                'day_number': 1,
                'name': 'New Day 1',
                'exercises': [
                    {'exercise_id': 'exercise_id_1', 'sets': 4, 'order_index': 0, 'reps': 5}, # e.g., Squat
                    {'exercise_id': 'exercise_id_2', 'sets': 3, 'order_index': 1, 'reps': 5}  # e.g., Bench Press
                ]
            }
            # Potentially more days
        ]
    }

    response = client.put(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json=updated_plan_payload
    )

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['name'] == 'Updated Plan Structure'
    assert response_data['total_volume'] == 7
    assert response_data['muscle_group_frequency']['Legs'] == 1
    assert response_data['muscle_group_frequency']['Chest'] == 1

    # Verify that plan_metrics upsert was called with correct calculated values
    plan_metrics_upsert_called = False
    for call_args in mock_cursor.execute.call_args_list:
        sql_query = call_args.args[0]
        if "INSERT INTO plan_metrics" in sql_query and "ON CONFLICT (plan_id) DO UPDATE" in sql_query:
            plan_metrics_upsert_called = True
            # args passed to execute: (sql, params)
            params = call_args.args[1]
            assert params[0] == MOCK_PLAN_ID  # plan_id
            assert params[1] == 7             # total_volume
            assert params[2].adapted == json.dumps({'Legs': 1, 'Chest': 1}) # muscle_group_frequency
            break
    assert plan_metrics_upsert_called, "Plan metrics upsert was not called"

    # Verify that existing plan_days were deleted
    delete_plan_days_called = any("DELETE FROM plan_days WHERE plan_id = %s;" in str(c.args[0]) and c.args[1] == (MOCK_PLAN_ID,) for c in mock_cursor.execute.call_args_list)
    assert delete_plan_days_called, "DELETE FROM plan_days was not called"

@patch('engine.app.get_db_connection')
def test_update_workout_plan_without_structure_change_preserves_metrics(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock fetching owner
    mock_owner_check = {'user_id': uuid.UUID(MOCK_USER_ID)}
    # Mock data for the plan being updated (name only)
    updated_plan_data = {'id': MOCK_PLAN_ID, 'user_id': MOCK_USER_ID, 'name': 'Only Name Updated'}

    # Side effects for fetchone:
    # 1. Ownership check
    # 2. Result of UPDATE workout_plans RETURNING *
    # 3. (If response rebuilds metrics) SELECT from plan_metrics
    # For this test, we are asserting metrics are NOT recalculated from days payload.
    # So, the plan details returned might or might not include metrics based on prior state.
    # The key is that _calculate_and_store_plan_metrics is NOT called with new days_payload.

    # If the endpoint's response always includes metrics, we need to provide them.
    # Assume the plan had some metrics previously.
    existing_metrics = {'total_volume': 10, 'muscle_group_frequency': {'Back': 2}}

    mock_cursor.fetchone.side_effect = [
        mock_owner_check,
        updated_plan_data, # After UPDATE workout_plans
        existing_metrics # When fetching metrics for the response
    ]
    # If full plan details are refetched for response (days and exercises)
    mock_cursor.fetchall.side_effect = [
        [], # No plan days (or mock them if needed for full response validation)
    ]


    token = generate_jwt_token(MOCK_USER_ID)
    update_payload = {
        'name': 'Only Name Updated'
        # 'days' array is NOT included in this payload
    }

    response = client.put(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_payload
    )

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['name'] == 'Only Name Updated'

    # Assert that metrics calculation and storage logic was NOT invoked with a new days_payload
    # This means no DELETE FROM plan_days and no INSERT/UPSERT to plan_metrics based on new calculations.
    delete_plan_days_called = False
    plan_metrics_recalculated = False
    for call_args in mock_cursor.execute.call_args_list:
        sql_query = str(call_args.args[0]) # Ensure it's a string for searching
        if "DELETE FROM plan_days WHERE plan_id = %s;" == sql_query.strip() and call_args.args[1] == (MOCK_PLAN_ID,):
            delete_plan_days_called = True
        # Check if the specific UPSERT for metrics was called (distinguish from initial creation if any)
        # This check is tricky if the helper is always called.
        # The key is that the _calculate_and_store_plan_metrics helper is not called with a NEW days_payload from request.
        # The current implementation of update_workout_plan only processes days IF 'days' in data.
        # So, we mainly check that plan_days are not deleted.

    assert not delete_plan_days_called, "DELETE FROM plan_days was called, indicating structure change was processed."

    # To be very sure metrics weren't recalculated from a non-existent days_payload,
    # one might need to inspect calls to _calculate_and_store_plan_metrics if it were a mockable object,
    # or ensure the UPSERT to plan_metrics wasn't made with values derived from an empty/default days_payload.
    # The absence of `DELETE FROM plan_days` is a strong indicator.
    # The response should still contain the old metrics.
    if existing_metrics: # If we mocked that the plan had metrics
        assert response_data.get('total_volume') == existing_metrics['total_volume']
        assert response_data.get('muscle_group_frequency') == existing_metrics['muscle_group_frequency']


@patch('engine.app.get_db_connection')
def test_delete_workout_plan_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_owner_check = {'user_id': uuid.UUID(MOCK_USER_ID)}
    mock_cursor.fetchone.return_value = mock_owner_check
    mock_cursor.rowcount = 1 # Simulate successful deletion

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.delete(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 204

# --- Placeholder for Plan Day and Plan Exercise Tests ---
# These would follow a similar structure to the Workout Plan tests above,
# mocking appropriate database calls and checking for correct responses and status codes.

# Example for Plan Day creation:
@patch('engine.app.get_db_connection')
def test_create_plan_day_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock 1: Parent plan ownership check
    mock_plan_owner = {'user_id': uuid.UUID(MOCK_USER_ID)}
    # Mock 2: Check for existing day_number (return None for no conflict)
    # Mock 3: Return value for the new plan day
    new_plan_day_data = {
        'id': MOCK_DAY_ID, 'plan_id': MOCK_PLAN_ID, 'day_number': 1, 'name': 'Day 1 - Push'
    }
    mock_cursor.fetchone.side_effect = [mock_plan_owner, None, new_plan_day_data]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/plans/{MOCK_PLAN_ID}/days',
        headers={'Authorization': f'Bearer {token}'},
        json={'day_number': 1, 'name': 'Day 1 - Push'}
    )
    assert response.status_code == 201
    response_data = response.get_json()
    assert response_data['name'] == 'Day 1 - Push'
    assert response_data['plan_id'] == MOCK_PLAN_ID

@patch('engine.app.get_db_connection')
def test_create_plan_day_conflict(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_plan_owner = {'user_id': uuid.UUID(MOCK_USER_ID)}
    existing_day_conflict = {'id': str(uuid.uuid4())} # Simulate finding an existing day
    mock_cursor.fetchone.side_effect = [mock_plan_owner, existing_day_conflict]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/plans/{MOCK_PLAN_ID}/days',
        headers={'Authorization': f'Bearer {token}'},
        json={'day_number': 1, 'name': 'Day 1 - Push'}
    )
    assert response.status_code == 409 # Conflict
    assert 'already exists for this plan' in response.get_json()['error']


@patch('engine.app.get_db_connection')
def test_get_plan_days_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock 1: Parent plan ownership check
    mock_plan_owner = {'user_id': uuid.UUID(MOCK_USER_ID)}
    # Mock 2: Return list of plan days
    mock_days_list = [
        {'id': MOCK_DAY_ID, 'plan_id': MOCK_PLAN_ID, 'day_number': 1, 'name': 'Day 1'},
        {'id': str(uuid.uuid4()), 'plan_id': MOCK_PLAN_ID, 'day_number': 2, 'name': 'Day 2'}
    ]
    mock_cursor.fetchone.return_value = mock_plan_owner # For plan ownership check
    mock_cursor.fetchall.return_value = mock_days_list # For list of days

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/plans/{MOCK_PLAN_ID}/days',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    response_data = response.get_json()
    assert len(response_data) == 2
    assert response_data[0]['name'] == 'Day 1'

@patch('engine.app.get_db_connection')
def test_get_plan_days_plan_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Plan not found

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/plans/{str(uuid.uuid4())}/days',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert 'parent workout plan not found' in response.get_json()['error'].lower()


@patch('engine.app.get_db_connection')
def test_update_plan_day_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock 1: fetch day_info (includes plan_owner_id)
    mock_day_info = {'plan_day_id': MOCK_DAY_ID, 'plan_id': MOCK_PLAN_ID, 'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    # Mock 2: day_number conflict check (return None for no conflict)
    # Mock 3: updated plan day data
    updated_day_data = {'id': MOCK_DAY_ID, 'name': 'Updated Day Name', 'day_number': 2}
    mock_cursor.fetchone.side_effect = [mock_day_info, None, updated_day_data]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/plandays/{MOCK_DAY_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Updated Day Name', 'day_number': 2}
    )
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['name'] == 'Updated Day Name'
    assert response_data['day_number'] == 2

@patch('engine.app.get_db_connection')
def test_update_plan_day_forbidden(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_day_info_other_owner = {'plan_day_id': MOCK_DAY_ID, 'plan_id': MOCK_PLAN_ID, 'plan_owner_id': uuid.UUID(MOCK_OTHER_USER_ID)}
    mock_cursor.fetchone.return_value = mock_day_info_other_owner

    token = generate_jwt_token(MOCK_USER_ID) # Current user is MOCK_USER_ID
    response = client.put(
        f'/v1/plandays/{MOCK_DAY_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Attempted Update'}
    )
    assert response.status_code == 403
    assert 'you do not own the parent plan' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_delete_plan_day_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_day_info = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    mock_cursor.fetchone.return_value = mock_day_info
    mock_cursor.rowcount = 1 # Simulate successful deletion

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.delete(
        f'/v1/plandays/{MOCK_DAY_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 204

@patch('engine.app.get_db_connection')
def test_delete_plan_day_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Day not found

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.delete(
        f'/v1/plandays/{str(uuid.uuid4())}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert 'plan day not found' in response.get_json()['error'].lower()


# Example for Plan Exercise creation:
@patch('engine.app.get_db_connection')
def test_create_plan_exercise_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock 1: Parent plan day ownership check
    mock_day_owner = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    # Mock 2: Exercise ID existence check in 'exercises' table
    mock_exercise_exists = {'id': MOCK_EXERCISE_ID_DB}
    # Mock 3: Check for order_index conflict (return None for no conflict)
    # Mock 4: Return value for the new plan exercise
    new_plan_exercise_data = {
        'id': MOCK_PLAN_EXERCISE_ID, 'plan_day_id': MOCK_DAY_ID,
        'exercise_id': MOCK_EXERCISE_ID_DB, 'order_index': 0, 'sets': 3
    }
    mock_cursor.fetchone.side_effect = [mock_day_owner, mock_exercise_exists, None, new_plan_exercise_data]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/plandays/{MOCK_DAY_ID}/exercises',
        headers={'Authorization': f'Bearer {token}'},
        json={'exercise_id': MOCK_EXERCISE_ID_DB, 'order_index': 0, 'sets': 3}
    )
    assert response.status_code == 201
    response_data = response.get_json()
    assert response_data['exercise_id'] == MOCK_EXERCISE_ID_DB
    assert response_data['plan_day_id'] == MOCK_DAY_ID

@patch('engine.app.get_db_connection')
def test_create_plan_exercise_exercise_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    non_existent_exercise_id = str(uuid.uuid4())

    mock_day_owner = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    mock_exercise_exists_check_returns_none = None # Exercise not found
    mock_cursor.fetchone.side_effect = [mock_day_owner, mock_exercise_exists_check_returns_none]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/plandays/{MOCK_DAY_ID}/exercises',
        headers={'Authorization': f'Bearer {token}'},
        json={'exercise_id': non_existent_exercise_id, 'order_index': 0, 'sets': 3}
    )
    assert response.status_code == 404 # Or 400 depending on how you want to classify this error
    assert f"exercise with id {non_existent_exercise_id} not found" in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_get_plan_exercises_for_day_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_day_owner = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    mock_exercises_list = [
        {'id': MOCK_PLAN_EXERCISE_ID, 'exercise_name': 'Bench Press', 'order_index': 0},
        {'id': str(uuid.uuid4()), 'exercise_name': 'Squat', 'order_index': 1}
    ]
    mock_cursor.fetchone.return_value = mock_day_owner # For day ownership check
    mock_cursor.fetchall.return_value = mock_exercises_list # For list of exercises

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/plandays/{MOCK_DAY_ID}/exercises',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    response_data = response.get_json()
    assert len(response_data) == 2
    assert response_data[0]['exercise_name'] == 'Bench Press'

@patch('engine.app.get_db_connection')
def test_get_plan_exercises_for_day_day_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Day not found for ownership check

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.get(
        f'/v1/plandays/{str(uuid.uuid4())}/exercises',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert 'parent plan day not found' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_update_plan_exercise_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_exercise_info = {
        'plan_exercise_id': MOCK_PLAN_EXERCISE_ID,
        'plan_day_id': MOCK_DAY_ID,
        'plan_id': MOCK_PLAN_ID,
        'plan_owner_id': uuid.UUID(MOCK_USER_ID)
    }
    # For the updated exercise data + exercise name lookup
    updated_exercise_data = {
        'id': MOCK_PLAN_EXERCISE_ID, 'sets': 5, 'exercise_id': MOCK_EXERCISE_ID_DB
    }
    exercise_name_lookup = {'name': 'Test Exercise'}

    # Mock fetchone calls:
    # 1. exercise_info (owner check)
    # 2. order_index conflict check (None means no conflict if order_index is changed)
    # 3. updated exercise data (RETURNING *)
    # 4. exercise name lookup
    mock_cursor.fetchone.side_effect = [mock_exercise_info, None, updated_exercise_data, exercise_name_lookup]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/planexercises/{MOCK_PLAN_EXERCISE_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'sets': 5, 'order_index': 1} # Example update
    )
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['sets'] == 5
    assert response_data['exercise_name'] == 'Test Exercise'


@patch('engine.app.get_db_connection')
def test_update_plan_exercise_order_conflict(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_exercise_info = {
        'plan_exercise_id': MOCK_PLAN_EXERCISE_ID,
        'plan_day_id': MOCK_DAY_ID,
        'plan_owner_id': uuid.UUID(MOCK_USER_ID)
    }
    conflict_check_finds_exercise = {'id': str(uuid.uuid4())} # Different ID, same order_index

    # Simulate ownership check passes, then order_index conflict found
    mock_cursor.fetchone.side_effect = [mock_exercise_info, conflict_check_finds_exercise]

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/planexercises/{MOCK_PLAN_EXERCISE_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'order_index': 0} # Attempting to update order_index
    )
    assert response.status_code == 409
    assert 'already exists for this day' in response.get_json()['error']


@patch('engine.app.get_db_connection')
def test_delete_plan_exercise_success(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_exercise_info = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    mock_cursor.fetchone.return_value = mock_exercise_info
    mock_cursor.rowcount = 1 # Simulate successful deletion

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.delete(
        f'/v1/planexercises/{MOCK_PLAN_EXERCISE_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 204

@patch('engine.app.get_db_connection')
def test_delete_plan_exercise_forbidden(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_exercise_info_other_owner = {'plan_owner_id': uuid.UUID(MOCK_OTHER_USER_ID)}
    mock_cursor.fetchone.return_value = mock_exercise_info_other_owner

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.delete(
        f'/v1/planexercises/{MOCK_PLAN_EXERCISE_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403
    assert 'you do not own the parent plan' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_create_workout_plan_invalid_days_per_week(mock_get_db_conn, client):
    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Test Plan', 'days_per_week': 8} # Invalid days_per_week
    )
    assert response.status_code == 400
    assert "invalid 'days_per_week'" in response.get_json()['error'].lower()
    assert "must be between 1 and 7" in response.get_json()['error'].lower()

    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Test Plan', 'days_per_week': 0} # Invalid days_per_week
    )
    assert response.status_code == 400
    assert "must be between 1 and 7" in response.get_json()['error'].lower()


@patch('engine.app.get_db_connection')
def test_create_workout_plan_invalid_plan_length_weeks(mock_get_db_conn, client):
    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/users/{MOCK_USER_ID}/plans',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Test Plan', 'plan_length_weeks': 0} # Invalid plan_length_weeks
    )
    assert response.status_code == 400
    assert "invalid 'plan_length_weeks'" in response.get_json()['error'].lower()
    assert "must be at least 1 week" in response.get_json()['error'].lower()


@patch('engine.app.get_db_connection')
def test_update_workout_plan_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Plan not found for ownership check

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/plans/{str(uuid.uuid4())}',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Updated Name'}
    )
    assert response.status_code == 404
    assert 'workout plan not found' in response.get_json()['error'].lower()


@patch('engine.app.get_db_connection')
def test_update_workout_plan_forbidden(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Plan exists but belongs to MOCK_OTHER_USER_ID
    mock_owner_check = {'user_id': uuid.UUID(MOCK_OTHER_USER_ID)}
    mock_cursor.fetchone.return_value = mock_owner_check

    token = generate_jwt_token(MOCK_USER_ID) # Current user is MOCK_USER_ID
    response = client.put(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Attempted Update by Wrong User'}
    )
    assert response.status_code == 403
    assert 'you do not own this plan' in response.get_json()['error'].lower()


@patch('engine.app.get_db_connection')
def test_delete_workout_plan_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Plan not found for ownership check

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.delete(
        f'/v1/plans/{str(uuid.uuid4())}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 404
    assert 'workout plan not found' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_delete_workout_plan_forbidden(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Plan exists but belongs to MOCK_OTHER_USER_ID
    mock_owner_check = {'user_id': uuid.UUID(MOCK_OTHER_USER_ID)}
    mock_cursor.fetchone.return_value = mock_owner_check

    token = generate_jwt_token(MOCK_USER_ID) # Current user is MOCK_USER_ID
    response = client.delete(
        f'/v1/plans/{MOCK_PLAN_ID}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403
    assert 'you do not own this plan' in response.get_json()['error'].lower()

# --- Plan Day Specific Validations ---
@patch('engine.app.get_db_connection')
def test_create_plan_day_invalid_day_number(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_plan_owner = {'user_id': uuid.UUID(MOCK_USER_ID)}
    mock_cursor.fetchone.return_value = mock_plan_owner # Plan ownership check

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.post(
        f'/v1/plans/{MOCK_PLAN_ID}/days',
        headers={'Authorization': f'Bearer {token}'},
        json={'day_number': -1, 'name': 'Invalid Day'}
    )
    assert response.status_code == 400
    assert "invalid 'day_number'" in response.get_json()['error'].lower()
    assert "must be a non-negative integer" in response.get_json()['error'].lower()

    response = client.post(
        f'/v1/plans/{MOCK_PLAN_ID}/days',
        headers={'Authorization': f'Bearer {token}'},
        json={'day_number': 'not-an-int', 'name': 'Invalid Day Type'}
    )
    assert response.status_code == 400
    assert "invalid 'day_number'" in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_update_plan_day_invalid_day_number(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_day_info = {'plan_day_id': MOCK_DAY_ID, 'plan_id': MOCK_PLAN_ID, 'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    mock_cursor.fetchone.return_value = mock_day_info # Ownership check

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/plandays/{MOCK_DAY_ID}',
        headers={'Authorization': f'Bearer {token}'},
        json={'day_number': -5}
    )
    assert response.status_code == 400
    assert "invalid 'day_number'" in response.get_json()['error'].lower()
    assert "must be a non-negative integer" in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_update_plan_day_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Day not found for ownership/update

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/plandays/{str(uuid.uuid4())}',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Updated Name'}
    )
    assert response.status_code == 404
    assert 'plan day not found' in response.get_json()['error'].lower()

# --- Plan Exercise Specific Validations ---

@patch('engine.app.get_db_connection')
def test_create_plan_exercise_missing_required_fields(mock_get_db_conn, client):
    mock_conn = MagicMock() # Simplified, assumes ownership check would pass if it got that far
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_day_owner = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)} # For parent day ownership
    mock_cursor.fetchone.return_value = mock_day_owner

    token = generate_jwt_token(MOCK_USER_ID)

    # Missing exercise_id
    response = client.post(
        f'/v1/plandays/{MOCK_DAY_ID}/exercises',
        headers={'Authorization': f'Bearer {token}'},
        json={'order_index': 0, 'sets': 3}
    )
    assert response.status_code == 400
    assert 'missing required field: exercise_id' in response.get_json()['error'].lower()

    # Missing order_index
    response = client.post(
        f'/v1/plandays/{MOCK_DAY_ID}/exercises',
        headers={'Authorization': f'Bearer {token}'},
        json={'exercise_id': MOCK_EXERCISE_ID_DB, 'sets': 3}
    )
    assert response.status_code == 400
    assert 'missing required field: order_index' in response.get_json()['error'].lower()

    # Missing sets
    response = client.post(
        f'/v1/plandays/{MOCK_DAY_ID}/exercises',
        headers={'Authorization': f'Bearer {token}'},
        json={'exercise_id': MOCK_EXERCISE_ID_DB, 'order_index': 0}
    )
    assert response.status_code == 400
    assert 'missing required field: sets' in response.get_json()['error'].lower()

@patch('engine.app.get_db_connection')
def test_create_plan_exercise_invalid_values(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_day_owner = {'plan_owner_id': uuid.UUID(MOCK_USER_ID)}
    mock_exercise_exists = {'id': MOCK_EXERCISE_ID_DB}
    # Simulate ownership, exercise existence, no order conflict for these tests
    mock_cursor.fetchone.side_effect = [mock_day_owner, mock_exercise_exists, None, MagicMock()]


    token = generate_jwt_token(MOCK_USER_ID)
    base_valid_payload = {'exercise_id': MOCK_EXERCISE_ID_DB, 'order_index': 0, 'sets': 3}

    # Invalid order_index
    payload = {**base_valid_payload, 'order_index': -1}
    response = client.post(f'/v1/plandays/{MOCK_DAY_ID}/exercises', headers={'Authorization': f'Bearer {token}'}, json=payload)
    assert response.status_code == 400
    assert "'order_index' must be non-negative" in response.get_json()['error']
    mock_cursor.fetchone.side_effect = [mock_day_owner, mock_exercise_exists, None, MagicMock()] # Reset side_effect

    # Invalid sets
    payload = {**base_valid_payload, 'sets': 0}
    response = client.post(f'/v1/plandays/{MOCK_DAY_ID}/exercises', headers={'Authorization': f'Bearer {token}'}, json=payload)
    assert response.status_code == 400
    assert "'sets' must be at least 1" in response.get_json()['error']
    mock_cursor.fetchone.side_effect = [mock_day_owner, mock_exercise_exists, None, MagicMock()]

    # Invalid rep_range_low
    payload = {**base_valid_payload, 'rep_range_low': -1}
    response = client.post(f'/v1/plandays/{MOCK_DAY_ID}/exercises', headers={'Authorization': f'Bearer {token}'}, json=payload)
    assert response.status_code == 400
    assert "'rep_range_low' must be non-negative" in response.get_json()['error']
    mock_cursor.fetchone.side_effect = [mock_day_owner, mock_exercise_exists, None, MagicMock()]

    # Invalid rest_seconds
    payload = {**base_valid_payload, 'rest_seconds': -10}
    response = client.post(f'/v1/plandays/{MOCK_DAY_ID}/exercises', headers={'Authorization': f'Bearer {token}'}, json=payload)
    assert response.status_code == 400
    assert "'rest_seconds' must be non-negative" in response.get_json()['error']


@patch('engine.app.get_db_connection')
def test_update_plan_exercise_invalid_values(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_exercise_info = {
        'plan_exercise_id': MOCK_PLAN_EXERCISE_ID, 'plan_day_id': MOCK_DAY_ID,
        'plan_id': MOCK_PLAN_ID, 'plan_owner_id': uuid.UUID(MOCK_USER_ID)
    }
    # Simulate ownership check pass, no conflict for valid updates
    mock_cursor.fetchone.side_effect = lambda q,v: mock_exercise_info if "pe.id = %s" in q else \
                                                (None if "order_index = %s" in q else MagicMock())


    token = generate_jwt_token(MOCK_USER_ID)

    # Invalid sets
    response = client.put(f'/v1/planexercises/{MOCK_PLAN_EXERCISE_ID}', headers={'Authorization': f'Bearer {token}'}, json={'sets': 0})
    assert response.status_code == 400
    assert "'sets' must be at least 1" in response.get_json()['error']
    mock_cursor.fetchone.side_effect = lambda q,v: mock_exercise_info if "pe.id = %s" in q else \
                                        (None if "order_index = %s" in q else MagicMock())

    # Invalid rep_range_high
    response = client.put(f'/v1/planexercises/{MOCK_PLAN_EXERCISE_ID}', headers={'Authorization': f'Bearer {token}'}, json={'rep_range_high': -2})
    assert response.status_code == 400
    assert "'rep_range_high' must be non-negative" in response.get_json()['error']

@patch('engine.app.get_db_connection')
def test_update_plan_exercise_not_found(mock_get_db_conn, client):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Exercise not found for ownership/update check

    token = generate_jwt_token(MOCK_USER_ID)
    response = client.put(
        f'/v1/planexercises/{str(uuid.uuid4())}',
        headers={'Authorization': f'Bearer {token}'},
        json={'sets': 5}
    )
    assert response.status_code == 404
    assert 'plan exercise not found' in response.get_json()['error'].lower()


# TODO: Add more tests for PUT, DELETE, GET (list/specific) for PlanDay and PlanExercise -> Mostly done for PlanExercise now
# TODO: Add tests for various error conditions (400, 401, 403, 404, 409) for all endpoints. -> Covered many, can always add more specific field validations
# TODO: Consider testing specific validation logic (e.g., days_per_week range). -> Partially done for workout plan create

if __name__ == '__main__':
    # This allows running pytest directly on this file if needed, though typically run via `pytest` command
    pytest.main()
