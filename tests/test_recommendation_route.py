import uuid
import pytest # Added import for pytest.approx
from datetime import date # For mocking date.today()
from unittest.mock import MagicMock, patch # Added for mocking

from engine.blueprints import analytics as analytics_bp
# Import phase constants for mocking
from engine.mesocycles import PHASE_ACCUMULATION, PHASE_INTENSIFICATION, PHASE_DELOAD


class FakeCursor:
    def __init__(self, user_exists=True, exercise_exists=True, e1rm_history_for_plateau=None, latest_e1rm_record=None):
        self.user_exists = user_exists
        self.exercise_exists = exercise_exists
        self.e1rm_history_for_plateau = e1rm_history_for_plateau if e1rm_history_for_plateau is not None else []
        self.latest_e1rm_record = latest_e1rm_record
        if self.latest_e1rm_record is None:
            self.latest_e1rm_record = {"estimated_1rm": 100.0, "source_weight": 100, "source_reps": 1, "source_rir": 0}
        self.last_query = ""
        self.query_count = 0 # To track order of queries if needed

    def execute(self, query, params=None):
        self.last_query = query
        self.params = params
        self.query_count +=1

    def fetchone(self):
        # print(f"\nDEBUG FakeCursor fetchone: Last query: {self.last_query}, Params: {self.params}")
        if "FROM users" in self.last_query:
            return {
                "goal_slider": 0.5, "rir_bias": 0.0, "recovery_multipliers": {"chest": 1.0},
                "experience_level": "intermediate", "sex": "unknown", "equipment_type": "barbell",
                "equipment_settings": {"available_plates_kg": [1.25, 2.5, 5, 10, 20], "barbell_weight_kg": 20.0}
            } if self.user_exists else None
        if "FROM exercises" in self.last_query:
            return {"name": "Bench Press", "main_target_muscle_group": "chest"} if self.exercise_exists else None

        # This is for the LATEST e1RM for current performance
        if "FROM estimated_1rm_history" in self.last_query and "ORDER BY calculated_at DESC LIMIT 1" in self.last_query:
            return self.latest_e1rm_record

        # This specific mock for get_or_create_current_mesocycle's internal SELECT will be overridden by monkeypatching the function itself.
        # So, we don't strictly need to handle it here if get_or_create_current_mesocycle is mocked directly.
        # However, if it *were* to be called, this indicates a test setup issue or unmocked path.
        if "FROM mesocycles" in self.last_query and "ORDER BY start_date DESC" in self.last_query:
             # This is the fetch for current mesocycle by get_or_create_current_mesocycle
             # This should ideally be mocked directly by mocking get_or_create_current_mesocycle
             # For now, return a default if not handled by a specific test's direct mock of the function
            # print("DEBUG FakeCursor: Returning default meso for initial fetch in get_or_create")
            return {"id": str(uuid.uuid4()), "user_id": self.params[0], "phase": "accumulation", "start_date": date(2024,1,1), "week_number":1}

        return None

    def fetchall(self):
        # print(f"\nDEBUG FakeCursor fetchall: Last query: {self.last_query}, Params: {self.params}")
        if "FROM workout_sets" in self.last_query:
            return []
        if "FROM estimated_1rm_history" in self.last_query and "ORDER BY calculated_at ASC" in self.last_query:
            return self.e1rm_history_for_plateau
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class FakeConn:
    def __init__(self, user_exists=True, exercise_exists=True, e1rm_history_for_plateau=None, latest_e1rm_record=None):
        self.user_exists = user_exists
        self.exercise_exists = exercise_exists
        self.e1rm_history_for_plateau = e1rm_history_for_plateau
        self.latest_e1rm_record = latest_e1rm_record

    def cursor(self, cursor_factory=None):
        return FakeCursor(self.user_exists, self.exercise_exists, self.e1rm_history_for_plateau, self.latest_e1rm_record)

    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


def fake_fatigue(*args, **kwargs): return 5.0

# Default mock user_id for mesocycle, can be overridden in tests if needed
MOCK_USER_ID_FOR_MESO = str(uuid.uuid4())

