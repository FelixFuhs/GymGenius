import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from engine.readiness import get_personal_hrv_baseline, calculate_readiness_multiplier
# Constants from readiness module for assertion checks
from engine.readiness import SLEEP_TARGET_HOURS, STRESS_MAX_LEVEL, SLEEP_WEIGHT, STRESS_WEIGHT, HRV_WEIGHT, MULTIPLIER_BASE, MULTIPLIER_RANGE

# --- Tests for get_personal_hrv_baseline ---

@pytest.fixture
def mock_db_conn():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = conn.cursor_instance # for 'with conn.cursor() as cur:'
    return conn

def test_get_hrv_baseline_success(mock_db_conn):
    user_id = uuid.uuid4()
    mock_cursor = mock_db_conn.cursor_instance
    mock_cursor.fetchone.return_value = {'avg_hrv': 55.5}

    avg_hrv = get_personal_hrv_baseline(user_id, mock_db_conn)

    mock_cursor.execute.assert_called_once()
    assert avg_hrv == pytest.approx(55.5)

def test_get_hrv_baseline_no_data(mock_db_conn):
    user_id = uuid.uuid4()
    mock_cursor = mock_db_conn.cursor_instance
    mock_cursor.fetchone.return_value = {'avg_hrv': None} # No average calculated by DB

    avg_hrv = get_personal_hrv_baseline(user_id, mock_db_conn)

    assert avg_hrv is None

def test_get_hrv_baseline_no_records_found(mock_db_conn): # Simulates query returning no rows
    user_id = uuid.uuid4()
    mock_cursor = mock_db_conn.cursor_instance
    mock_cursor.fetchone.return_value = None

    avg_hrv = get_personal_hrv_baseline(user_id, mock_db_conn)

    assert avg_hrv is None

def test_get_hrv_baseline_db_error(mock_db_conn):
    user_id = uuid.uuid4()
    mock_cursor = mock_db_conn.cursor_instance
    mock_cursor.execute.side_effect = Exception("DB error") # Simulate a generic DB error

    avg_hrv = get_personal_hrv_baseline(user_id, mock_db_conn)
    assert avg_hrv is None # Should gracefully handle error and return None


# --- Tests for calculate_readiness_multiplier ---

@patch('engine.readiness.get_personal_hrv_baseline') # Mock the baseline function
def test_calculate_readiness_all_optimal(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock() # db_conn is passed to get_personal_hrv_baseline

    mock_get_baseline.return_value = 50.0 # Personal avg HRV

    sleep_h = 8.0
    stress_lvl = 1
    hrv_ms = 50.0 # Current HRV matches baseline

    # Expected contributions:
    # Sleep: min(1, 8/8)*0.4 = 0.4
    # Stress: ( (10-1)/(10-1) )*0.3 = 1*0.3 = 0.3
    # HRV: min(1, 50/50)*0.3 = 0.3
    # Total score = 0.4 + 0.3 + 0.3 = 1.0
    # Multiplier = 0.93 + (0.14 * 1.0) = 1.07
    expected_total_score = 1.0

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)

    mock_get_baseline.assert_called_once_with(user_id, mock_db_conn)
    assert multiplier == pytest.approx(MULTIPLIER_BASE + MULTIPLIER_RANGE * expected_total_score)
    assert score == pytest.approx(expected_total_score)

