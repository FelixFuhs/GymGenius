import pytest
from datetime import datetime, timezone, timedelta
import uuid
import jwt # For decoding tokens to get jti if needed by other parts of app flow
from engine.app import app # Main Flask app
from engine.blueprints import workouts as workouts_bp # Blueprint to be tested

# --- Fake Database Layer (Adapted for Workouts) ---
class FakeWorkoutsCursor:
    def __init__(self, conn):
        self.conn = conn
        self.result_set = []
        self.current_row = -1
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, query, params=None):
        self.result_set = []
        self.current_row = -1
        self.rowcount = 0
        q_lower = query.lower().strip()
        params_tuple = params if isinstance(params, tuple) else (params,)

        # print(f"Executing query: {q_lower} with params: {params_tuple}") # Debugging

        if "update workout_sets set" in q_lower and "where id = %s and workout_id in (select id from workouts where user_id = %s)" in q_lower:
            # PATCH /v1/sets/<set_id>
            # Example: UPDATE workout_sets SET actual_reps = %s, updated_at = NOW() WHERE id = %s AND workout_id IN (...)
            set_id_to_update = params_tuple[-2] # set_id is second to last
            user_id_for_ownership = params_tuple[-1] # user_id is last

            # Find the set
            found_set = None
            owning_workout_id = None
            for s_id, s_data in self.conn.workout_sets.items():
                if s_id == set_id_to_update:
                    # Check ownership: workout_id of set must belong to user_id_for_ownership
                    workout_of_set = self.conn.workouts.get(s_data['workout_id'])
                    if workout_of_set and workout_of_set['user_id'] == user_id_for_ownership:
                        found_set = s_data
                        owning_workout_id = s_data['workout_id']
                        break

            if found_set:
                # Parse SET clauses. This is simplified. A real parser would be complex.
                # "SET actual_reps = %s, notes = %s, updated_at = NOW() WHERE ..."
                # Assuming params_tuple[:-2] are the values for the set clauses
                updates_to_apply = {}
                set_clause_str = query.split("SET")[1].split("WHERE")[0].strip()
                update_fields = [f.split('=')[0].strip() for f in set_clause_str.split(',') if "updated_at = now()" not in f.lower()]

                for i, field_name in enumerate(update_fields):
                    updates_to_apply[field_name] = params_tuple[i]

                if updates_to_apply: # Only update if there are fields to change
                    for key, value in updates_to_apply.items():
                        found_set[key] = value
                    found_set['updated_at'] = datetime.now(timezone.utc)
                    self.conn.workout_sets[set_id_to_update] = found_set
                    self.rowcount = 1
                else: # No actual fields to update, but ownership was fine
                    self.rowcount = 0
            else:
                self.rowcount = 0


        elif "delete from workout_sets where id = %s and workout_id in (select id from workouts where user_id = %s)" in q_lower:
            # DELETE /v1/sets/<set_id>
            set_id_to_delete = params_tuple[0]
            user_id_for_ownership = params_tuple[1]

            found_set = None
            for s_id, s_data in self.conn.workout_sets.items():
                if s_id == set_id_to_delete:
                    workout_of_set = self.conn.workouts.get(s_data['workout_id'])
                    if workout_of_set and workout_of_set['user_id'] == user_id_for_ownership:
                        found_set = s_data
                        break

            if found_set:
                del self.conn.workout_sets[set_id_to_delete]
                self.rowcount = 1
            else:
                self.rowcount = 0

        elif "select workout_id from workout_sets where id = %s" in q_lower: # Helper for PATCH ownership check
            set_id_check = params_tuple[0]
            s_data = self.conn.workout_sets.get(set_id_check)
            if s_data:
                self.result_set = [{'workout_id': s_data['workout_id']}]
            else:
                self.result_set = []

        elif "select id from workout_sets where id = %s" in q_lower: # Helper for DELETE ownership check
             set_id_check = params_tuple[0]
             if self.conn.workout_sets.get(set_id_check):
                 self.result_set = [{'id': set_id_check}]
             else:
                 self.result_set = []

        # Add more query handlers as needed for setup or other tests
        elif "insert into exercises" in q_lower:
            ex_id, name = params_tuple[0], params_tuple[1] # Simplified
            self.conn.exercises[ex_id] = {'id': ex_id, 'name': name, 'is_public': True} # Add other fields as needed
            self.rowcount = 1

        elif "insert into workouts (id, user_id" in q_lower: # Made more specific
            # Assuming order: id, user_id, plan_day_id, started_at, fatigue_level, sleep_hours, stress_level, notes
            # For tests, we might only care about id and user_id primarily
            workout_id, user_id_val = params_tuple[0], params_tuple[1]
            self.conn.workouts[workout_id] = {
                'id': workout_id,
                'user_id': user_id_val,
                'started_at': params_tuple[3] if len(params_tuple) > 3 else datetime.now(timezone.utc)
                # Add other fields if they are used by the code being tested
            }
            self.rowcount = 1
            # For RETURNING *, simulate it
            self.result_set = [self.conn.workouts[workout_id]]


        elif "insert into workout_sets (id, workout_id, exercise_id" in q_lower: # Made more specific
            # id, workout_id, exercise_id, set_number, actual_weight, actual_reps, actual_rir, mti, completed_at, notes
            # Simplified: id, workout_id, exercise_id, set_number, weight, reps, rir, notes
            set_data_map = {
                'id': params_tuple[0], 'workout_id': params_tuple[1], 'exercise_id': params_tuple[2],
                'set_number': params_tuple[3], 'actual_weight': params_tuple[4],
                'actual_reps': params_tuple[5], 'actual_rir': params_tuple[6],
                'notes': params_tuple[9] if len(params_tuple) > 9 else None, # Assuming notes is 10th param (index 9)
                'mti': params_tuple[7] if len(params_tuple) > 7 else 0.0, # Assuming mti is 8th param (index 7)
                'completed_at': params_tuple[8] if len(params_tuple) > 8 else datetime.now(timezone.utc),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            self.conn.workout_sets[set_data_map['id']] = set_data_map
            self.rowcount = 1
            self.result_set = [set_data_map] # For RETURNING *

        elif "select id from workouts where id = %s" in q_lower: # For fetching a single workout by ID (used by other tests)
            workout_id_to_find = params_tuple[0]
            if workout_id_to_find in self.conn.workouts:
                self.result_set = [self.conn.workouts[workout_id_to_find]]
            else:
                self.result_set = []

        elif "select user_id from workouts where id = %s" in q_lower: # For ownership check
            workout_id_to_find = params_tuple[0]
            workout = self.conn.workouts.get(workout_id_to_find)
            if workout:
                self.result_set = [{'user_id': workout['user_id']}]
            else:
                self.result_set = []

        # Queries for recommend_set_parameters_for_exercise
        elif "select goal_slider, rir_bias, available_plates" in q_lower and "from users where id = %s" in q_lower:
            user_id_param = params_tuple[0]
            user_details = self.conn.users.get(user_id_param) # Assuming users stored by id for this
            if user_details:
                # Ensure all selected fields are returned with defaults if not present in mock
                self.result_set = [{
                    'goal_slider': user_details.get('goal_slider', 0.5),
                    'rir_bias': user_details.get('rir_bias', 0.0),
                    'available_plates': user_details.get('available_plates', {'plates_kg': [20,10,5,2.5,1.25], 'barbell_weight_kg': 20.0}),
                    'barbell_weight_kg': (user_details.get('available_plates', {}).get('barbell_weight_kg', 20.0)
                                          if isinstance(user_details.get('available_plates'), dict)
                                          else 20.0)
                }]
            else:
                self.result_set = []

        elif "select id, name, equipment_type, main_target_muscle_group from exercises where id = %s" in q_lower:
            ex_id_param = params_tuple[0]
            ex_details = self.conn.exercises.get(ex_id_param)
            if ex_details:
                self.result_set = [{
                    'id': ex_details['id'], # Added id and name for logging in endpoint
                    'name': ex_details['name'],
                    'equipment_type': ex_details.get('equipment_type', 'barbell'),
                    'main_target_muscle_group': ex_details.get('main_target_muscle_group', 'chest') # Example default
                }]
            else:
                self.result_set = []

        elif "select estimated_1rm from estimated_1rm_history where user_id = %s and exercise_id = %s" in q_lower:
            user_id_param, ex_id_param = params_tuple[0], params_tuple[1]
            history_key = f"{user_id_param}_{ex_id_param}"
            e1rm_rec = self.conn.estimated_1rm_history.get(history_key) # Get latest
            if e1rm_rec:
                self.result_set = [{'estimated_1rm': e1rm_rec['estimated_1rm']}]
            else:
                self.result_set = []

        elif "select sleep_hours, stress_level, hrv_ms from workouts where user_id = %s and completed_at is not null" in q_lower:
            user_id_param = params_tuple[0]
            # Find the latest completed workout for this user
            latest_workout = None
            for w_id, w_data in self.conn.workouts.items():
                if w_data['user_id'] == user_id_param and w_data.get('completed_at') is not None:
                    if latest_workout is None or w_data['completed_at'] > latest_workout['completed_at']:
                        latest_workout = w_data

            if latest_workout:
                self.result_set = [{
                    'sleep_hours': latest_workout.get('sleep_hours'),
                    'stress_level': latest_workout.get('stress_level'),
                    'hrv_ms': latest_workout.get('hrv_ms')
                }]
            else:
                self.result_set = []

        elif "select w.completed_at as session_date, sum(ws.mti) as stimulus" in q_lower:
            # Query for fatigue session history
            user_id_param = params_tuple[0]
            muscle_group_param = params_tuple[1]
            # This mock will be simpler: it will rely on pre-populated self.conn.fatigue_history
            # which tests can set up directly.
            # fatigue_history structure: list of dicts like [{'session_date': dt, 'stimulus': float}]
            self.result_set = self.conn.fatigue_session_history.get(f"{user_id_param}_{muscle_group_param}", [])


    def fetchone(self):
        if not self.result_set or self.current_row >= len(self.result_set) -1 and self.current_row != -1 : # -1 means execute was just called
            if self.current_row == -1 and self.result_set : # first fetchone after execute
                 self.current_row = 0
                 return self.result_set[0]
            return None
        self.current_row +=1
        return self.result_set[self.current_row]

    def fetchall(self):
        return self.result_set


class FakeWorkoutsConn:
    def __init__(self):
        self.users = {} # user_id -> {id, email, goal_slider, rir_bias, available_plates etc.}
        self.exercises = {} # exercise_id -> {id, name, equipment_type, main_target_muscle_group}
        self.workouts = {} # workout_id -> {id, user_id, completed_at, sleep_hours, stress_level, hrv_ms ...}
        self.workout_sets = {} # set_id -> {workout_id, exercise_id, weight, reps, rir, notes, updated_at, mti}
        self.estimated_1rm_history = {} # composite_key (user_id_exercise_id) -> {estimated_1rm, calculated_at} - simplified to store only latest
        self.fatigue_session_history = {} # key: f"{user_id}_{muscle_group}" -> list of session records

    def cursor(self, cursor_factory=None):
        return FakeWorkoutsCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

# --- Pytest Fixtures ---
@pytest.fixture(scope='module') # Use module scope if app config is test-wide
def test_app():
    app.config.update({
        "TESTING": True,
        "JWT_SECRET_KEY": "test-secret-key-workouts",
        # Ensure any other necessary configs are set (e.g., DB paths if not fully mocked)
    })
    yield app

@pytest.fixture
def client(test_app):
    return test_app.test_client()

@pytest.fixture(autouse=True) # Autouse to apply to all tests in this file
def mock_db(monkeypatch):
    """Provide a fake database layer for workout endpoints."""
    conn = FakeWorkoutsConn()
    # Mock for the workouts blueprint
    monkeypatch.setattr(workouts_bp, 'get_db_connection', lambda: conn)
    monkeypatch.setattr(workouts_bp, 'release_db_connection', lambda _conn: None)

    # If @jwt_required uses its own db connection from engine.app, mock that too if blocklist is involved
    # For PATCH/DELETE on sets, blocklist is not directly used by these endpoints, but by @jwt_required.
    # If using the same FakeConn for auth features (like blocklist) it needs to be comprehensive.
    # For now, assuming these tests focus on workout logic, and @jwt_required is tested elsewhere
    # or its DB interactions are simple (e.g. does not write to blocklist here).
    # If blocklist IS used by @jwt_required, this mock_db needs to handle jwt_blocklist table too.
    # Let's assume for now that the JWT validation itself is fine and we are testing endpoint logic.
    yield conn


@pytest.fixture
def registered_user(client, mock_db): # Depends on mock_db to store user if auth is also faked here
    user_email = f"testuser_{uuid.uuid4()}@example.com"
    user_password = "password123"

    # Simulate user registration if your FakeWorkoutsConn needs user records
    # This part might need actual auth API call if not faking user table within FakeWorkoutsConn
    # For now, let's assume user ID is what matters and we can generate one.
    user_id = str(uuid.uuid4())
    # Store user with default fields needed for recommendation endpoint
    mock_db.users[user_id] = {
        'id': user_id,
        'email': user_email,
        'goal_slider': 0.5, # Default
        'rir_bias': 0.0,    # Default
        'available_plates': {'plates_kg': [25,20,15,10,5,2.5,1.25], 'barbell_weight_kg': 20.0}, # Default
        'password_hash': 'some_hash' # Needed if other parts of app interact with users table
    }
    return {"id": user_id, "email": user_email, "password": user_password}

@pytest.fixture
def auth_headers(client, registered_user):
    # This would typically involve calling a login endpoint to get a real token.
    # For simplicity in unit testing endpoints *after* auth, we can craft a token.
    # However, the created token needs 'jti' if logout/blocklist is involved in flow.
    # The PATCH/DELETE endpoints themselves don't add to blocklist.
    # The @jwt_required decorator checks it.

    # For these tests, we need a valid token that passes @jwt_required.
    # The decorator needs `g.current_user_id` and `g.decoded_token_data`.
    # A simple way is to generate a token known to the test app.
    token_payload = {
        'user_id': registered_user['id'],
        'exp': datetime.now(timezone.utc) + timedelta(minutes=15),
        'iat': datetime.now(timezone.utc),
        'jti': str(uuid.uuid4()) # Important for blocklist if that's tested implicitly
    }
    access_token = jwt.encode(token_payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    return {'Authorization': f'Bearer {access_token}'}


@pytest.fixture
def test_exercise(mock_db):
    ex_id = str(uuid.uuid4())
    ex_data = {
        'id': ex_id,
        'name': 'Test Exercise',
        'category': 'Strength',
        'equipment_type': 'barbell',
        'main_target_muscle_group': 'chest', # Example
        'is_public': True
    }
    mock_db.exercises[ex_id] = ex_data
    return ex_data

@pytest.fixture
def test_workout(mock_db, registered_user):
    workout_id = str(uuid.uuid4())
    workout_data = {
        'id': workout_id,
        'user_id': registered_user['id'],
        'started_at': datetime.now(timezone.utc)
    }
    mock_db.workouts[workout_id] = workout_data
    return workout_data

@pytest.fixture
def test_set(mock_db, test_workout, test_exercise):
    set_id = str(uuid.uuid4())
    set_data = {
        'id': set_id,
        'workout_id': test_workout['id'],
        'exercise_id': test_exercise['id'],
        'set_number': 1,
        'actual_weight': 100.0,
        'actual_reps': 5,
        'actual_rir': 2,
        'notes': 'Initial test set',
        'mti': 10.0, # Example MTI
        'completed_at': datetime.now(timezone.utc),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }
    mock_db.workout_sets[set_id] = set_data
    return set_data

# --- Actual Tests ---

# PATCH /v1/sets/<set_id> Tests
def test_edit_set_success(client, auth_headers, test_set, mock_db, registered_user):
    update_payload = {
        "actual_reps": 8,
        "notes": "Updated notes for test set"
    }
    original_updated_at = mock_db.workout_sets[test_set['id']]['updated_at']

    response = client.patch(f"/v1/sets/{test_set['id']}", headers=auth_headers, json=update_payload)

    assert response.status_code == 200
    assert response.json['msg'] == "Set updated successfully"

    updated_set_in_db = mock_db.workout_sets[test_set['id']]
    assert updated_set_in_db['actual_reps'] == update_payload['actual_reps']
    assert updated_set_in_db['notes'] == update_payload['notes']
    assert updated_set_in_db['actual_weight'] == test_set['actual_weight'] # Unchanged
    assert updated_set_in_db['updated_at'] > original_updated_at

def test_edit_set_empty_payload(client, auth_headers, test_set):
    response = client.patch(f"/v1/sets/{test_set['id']}", headers=auth_headers, json={})
    assert response.status_code == 400
    assert "No valid fields to update" in response.json.get('description', response.json.get('error', ''))

def test_edit_set_no_json_payload(client, auth_headers, test_set):
    response = client.patch(f"/v1/sets/{test_set['id']}", headers=auth_headers) # No json kwarg
    assert response.status_code == 400
    assert "No JSON payload provided" in response.json.get('description', response.json.get('error', ''))


def test_edit_set_invalid_data_types(client, auth_headers, test_set):
    payload = {"actual_reps": "should_be_int"}
    response = client.patch(f"/v1/sets/{test_set['id']}", headers=auth_headers, json=payload)
    assert response.status_code == 400
    assert "Invalid type for field 'actual_reps'" in response.json.get('description', response.json.get('error', ''))

def test_edit_set_unauthorized_different_user(client, auth_headers, test_set, mock_db):
    # Create another user and try to edit test_set which belongs to original registered_user
    other_user_id = str(uuid.uuid4())
    mock_db.users[other_user_id] = {'id': other_user_id, 'email': 'other@example.com'}

    other_user_token_payload = {
        'user_id': other_user_id, 'exp': datetime.now(timezone.utc) + timedelta(minutes=15), 'jti': str(uuid.uuid4())
    }
    other_user_access_token = jwt.encode(other_user_token_payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    other_auth_headers = {'Authorization': f'Bearer {other_user_access_token}'}

    payload = {"actual_reps": 10}
    response = client.patch(f"/v1/sets/{test_set['id']}", headers=other_auth_headers, json=payload)
    assert response.status_code == 404 # Current implementation returns 404 due to ownership check failing
    assert "Set not found or not authorized" in response.json.get('description', response.json.get('error', ''))


def test_edit_set_not_found(client, auth_headers):
    non_existent_set_id = str(uuid.uuid4())
    payload = {"actual_reps": 5}
    response = client.patch(f"/v1/sets/{non_existent_set_id}", headers=auth_headers, json=payload)
    assert response.status_code == 404
    assert "Set not found" in response.json.get('description', response.json.get('error', '')) # Check if it's "Set not found" specifically

def test_edit_set_partial_update(client, auth_headers, test_set, mock_db):
    update_payload = {"notes": "Only notes updated"}
    original_reps = mock_db.workout_sets[test_set['id']]['actual_reps']
    original_weight = mock_db.workout_sets[test_set['id']]['actual_weight']

    response = client.patch(f"/v1/sets/{test_set['id']}", headers=auth_headers, json=update_payload)
    assert response.status_code == 200

    updated_set_in_db = mock_db.workout_sets[test_set['id']]
    assert updated_set_in_db['notes'] == update_payload['notes']
    assert updated_set_in_db['actual_reps'] == original_reps # Should be unchanged
    assert updated_set_in_db['actual_weight'] == original_weight # Should be unchanged


# DELETE /v1/sets/<set_id> Tests
def test_delete_set_success(client, auth_headers, test_set, mock_db):
    set_id_to_delete = test_set['id']
    assert set_id_to_delete in mock_db.workout_sets # Pre-condition

    response = client.delete(f"/v1/sets/{set_id_to_delete}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json['msg'] == "Set deleted successfully"
    assert set_id_to_delete not in mock_db.workout_sets # Post-condition

def test_delete_set_unauthorized_different_user(client, test_set, mock_db):
    other_user_id = str(uuid.uuid4())
    mock_db.users[other_user_id] = {'id': other_user_id, 'email': 'other_delete@example.com'}
    other_user_token_payload = {
        'user_id': other_user_id, 'exp': datetime.now(timezone.utc) + timedelta(minutes=15), 'jti': str(uuid.uuid4())
    }
    other_user_access_token = jwt.encode(other_user_token_payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    other_auth_headers = {'Authorization': f'Bearer {other_user_access_token}'}

    response = client.delete(f"/v1/sets/{test_set['id']}", headers=other_auth_headers)
    assert response.status_code == 404
    assert "Set not found or not authorized" in response.json.get('description', response.json.get('error', ''))
    assert test_set['id'] in mock_db.workout_sets # Ensure it wasn't deleted


def test_delete_set_not_found(client, auth_headers):
    non_existent_set_id = str(uuid.uuid4())
    response = client.delete(f"/v1/sets/{non_existent_set_id}", headers=auth_headers)
    assert response.status_code == 404
    assert "Set not found" in response.json.get('description', response.json.get('error', '')) # Distinguish this from unauthorized


# Integration Test Example
def test_delete_set_impact_on_workout(client, auth_headers, mock_db, registered_user, test_exercise):
    # Create a workout
    workout_id = str(uuid.uuid4())
    mock_db.workouts[workout_id] = {'id': workout_id, 'user_id': registered_user['id'], 'started_at': datetime.now(timezone.utc)}

    # Create 3 sets for this workout
    set1_id = str(uuid.uuid4())
    set2_id = str(uuid.uuid4())
    set3_id = str(uuid.uuid4())

    mock_db.workout_sets[set1_id] = {'id': set1_id, 'workout_id': workout_id, 'exercise_id': test_exercise['id'], 'set_number': 1, 'actual_reps': 5, 'actual_weight': 100}
    mock_db.workout_sets[set2_id] = {'id': set2_id, 'workout_id': workout_id, 'exercise_id': test_exercise['id'], 'set_number': 2, 'actual_reps': 5, 'actual_weight': 100}
    mock_db.workout_sets[set3_id] = {'id': set3_id, 'workout_id': workout_id, 'exercise_id': test_exercise['id'], 'set_number': 3, 'actual_reps': 5, 'actual_weight': 100}

    # Delete the 2nd set
    response = client.delete(f"/v1/sets/{set2_id}", headers=auth_headers)
    assert response.status_code == 200
    assert set2_id not in mock_db.workout_sets

    # Verify workout still exists
    assert workout_id in mock_db.workouts
    # Verify other sets still exist and are linked to the workout
    assert set1_id in mock_db.workout_sets
    assert mock_db.workout_sets[set1_id]['workout_id'] == workout_id
    assert set3_id in mock_db.workout_sets
    assert mock_db.workout_sets[set3_id]['workout_id'] == workout_id

    # Verify count of sets for this workout (optional, depends on how you'd query this)
    count = 0
    for s_data in mock_db.workout_sets.values():
        if s_data['workout_id'] == workout_id:
            count +=1
    assert count == 2

# Placeholder for further tests if needed
# E.g., testing the recalculation logic if it were implemented beyond comments.
# This would require more complex mocking or a test setup that can run RQ tasks.

# --- Recommendation Endpoint Tests ---

@patch('engine.blueprints.workouts.calculate_training_params')
@patch('engine.blueprints.workouts.calculate_readiness_multiplier')
@patch('engine.blueprints.workouts.round_to_available_plates')
@patch('engine.blueprints.workouts.calculate_current_fatigue') # Though fatigue is placeholder for now
def test_recommend_set_parameters_success(
    mock_calc_fatigue, mock_round_plates, mock_calc_readiness, mock_calc_training_params,
    client, auth_headers, registered_user, test_exercise, mock_db
):
    user_id = registered_user['id']
    exercise_id = test_exercise['id']

    # Setup mock DB data
    mock_db.estimated_1rm_history[f"{user_id}_{exercise_id}"] = {'estimated_1rm': 100.0, 'calculated_at': datetime.now(timezone.utc)}
    mock_db.workouts['completed_workout_id'] = {
        'id': 'completed_workout_id', 'user_id': user_id, 'completed_at': datetime.now(timezone.utc) - timedelta(days=1),
        'sleep_hours': 7.0, 'stress_level': 3, 'hrv_ms': 55.0
    }
    # Ensure user data in mock_db.users[user_id] has goal_slider, rir_bias, available_plates
    mock_db.users[user_id].update({
        'goal_slider': 0.5, 'rir_bias': 0.1,
        'available_plates': {'plates_kg': [20,10,5,2.5,1.25], 'barbell_weight_kg': 20.0}
    })


    # Configure mock return values
    mock_calc_training_params.return_value = {
        'load_percentage_of_1rm': 0.75, 'target_rir_float': 2.0, 'rest_seconds': 120,
        'rep_range_low': 8, 'rep_range_high': 12, 'target_rir': 2
    }
    # calculate_readiness_multiplier now returns (multiplier, score)
    mock_readiness_multiplier = 0.95
    mock_readiness_total_score = 0.2 # Example score that might lead to 0.95 multiplier: 0.93 + 0.14*S = 0.95 -> 0.14S = 0.02 -> S = 0.02/0.14 approx 0.14
    # Let's use a score that's easier to verify: if score is 0.5, mult = 0.93 + 0.14*0.5 = 0.93 + 0.07 = 1.0
    # If score is (0.95-0.93)/0.14 = 0.02/0.14 approx 0.1428
    mock_readiness_total_score_for_0_95_mult = (0.95 - 0.93) / 0.14
    mock_calc_readiness.return_value = (mock_readiness_multiplier, mock_readiness_total_score_for_0_95_mult)

    mock_round_plates.side_effect = lambda target_weight_kg, **kwargs: round(target_weight_kg * 2) / 2.0 # Simple rounding
    mock_calc_fatigue.return_value = 0.0 # Assuming no fatigue for this test


    response = client.get(f"/v1/users/{user_id}/exercises/{exercise_id}/recommend-set-parameters", headers=auth_headers)

    assert response.status_code == 200
    data = response.json

    assert 'recommended_weight_kg' in data
    assert 'target_reps_low' in data
    assert 'target_reps_high' in data
    assert 'target_rir' in data
    assert 'explanation' in data
    assert 'readiness_score_percent' in data # New field

    mock_calc_training_params.assert_called_once()
    mock_calc_readiness.assert_called_once()
    mock_round_plates.assert_called_once()

    # Verify readiness multiplier was called with expected data
    readiness_args = mock_calc_readiness.call_args[0]
    assert readiness_args[0] == 7.0 # sleep_h
    assert readiness_args[1] == 3   # stress_lvl
    assert readiness_args[2] == 55.0 # hrv_ms
    assert str(readiness_args[3]) == user_id # user_id (ensure UUID if that's what readiness expects)
    # readiness_args[4] is db_conn

    # Rough check of weight application (exact value depends on complex internal calcs)
    # Base weight: 100kg * (1 - 0.0333 * (10 + (2.0-0.1))) approx 100 * (1 - 0.0333 * 11.9) = 100 * (1-0.396) = 60.4kg
    # After readiness (0.95): 60.4 * 0.95 = 57.38kg. Rounded: 57.5kg
    # This is a conceptual check; the actual values depend on the precise mocked logic.
    # The key is that the mocks are called and the structure is correct.
    # Example: if init_weight = 60, readiness=0.95, then 57. Rounded to 57.0 or 57.5
    assert data['recommended_weight_kg'] is not None
    assert "Readiness adj: 0.950" in data['explanation']
    assert data['readiness_score_percent'] == round(mock_readiness_total_score_for_0_95_mult * 100)


@patch('engine.blueprints.workouts.calculate_training_params')
@patch('engine.blueprints.workouts.calculate_readiness_multiplier')
@patch('engine.blueprints.workouts.round_to_available_plates')
@patch('engine.blueprints.workouts.calculate_current_fatigue')
def test_recommend_set_parameters_no_readiness_data(
    mock_calc_fatigue, mock_round_plates, mock_calc_readiness, mock_calc_training_params,
    client, auth_headers, registered_user, test_exercise, mock_db
):
    user_id = registered_user['id']
    exercise_id = test_exercise['id']
    mock_db.estimated_1rm_history[f"{user_id}_{exercise_id}"] = {'estimated_1rm': 100.0}
    # Ensure no completed workouts with readiness data by clearing workouts or specific fields
    mock_db.workouts.clear() # Or ensure 'completed_workout_id' is not set up with sleep/stress

    mock_calc_training_params.return_value = {'rep_range_low': 8, 'rep_range_high': 12, 'target_rir': 2, 'target_rir_float': 2.0}
    mock_round_plates.side_effect = lambda target_weight_kg, **kwargs: round(target_weight_kg)
    mock_calc_fatigue.return_value = 0.0

    # Simulate scenario where calculate_readiness_multiplier is called but determines a neutral/default state
    # This happens if latest_workout_readiness_data is None or essential fields (sleep/stress) are missing.
    # The function calculate_readiness_multiplier itself would return (1.0, some_score_that_results_in_1.0_mult)
    # For example, if total_score = (1.0 - MULTIPLIER_BASE) / MULTIPLIER_RANGE
    # MULTIPLIER_BASE = 0.93, MULTIPLIER_RANGE = 0.14
    # (1.0 - 0.93) / 0.14 = 0.07 / 0.14 = 0.5
    neutral_score_for_1_0_mult = 0.5
    if (0.93 + 0.14 * 0.5) != 1.0: # Adjust if constants changed
        neutral_score_for_1_0_mult = (1.0 - 0.93) / 0.14 if 0.14 != 0 else 0.5 # Avoid div by zero

    mock_calc_readiness.return_value = (1.0, neutral_score_for_1_0_mult)


    response = client.get(f"/v1/users/{user_id}/exercises/{exercise_id}/recommend-set-parameters", headers=auth_headers)
    assert response.status_code == 200
    data = response.json

    # In this scenario (no workout data), calculate_readiness_multiplier is NOT called.
    # readiness_total_score remains None.
    mock_calc_readiness.assert_not_called()
    assert "No recent readiness data for adjustment." in data['explanation']
    assert data['readiness_score_percent'] is None
    # Weight should not be adjusted by readiness factor other than 1.0

@patch('engine.blueprints.workouts.calculate_training_params')
@patch('engine.blueprints.workouts.calculate_readiness_multiplier')
@patch('engine.blueprints.workouts.round_to_available_plates')
@patch('engine.blueprints.workouts.calculate_current_fatigue')
def test_recommend_set_parameters_no_e1rm_history(
    mock_calc_fatigue, mock_round_plates, mock_calc_readiness, mock_calc_training_params,
    client, auth_headers, registered_user, test_exercise, mock_db
):
    user_id = registered_user['id']
    exercise_id = test_exercise['id']
    # Ensure no e1RM history for this user/exercise in mock_db.estimated_1rm_history
    if f"{user_id}_{exercise_id}" in mock_db.estimated_1rm_history:
        del mock_db.estimated_1rm_history[f"{user_id}_{exercise_id}"]

    response = client.get(f"/v1/users/{user_id}/exercises/{exercise_id}/recommend-set-parameters", headers=auth_headers)
    assert response.status_code == 200 # Endpoint handles this as a valid case with specific message
    data = response.json
    assert "No performance history found" in data['message']
    assert data['recommended_weight_kg'] is None

def test_recommend_set_parameters_unauthorized(client, auth_headers, registered_user, test_exercise):
    other_user_id = str(uuid.uuid4()) # Different user
    exercise_id = test_exercise['id']

    response = client.get(f"/v1/users/{other_user_id}/exercises/{exercise_id}/recommend-set-parameters", headers=auth_headers)
    assert response.status_code == 403 # Forbidden
    assert "Forbidden" in response.json['error']

@patch('engine.blueprints.workouts.calculate_training_params')
@patch('engine.blueprints.workouts.calculate_readiness_multiplier')
@patch('engine.blueprints.workouts.round_to_available_plates')
@patch('engine.blueprints.workouts.calculate_current_fatigue')
def test_recommend_set_parameters_significant_fatigue(
    mock_calc_fatigue, mock_round_plates, mock_calc_readiness, mock_calc_training_params,
    client, auth_headers, registered_user, test_exercise, mock_db
):
    user_id = registered_user['id']
    exercise_id = test_exercise['id']
    exercise_muscle_group = mock_db.exercises[exercise_id]['main_target_muscle_group']

    mock_db.estimated_1rm_history[f"{user_id}_{exercise_id}"] = {'estimated_1rm': 100.0}
    # Simulate session history leading to high fatigue
    mock_db.fatigue_session_history[f"{user_id}_{exercise_muscle_group}"] = [
        {'session_date': datetime.now(timezone.utc) - timedelta(days=1), 'stimulus': 300.0}, # High stimulus
        {'session_date': datetime.now(timezone.utc) - timedelta(days=2), 'stimulus': 250.0}  # High stimulus
    ]
    # Mock user data (already set in fixture or previous tests, ensure it's what you want)
    mock_db.users[user_id].update({'goal_slider': 0.5, 'rir_bias': 0.0})


    mock_calc_training_params.return_value = {'rep_range_low': 8, 'rep_range_high': 12, 'target_rir': 2, 'target_rir_float': 2.0}
    mock_calc_readiness.return_value = 1.0 # Neutral readiness for this test
    mock_round_plates.side_effect = lambda target_weight_kg, **kwargs: round(target_weight_kg * 2) / 2.0

    # Mock calculate_current_fatigue to return a high fatigue score
    # MAX_REASONABLE_FATIGUE_SCORE = 500.0, MAX_FATIGUE_REDUCTION_PERCENT = 0.20
    # If fatigue_score = 500, fatigue_effect = 1.0, multiplier = 1.0 - 0.20 = 0.80
    # If fatigue_score = 250, fatigue_effect = 0.5, multiplier = 1.0 - (0.5*0.20) = 1.0 - 0.10 = 0.90
    high_fatigue_score = 250.0
    mock_calc_fatigue.return_value = high_fatigue_score

    response = client.get(f"/v1/users/{user_id}/exercises/{exercise_id}/recommend-set-parameters", headers=auth_headers)
    assert response.status_code == 200
    data = response.json

    mock_calc_fatigue.assert_called_once()
    assert f"Fatigue adj: {0.900:.3f}" in data['explanation'] # 1.0 - (250/500 * 0.20) = 0.90

    # Conceptual check: weight should be reduced by ~10% due to fatigue_multiplier of 0.90
    # Initial weight (from previous test, roughly): 60.4kg
    # After fatigue (0.90) and readiness (1.0): 60.4 * 0.90 = 54.36kg. Rounded: 54.5kg
    # Verify this logic aligns with the actual calculation in the endpoint.
    # The key is that the weight is less than if fatigue_multiplier was 1.0.

    # Calculate expected pre-adjustment weight (from test_recommend_set_parameters_success)
    # target_reps = 10, effective_rir_for_calc = 2.0 (if bias 0) -> total_reps_for_e1rm = 12
    # denominator = 1 - (0.0333 * 12) = 1 - 0.3996 = 0.6004
    # weight_pre_adjust = 100.0 * 0.6004 = 60.04
    # weight_post_fatigue = 60.04 * 0.90 = 54.036
    # weight_post_readiness = 54.036 * 1.0 = 54.036
    # rounded = round(54.036 * 2)/2 = round(108.072)/2 = 108/2 = 54.0 (if mock_round_plates was just round())
    # With mock_round_plates.side_effect = lambda target_weight_kg, **kwargs: round(target_weight_kg * 2) / 2.0
    # rounded = round(54.036 * 2)/2 = round(108.072)/2 = 108.0/2 = 54.0
    # This seems off, let's re-check the rounding from previous test.
    # Previous test: 60.4 * 0.95 = 57.38kg. Rounded: 57.5kg. This implies round(X*2)/2.0
    # So, 54.036 -> 54.0
    assert data['recommended_weight_kg'] == pytest.approx(54.0)


@patch('engine.blueprints.workouts.calculate_training_params')
@patch('engine.blueprints.workouts.calculate_readiness_multiplier')
@patch('engine.blueprints.workouts.round_to_available_plates')
@patch('engine.blueprints.workouts.calculate_current_fatigue')
def test_recommend_set_parameters_no_session_history(
    mock_calc_fatigue, mock_round_plates, mock_calc_readiness, mock_calc_training_params,
    client, auth_headers, registered_user, test_exercise, mock_db
):
    user_id = registered_user['id']
    exercise_id = test_exercise['id']
    exercise_muscle_group = mock_db.exercises[exercise_id]['main_target_muscle_group']

    mock_db.estimated_1rm_history[f"{user_id}_{exercise_id}"] = {'estimated_1rm': 100.0}
    # Ensure no session history for fatigue calculation
    mock_db.fatigue_session_history[f"{user_id}_{exercise_muscle_group}"] = []
    mock_db.users[user_id].update({'goal_slider': 0.5, 'rir_bias': 0.0})


    mock_calc_training_params.return_value = {'rep_range_low': 8, 'rep_range_high': 12, 'target_rir': 2, 'target_rir_float': 2.0}
    mock_calc_readiness.return_value = 1.0 # Neutral readiness
    mock_round_plates.side_effect = lambda target_weight_kg, **kwargs: round(target_weight_kg * 2) / 2.0
    mock_calc_fatigue.return_value = 0.0 # No history means 0 fatigue score

    response = client.get(f"/v1/users/{user_id}/exercises/{exercise_id}/recommend-set-parameters", headers=auth_headers)
    assert response.status_code == 200
    data = response.json

    mock_calc_fatigue.assert_called_once()
    # Check that fatigue explanation part is NOT there or indicates low/no fatigue
    # The current logic adds "Fatigue adj: 1.000 (score: 0.0)." if it's calculated.
    # If fatigue_multiplier is 1.0, it doesn't add to explanation_parts.
    # The code `if abs(fatigue_multiplier - 1.0) > 0.005:` controls this.
    # So, if fatigue score is 0, multiplier is 1.0, no fatigue explanation added.
    assert "Fatigue adj" not in data['explanation']

    # Expected weight without fatigue or readiness adjustment (using simplified Epley from previous test)
    # weight_pre_adjust = 60.04
    # rounded = round(60.04 * 2)/2 = 60.0
    assert data['recommended_weight_kg'] == pytest.approx(60.0)