def call_route(client, monkeypatch, *, user=True, exercise=True, previous_set_data=None,
               e1rm_history_for_plateau=None, latest_e1rm_record=None, mock_meso_details=None):

    test_user_id = uuid.uuid4() # Use a consistent user_id for the route call

    monkeypatch.setattr(analytics_bp, "get_db_connection",
                        lambda: FakeConn(user, exercise, e1rm_history_for_plateau=e1rm_history_for_plateau, latest_e1rm_record=latest_e1rm_record))
    monkeypatch.setattr(analytics_bp, "release_db_connection", lambda conn: None)
    monkeypatch.setattr(analytics_bp, "calculate_current_fatigue", fake_fatigue)
    monkeypatch.setattr(analytics_bp, "calculate_confidence_score", lambda u,e,c: 0.75)

    # Mock get_or_create_current_mesocycle
    default_meso_mock_data = {
        'id': str(uuid.uuid4()), 'user_id': str(test_user_id),
        'phase': PHASE_ACCUMULATION, 'week_number': 1, 'start_date': date.today()
    }
    effective_meso_details_to_return = mock_meso_details if mock_meso_details is not None else default_meso_mock_data

    # Ensure the user_id in the mocked meso details matches the one in the route
    effective_meso_details_to_return['user_id'] = str(test_user_id)

    monkeypatch.setattr(analytics_bp, "get_or_create_current_mesocycle",
                        lambda cur, uid, today_date: effective_meso_details_to_return) # Pass uid to lambda

    # Mock date.today() for consistent results if meso logic depends on it via analytics.py
    monkeypatch.setattr(analytics_bp, "date", MagicMock(today=MagicMock(return_value=date(2024, 1, 15))))


    exercise_id = uuid.uuid4()
    url = f"/v1/user/{test_user_id}/exercise/{exercise_id}/recommend-set-parameters"

    if previous_set_data:
        resp = client.post(url, json=previous_set_data)
    else:
        resp = client.get(url)
    return resp


def test_recommend_success_get(client, monkeypatch):
    resp = call_route(client, monkeypatch, previous_set_data=None)
    assert resp.status_code == 200
    data = resp.get_json()
    expected_fields = [
        "user_id", "exercise_id", "exercise_name", "recommended_weight_kg",
        "explanation", "intra_session_adjustment_details",
        "plateau_analysis_details", "mesocycle_details"
    ]
    for field in expected_fields:
        assert field in data, f"Field {field} missing in response"

    assert data["intra_session_adjustment_details"]["type"] == "none"
    assert data["plateau_analysis_details"]["deload_applied"] == False
    assert data["mesocycle_details"]["phase"] == PHASE_ACCUMULATION # Default from call_route mock
    assert data["mesocycle_details"]["load_modifier_applied"] == 1.0


# --- Tests for intra-session adaptation ---
# (These tests remain unchanged from previous step, confirmed working)
def test_recommend_with_prev_set_decrease(client, monkeypatch):
    prev_metrics = {"previous_set_metrics": {"prev_actual_rir": 0, "prev_target_rir": 2, "prev_weight_lifted": 100.0}}
    resp = call_route(client, monkeypatch, previous_set_data=prev_metrics)
    assert resp.status_code == 200
    data = resp.get_json(); assert data["intra_session_adjustment_details"]["type"] == "decreased"
    assert data["intra_session_adjustment_details"]["to_weight_before_fatigue"] == pytest.approx(95.0)
    assert "intra_adjusted" in data["e1rm_source"]

def test_recommend_with_prev_set_increase(client, monkeypatch):
    prev_metrics = {"previous_set_metrics": {"prev_actual_rir": 4, "prev_target_rir": 2, "prev_weight_lifted": 100.0}}
    resp = call_route(client, monkeypatch, previous_set_data=prev_metrics)
    assert resp.status_code == 200
    data = resp.get_json(); assert data["intra_session_adjustment_details"]["type"] == "increased"
    assert data["intra_session_adjustment_details"]["to_weight_before_fatigue"] == pytest.approx(105.0)
    assert "intra_adjusted" in data["e1rm_source"]

