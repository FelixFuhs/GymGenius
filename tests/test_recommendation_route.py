import uuid

from engine.app import app


class FakeCursor:
    def __init__(self, user_exists=True, exercise_exists=True):
        self.user_exists = user_exists
        self.exercise_exists = exercise_exists
        self.last_query = ""

    def execute(self, query, params=None):
        self.last_query = query
        self.params = params

    def fetchone(self):
        if "FROM users" in self.last_query:
            return {
                "goal_slider": 0.5,
                "rir_bias": 0.0,
                "recovery_multipliers": {"chest": 1.0},
            } if self.user_exists else None
        if "FROM exercises" in self.last_query:
            return {
                "name": "Bench Press",
                "main_target_muscle_group": "chest",
            } if self.exercise_exists else None
        if "FROM estimated_1rm_history" in self.last_query:
            return {"estimated_1rm": 100.0}
        return None

    def fetchall(self):
        if "FROM workout_sets" in self.last_query:
            return []
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class FakeConn:
    def __init__(self, user_exists=True, exercise_exists=True):
        self.user_exists = user_exists
        self.exercise_exists = exercise_exists

    def cursor(self, cursor_factory=None):
        return FakeCursor(self.user_exists, self.exercise_exists)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def fake_fatigue(*args, **kwargs):
    return 5.0


def call_route(client, monkeypatch, *, user=True, exercise=True):
    monkeypatch.setattr(app, "get_db_connection", lambda: FakeConn(user, exercise))
    monkeypatch.setattr(app, "calculate_current_fatigue", fake_fatigue)
    user_id = uuid.uuid4()
    exercise_id = uuid.uuid4()
    resp = client.get(
        f"/v1/user/{user_id}/exercise/{exercise_id}/recommend-set-parameters"
    )
    return resp


def test_recommend_success(client, monkeypatch):
    resp = call_route(client, monkeypatch)
    assert resp.status_code == 200
    data = resp.get_json()
    for field in [
        "user_id",
        "exercise_id",
        "exercise_name",
        "recommended_weight_kg",
        "explanation",
    ]:
        assert field in data


def test_recommend_user_missing(client, monkeypatch):
    resp = call_route(client, monkeypatch, user=False)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "User not found"


def test_recommend_exercise_missing(client, monkeypatch):
    resp = call_route(client, monkeypatch, exercise=False)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Exercise not found"
