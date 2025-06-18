import unittest
from unittest.mock import MagicMock, call, patch
import uuid
from datetime import date, timedelta

from engine.mesocycles import get_or_create_current_mesocycle, PHASE_ACCUMULATION, PHASE_INTENSIFICATION, PHASE_DELOAD, PHASE_DURATIONS

class TestGetOrCreateCurrentMesocycle(unittest.TestCase):

    def setUp(self):
        self.mock_cursor = MagicMock(spec=['execute', 'fetchone'])
        self.user_id = str(uuid.uuid4())
        self.today = date(2024, 1, 15)

    def _assert_insert_params(self, captured_params_holder, expected_id, expected_phase, expected_start_date, expected_week_number):
        inserted_params = captured_params_holder.get('params_tuple')
        self.assertIsNotNone(inserted_params, "INSERT call was not captured or params not stored")
        self.assertEqual(inserted_params[0], expected_id, "Inserted ID mismatch")
        self.assertEqual(inserted_params[1], self.user_id, "Inserted user_id mismatch")
        self.assertEqual(inserted_params[2], expected_phase, "Inserted phase mismatch")
        self.assertEqual(inserted_params[3], expected_start_date, "Inserted start_date mismatch")
        self.assertEqual(inserted_params[4], expected_week_number, "Inserted week_number mismatch")

    def test_no_existing_mesocycle_creates_new_accumulation_week1(self):
        expected_new_id_obj = uuid.uuid4()
        expected_new_id_str = str(expected_new_id_obj)

        captured_insert_params_holder = {}
        def execute_side_effect(query, params):
            if "INSERT INTO mesocycles" in query:
                self.assertEqual(params[0], expected_new_id_str)
                captured_insert_params_holder['params_tuple'] = params
        self.mock_cursor.execute.side_effect = execute_side_effect

        # SUT calls fetchone once (initial check), returns None.
        # Then INSERTs, then constructs and returns dict directly.
        self.mock_cursor.fetchone.return_value = None

        with patch('uuid.uuid4', return_value=expected_new_id_obj):
            meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_ACCUMULATION)
        self.assertEqual(meso['week_number'], 1)
        self.assertEqual(meso['start_date'], self.today)
        self.assertEqual(meso['id'], expected_new_id_str)
        self._assert_insert_params(captured_insert_params_holder, expected_new_id_str, PHASE_ACCUMULATION, self.today, 1)


    def test_existing_accumulation_week1_today_is_same_week(self):
        initial_meso_id = str(uuid.uuid4())
        start_date = self.today - timedelta(days=3)
        self.mock_cursor.fetchone.return_value = {
            'id': initial_meso_id, 'user_id': self.user_id, 'phase': PHASE_ACCUMULATION,
            'week_number': 1, 'start_date': start_date
        }
        self.mock_cursor.execute.side_effect = None

        meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_ACCUMULATION)
        self.assertEqual(meso['week_number'], 1)
        self.assertEqual(meso['start_date'], start_date)
        self.assertEqual(meso['id'], initial_meso_id)
        update_called = any("UPDATE mesocycles" in c.args[0] for c in self.mock_cursor.execute.call_args_list if c)
        self.assertFalse(update_called)


    def test_existing_accumulation_week1_today_is_next_week(self):
        initial_meso_id = str(uuid.uuid4())
        start_date = self.today - timedelta(weeks=1)
        self.mock_cursor.fetchone.return_value = {
            'id': initial_meso_id, 'user_id': self.user_id, 'phase': PHASE_ACCUMULATION,
            'week_number': 1, 'start_date': start_date
        }
        self.mock_cursor.execute.side_effect = None

        meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_ACCUMULATION)
        self.assertEqual(meso['week_number'], 2)
        self.assertEqual(meso['start_date'], start_date)
        self.assertEqual(meso['id'], initial_meso_id)
        self.mock_cursor.execute.assert_any_call(
            "UPDATE mesocycles SET phase = %s, week_number = %s, start_date = %s WHERE id = %s",
            (PHASE_ACCUMULATION, 2, start_date, initial_meso_id)
        )

    def test_transition_accumulation_to_intensification(self):
        initial_meso_id = str(uuid.uuid4())
        start_date_acc = self.today - timedelta(weeks=PHASE_DURATIONS[PHASE_ACCUMULATION])
        self.mock_cursor.fetchone.return_value = {
            'id': initial_meso_id, 'user_id': self.user_id, 'phase': PHASE_ACCUMULATION,
            'week_number': PHASE_DURATIONS[PHASE_ACCUMULATION], 'start_date': start_date_acc
        }
        self.mock_cursor.execute.side_effect = None

        expected_intensification_start_date = start_date_acc + timedelta(weeks=PHASE_DURATIONS[PHASE_ACCUMULATION])

        meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_INTENSIFICATION)
        self.assertEqual(meso['week_number'], 1)
        self.assertEqual(meso['start_date'], expected_intensification_start_date)
        self.assertEqual(meso['id'], initial_meso_id)
        self.mock_cursor.execute.assert_any_call(
            "UPDATE mesocycles SET phase = %s, week_number = %s, start_date = %s WHERE id = %s",
            (PHASE_INTENSIFICATION, 1, expected_intensification_start_date, initial_meso_id)
        )

    def test_transition_intensification_to_deload(self):
        initial_meso_id = str(uuid.uuid4())
        start_date_int = self.today - timedelta(weeks=PHASE_DURATIONS[PHASE_INTENSIFICATION])
        self.mock_cursor.fetchone.return_value = {
            'id': initial_meso_id, 'user_id': self.user_id, 'phase': PHASE_INTENSIFICATION,
            'week_number': PHASE_DURATIONS[PHASE_INTENSIFICATION], 'start_date': start_date_int
        }
        self.mock_cursor.execute.side_effect = None
        expected_deload_start_date = start_date_int + timedelta(weeks=PHASE_DURATIONS[PHASE_INTENSIFICATION])

        meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_DELOAD)
        self.assertEqual(meso['week_number'], 1)
        self.assertEqual(meso['start_date'], expected_deload_start_date)
        self.assertEqual(meso['id'], initial_meso_id)
        self.mock_cursor.execute.assert_any_call(
            "UPDATE mesocycles SET phase = %s, week_number = %s, start_date = %s WHERE id = %s",
            (PHASE_DELOAD, 1, expected_deload_start_date, initial_meso_id)
        )

    def test_transition_deload_to_new_accumulation_cycle(self):
        initial_meso_id_old = str(uuid.uuid4())
        start_date_del = self.today - timedelta(weeks=PHASE_DURATIONS[PHASE_DELOAD])
        expected_new_accumulation_start_date = start_date_del + timedelta(weeks=PHASE_DURATIONS[PHASE_DELOAD])

        new_id_obj = uuid.uuid4()
        new_id_str = str(new_id_obj)

        captured_insert_params = {}
        def execute_side_effect(query, params):
            if "INSERT INTO mesocycles" in query:
                self.assertEqual(params[0], new_id_str)
                captured_insert_params['params_tuple'] = params
        self.mock_cursor.execute.side_effect = execute_side_effect

        # SUT calls fetchone once (initial SELECT), then INSERTs, then returns constructed dict.
        self.mock_cursor.fetchone.return_value = {
            'id': initial_meso_id_old, 'user_id': self.user_id, 'phase': PHASE_DELOAD,
            'week_number': PHASE_DURATIONS[PHASE_DELOAD], 'start_date': start_date_del
        }

        with patch('uuid.uuid4', return_value=new_id_obj):
            meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_ACCUMULATION)
        self.assertEqual(meso['week_number'], 1)
        self.assertEqual(meso['start_date'], expected_new_accumulation_start_date)
        self.assertEqual(meso['id'], new_id_str)

        self._assert_insert_params(captured_insert_params, new_id_str, PHASE_ACCUMULATION, expected_new_accumulation_start_date, 1)


    def test_long_time_passed_multiple_transitions(self):
        initial_meso_id_old = str(uuid.uuid4())
        start_date_very_old_acc = self.today - timedelta(weeks=6)

        new_id_obj_long = uuid.uuid4()
        new_id_str_long = str(new_id_obj_long)

        expected_new_cycle_start_date = start_date_very_old_acc + timedelta(weeks=PHASE_DURATIONS[PHASE_ACCUMULATION] + PHASE_DURATIONS[PHASE_INTENSIFICATION] + PHASE_DURATIONS[PHASE_DELOAD])
        expected_week_in_new_cycle = ((self.today - expected_new_cycle_start_date).days // 7) + 1

        captured_insert_params_long = {}
        def execute_side_effect_long(query, params):
            if "INSERT INTO mesocycles" in query:
                self.assertEqual(params[0], new_id_str_long)
                captured_insert_params_long['params_tuple'] = params
        self.mock_cursor.execute.side_effect = execute_side_effect_long

        # SUT calls fetchone once (initial SELECT), then INSERTs, then returns constructed dict.
        self.mock_cursor.fetchone.return_value = {
            'id': initial_meso_id_old, 'user_id': self.user_id, 'phase': PHASE_ACCUMULATION,
            'week_number': 1, 'start_date': start_date_very_old_acc
        }

        with patch('uuid.uuid4', return_value=new_id_obj_long):
            meso = get_or_create_current_mesocycle(self.mock_cursor, self.user_id, self.today)

        self.assertEqual(meso['phase'], PHASE_ACCUMULATION)
        self.assertEqual(meso['week_number'], expected_week_in_new_cycle)
        self.assertEqual(meso['start_date'], expected_new_cycle_start_date)
        self.assertEqual(meso['id'], new_id_str_long)

        self._assert_insert_params(captured_insert_params_long, new_id_str_long, PHASE_ACCUMULATION, expected_new_cycle_start_date, expected_week_in_new_cycle)


if __name__ == '__main__':
    unittest.main()