def test_recommend_with_prev_set_no_change(client, monkeypatch):
    prev_metrics = {"previous_set_metrics": {"prev_actual_rir": 2, "prev_target_rir": 2, "prev_weight_lifted": 100.0}}
    resp = call_route(client, monkeypatch, previous_set_data=prev_metrics)
    assert resp.status_code == 200
    data = resp.get_json(); assert data["intra_session_adjustment_details"]["type"] == "none"
    assert data["intra_session_adjustment_details"]["to_weight_before_fatigue"] == pytest.approx(100.0)
    assert "intra_adjusted" in data["e1rm_source"]

def test_recommend_with_invalid_prev_set_metrics(client, monkeypatch):
    prev_metrics = {"previous_set_metrics": {"prev_actual_rir": 0, "prev_target_rir": 2, "prev_weight_lifted": "not_a_float"}}
    resp = call_route(client, monkeypatch, previous_set_data=prev_metrics)
    assert resp.status_code == 200
    data = resp.get_json(); assert data["intra_session_adjustment_details"]["type"] == "none"
    assert data["intra_session_adjustment_details"].get("error") == "Invalid metric types"
    assert "intra_adjusted" not in data["e1rm_source"]

# --- Tests for User/Exercise Not Found ---
def test_recommend_user_missing(client, monkeypatch):
    resp = call_route(client, monkeypatch, user=False)
    assert resp.status_code == 404; assert resp.get_json()["error"] == "User not found"

def test_recommend_exercise_missing(client, monkeypatch):
    resp = call_route(client, monkeypatch, exercise=False)
    assert resp.status_code == 404; assert resp.get_json()["error"] == "Exercise not found"

# --- Tests for Plateau Deload ---
# (These tests remain unchanged from previous step, confirmed working)
def test_recommend_plateau_deload_applied(client, monkeypatch):
    stagnation_history = [{"estimated_1rm": 100.0} for _ in range(10)]
    latest_e1rm_rec = {"estimated_1rm": 100.0, "source_weight": None, "source_reps": None, "source_rir": None}
    resp = call_route(client, monkeypatch, e1rm_history_for_plateau=stagnation_history, latest_e1rm_record=latest_e1rm_rec)
    assert resp.status_code == 200; data = resp.get_json()
    assert data["plateau_analysis_details"]["plateau_detected"] == True
    assert data["plateau_analysis_details"]["deload_applied"] == True
    assert data["plateau_analysis_details"]["original_e1rm"] == pytest.approx(100.0)
    assert data["plateau_analysis_details"]["deloaded_e1rm"] == pytest.approx(90.0)
    assert data["estimated_1rm_kg"] == pytest.approx(90.0)
    assert "_plateau_deload" in data["e1rm_source"]

def test_recommend_no_plateau_progression(client, monkeypatch):
    progression_history = [{"estimated_1rm": 90.0 + i*2.5} for i in range(10)]
    latest_e1rm_val = progression_history[-1]["estimated_1rm"]
    latest_e1rm_rec = {"estimated_1rm": latest_e1rm_val, "source_weight": None, "source_reps": None, "source_rir": None}
    resp = call_route(client, monkeypatch, e1rm_history_for_plateau=progression_history, latest_e1rm_record=latest_e1rm_rec)
    assert resp.status_code == 200; data = resp.get_json()
    assert data["plateau_analysis_details"]["plateau_detected"] == False
    assert data["plateau_analysis_details"]["deload_applied"] == False
    assert data["estimated_1rm_kg"] == pytest.approx(latest_e1rm_val)
    assert "_plateau_deload" not in data["e1rm_source"]

def test_recommend_insufficient_history_for_plateau(client, monkeypatch):
    short_history = [{"estimated_1rm": 100.0} for _ in range(3)]
    latest_e1rm_rec = {"estimated_1rm": 100.0, "source_weight": None, "source_reps": None, "source_rir": None}
    resp = call_route(client, monkeypatch, e1rm_history_for_plateau=short_history, latest_e1rm_record=latest_e1rm_rec)
    assert resp.status_code == 200; data = resp.get_json()
    assert data["plateau_analysis_details"]["plateau_detected"] == False
    assert data["plateau_analysis_details"]["deload_applied"] == False
    assert data["plateau_analysis_details"]["reason_no_plateau_check"] == "Insufficient history"
    assert data["estimated_1rm_kg"] == pytest.approx(100.0)
    assert "_plateau_deload" not in data["e1rm_source"]