@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_all_poor(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()

    mock_get_baseline.return_value = 50.0

    sleep_h = 0.0
    stress_lvl = 10
    hrv_ms = 25.0 # Significantly lower than baseline

    # Expected contributions:
    # Sleep: min(1, 0/8)*0.4 = 0.0
    # Stress: ( (10-10)/(10-1) )*0.3 = 0*0.3 = 0.0
    # HRV: min(1, 25/50)*0.3 = 0.5*0.3 = 0.15
    # Total score = 0.0 + 0.0 + 0.15 = 0.15
    # Multiplier = 0.93 + (0.14 * 0.15) = 0.93 + 0.021 = 0.951
    expected_total_score = (0.0 * SLEEP_WEIGHT) + \
                           (0.0 * STRESS_WEIGHT) + \
                           (min(1.0, 25.0/50.0) * HRV_WEIGHT) # 0.15

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    assert score == pytest.approx(expected_total_score)
    assert multiplier == pytest.approx(MULTIPLIER_BASE + MULTIPLIER_RANGE * expected_total_score)


@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_no_hrv_data(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()

    # get_personal_hrv_baseline not called if hrv_ms is None

    sleep_h = 7.0
    stress_lvl = 3
    hrv_ms = None # User didn't provide HRV

    # Expected contributions:
    # Sleep: min(1, 7/8)*0.4 = (7/8)*0.4 = 0.875 * 0.4 = 0.35
    # Stress: ( (10-3)/(10-1) )*0.3 = (7/9)*0.3 approx 0.7777 * 0.3 = 0.23333...
    # HRV: 0.0
    # Total score = 0.35 + 0.23333... = 0.58333...
    # Multiplier = 0.93 + (0.14 * 0.58333...) = 0.93 + 0.081666... = 1.011666...

    multiplier = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)

    mock_get_baseline.assert_not_called()
    expected_sleep_contrib = (7.0 / SLEEP_TARGET_HOURS) * SLEEP_WEIGHT
    expected_stress_contrib = ((STRESS_MAX_LEVEL - stress_lvl) / (STRESS_MAX_LEVEL - 1.0)) * STRESS_WEIGHT
    expected_total_score = expected_sleep_contrib + expected_stress_contrib
    expected_multiplier = MULTIPLIER_BASE + (MULTIPLIER_RANGE * expected_total_score)

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    assert score == pytest.approx(expected_total_score)
    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    assert score == pytest.approx(expected_total_score)
    assert multiplier == pytest.approx(expected_multiplier)

@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_no_hrv_baseline(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()

    mock_get_baseline.return_value = None # No baseline available for user

    sleep_h = 7.0
    stress_lvl = 3
    hrv_ms = 45.0 # User provided HRV, but no baseline to compare

    # Expected contributions (same as no_hrv_data because HRV contribution becomes 0):
    # Sleep: 0.35
    # Stress: 0.23333...
    # HRV: 0.0
    # Total score = 0.58333...
    # Multiplier = 1.011666...

    multiplier = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)

    mock_get_baseline.assert_called_once_with(user_id, mock_db_conn)
    expected_sleep_contrib = (7.0 / SLEEP_TARGET_HOURS) * SLEEP_WEIGHT
    expected_stress_contrib = ((STRESS_MAX_LEVEL - stress_lvl) / (STRESS_MAX_LEVEL - 1.0)) * STRESS_WEIGHT
    expected_total_score = expected_sleep_contrib + expected_stress_contrib # HRV contrib is 0
    expected_multiplier = MULTIPLIER_BASE + (MULTIPLIER_RANGE * expected_total_score)

    assert multiplier == pytest.approx(expected_multiplier)

@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_missing_sleep_and_stress(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()
    mock_get_baseline.return_value = 50.0

    sleep_h = None
    stress_lvl = None
    hrv_ms = 55.0 # Slightly above baseline

    # Expected contributions:
    # Sleep: 0.0
    # Stress: 0.0
    # HRV: min(1, 55/50)*0.3 = 1.0 * 0.3 = 0.3
    # Total score = 0.3
    # Multiplier = 0.93 + (0.14 * 0.3) = 0.93 + 0.042 = 0.972
    expected_total_score = (min(1.0, 55.0/50.0) * HRV_WEIGHT) # 1.0 * 0.3 = 0.3

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    assert score == pytest.approx(expected_total_score)
    assert multiplier == pytest.approx(MULTIPLIER_BASE + MULTIPLIER_RANGE * expected_total_score)

@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_hrv_well_above_baseline(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()
    mock_get_baseline.return_value = 40.0 # Personal avg HRV

    sleep_h = 8.0 # Optimal
    stress_lvl = 1  # Optimal
    hrv_ms = 80.0   # HRV is double baseline, normalized_hrv should cap at 1.0

    # Expected contributions:
    # Sleep: 0.4
    # Stress: 0.3
    # HRV: min(1.0, 80.0/40.0) * 0.3 = 1.0 * 0.3 = 0.3
    # Total score = 1.0
    # Multiplier = 1.07
    expected_total_score = 1.0

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    assert score == pytest.approx(expected_total_score)
    assert multiplier == pytest.approx(MULTIPLIER_BASE + MULTIPLIER_RANGE * expected_total_score)

@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_all_inputs_none(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()

    sleep_h = None
    stress_lvl = None
    hrv_ms = None

    # Expected contributions: All 0.0
    # Total score = 0.0
    # Multiplier = 0.93 + (0.14 * 0.0) = 0.93
    expected_total_score = 0.0

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    mock_get_baseline.assert_not_called() # Because hrv_ms is None
    assert score == pytest.approx(expected_total_score)
    assert multiplier == pytest.approx(MULTIPLIER_BASE + MULTIPLIER_RANGE * expected_total_score)

@patch('engine.readiness.get_personal_hrv_baseline')
def test_calculate_readiness_stress_at_max(mock_get_baseline):
    user_id = uuid.uuid4()
    mock_db_conn = MagicMock()
    mock_get_baseline.return_value = 50.0

    sleep_h = 8.0 # Optimal
    stress_lvl = 10 # Max stress
    hrv_ms = 50.0   # Matches baseline

    # Expected contributions:
    # Sleep: 0.4
    # Stress: ((10-10)/(10-1))*0.3 = 0.0
    # HRV: 0.3
    # Total score = 0.4 + 0.0 + 0.3 = 0.7
    # Multiplier = 0.93 + (0.14 * 0.7) = 0.93 + 0.098 = 1.028
    expected_total_score = (min(1.0, 8.0/SLEEP_TARGET_HOURS) * SLEEP_WEIGHT) + \
                           (((STRESS_MAX_LEVEL - 10.0) / (STRESS_MAX_LEVEL - 1.0)) * STRESS_WEIGHT) + \
                           (min(1.0, 50.0/50.0) * HRV_WEIGHT) # 0.4 + 0 + 0.3 = 0.7

    multiplier, score = calculate_readiness_multiplier(sleep_h, stress_lvl, hrv_ms, user_id, mock_db_conn)
    assert score == pytest.approx(expected_total_score)
    assert multiplier == pytest.approx(MULTIPLIER_BASE + MULTIPLIER_RANGE * expected_total_score)