# --- Tests for Mesocycle Load Modification ---

def test_recommend_intensification_phase_modifier(client, monkeypatch):
    latest_e1rm_rec = {"estimated_1rm": 100.0, "source_weight": None, "source_reps": None, "source_rir": None}
    # Use a fixed date for "today" in the test to match the meso start_date for simplicity in mock
    fixed_today = date(2024, 1, 15)
    meso_details_intens = {
        'id': str(uuid.uuid4()), 'user_id': MOCK_USER_ID_FOR_MESO, # User ID in meso_details should match route's user_id
        'phase': PHASE_INTENSIFICATION, 'week_number': 1, 'start_date': fixed_today
    }
    with patch.object(analytics_bp, 'date') as mock_date: # Mock date.today() call in analytics_bp
        mock_date.today.return_value = fixed_today
        resp = call_route(client, monkeypatch, latest_e1rm_record=latest_e1rm_rec, mock_meso_details=meso_details_intens)

    assert resp.status_code == 200
    data = resp.get_json()

    assert data["mesocycle_details"]["phase"] == PHASE_INTENSIFICATION
    assert data["mesocycle_details"]["load_modifier_applied"] == pytest.approx(1.02)
    assert data["estimated_1rm_kg"] == pytest.approx(100.0 * 1.02)
    assert "_meso_intensification" in data["e1rm_source"]

def test_recommend_deload_phase_modifier(client, monkeypatch):
    latest_e1rm_rec = {"estimated_1rm": 100.0, "source_weight": None, "source_reps": None, "source_rir": None}
    fixed_today = date(2024, 1, 15)
    meso_details_deload = {
        'id': str(uuid.uuid4()), 'user_id': MOCK_USER_ID_FOR_MESO,
        'phase': PHASE_DELOAD, 'week_number': 1, 'start_date': fixed_today
    }
    with patch.object(analytics_bp, 'date') as mock_date:
        mock_date.today.return_value = fixed_today
        resp = call_route(client, monkeypatch, latest_e1rm_record=latest_e1rm_rec, mock_meso_details=meso_details_deload)

    assert resp.status_code == 200
    data = resp.get_json()

    assert data["mesocycle_details"]["phase"] == PHASE_DELOAD
    assert data["mesocycle_details"]["load_modifier_applied"] == pytest.approx(0.90)
    assert data["estimated_1rm_kg"] == pytest.approx(100.0 * 0.90)
    assert "_meso_deload" in data["e1rm_source"]

def test_recommend_accumulation_phase_no_modifier(client, monkeypatch):
    latest_e1rm_rec = {"estimated_1rm": 100.0, "source_weight": None, "source_reps": None, "source_rir": None}
    fixed_today = date(2024, 1, 15)
    # call_route default mock is accumulation
    meso_details_accum = {
        'id': str(uuid.uuid4()), 'user_id': MOCK_USER_ID_FOR_MESO,
        'phase': PHASE_ACCUMULATION, 'week_number': 1, 'start_date': fixed_today
    }
    with patch.object(analytics_bp, 'date') as mock_date:
        mock_date.today.return_value = fixed_today
        resp = call_route(client, monkeypatch, latest_e1rm_record=latest_e1rm_rec, mock_meso_details=meso_details_accum)

    assert resp.status_code == 200
    data = resp.get_json()

    assert data["mesocycle_details"]["phase"] == PHASE_ACCUMULATION
    assert data["mesocycle_details"]["load_modifier_applied"] == pytest.approx(1.0)
    assert data["estimated_1rm_kg"] == pytest.approx(100.0)
    assert "_meso_accumulation" not in data["e1rm_source"] # No specific tag for accumulation 1.0 modifier
    assert "_meso_intensification" not in data["e1rm_source"]
    assert "_meso_deload" not in data["e1rm_source"]
