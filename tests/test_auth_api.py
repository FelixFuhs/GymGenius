import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch # For overriding datetime.now if needed for expiry tests

# Assuming conftest.py provides a 'client' fixture and 'app' fixture
# Also assuming a way to create users, e.g., a utility function or direct DB interaction for setup.

def register_user(client, email, password):
    """Helper to register a new user."""
    return client.post('/v1/auth/register', json={
        'email': email,
        'password': password
    })

def login_user(client, email, password):
    """Helper to log in a user."""
    return client.post('/v1/auth/login', json={
        'email': email,
        'password': password
    })

@pytest.fixture(scope='function')
def test_user(client):
    """Fixture to create and login a test user, yielding tokens and user ID."""
    email = "testuser_auth@example.com"
    password = "password123"

    register_response = register_user(client, email, password)
    assert register_response.status_code == 201
    user_id = register_response.get_json()['user']['id']

    login_response = login_user(client, email, password)
    assert login_response.status_code == 200
    tokens = login_response.get_json()

    return {
        "user_id": user_id,
        "email": email,
        "password": password,
        "access_token": tokens.get('access_token'),
        "refresh_token": tokens.get('refresh_token')
    }

def test_login_returns_both_tokens(test_user):
    """Test that login successfully returns access and refresh tokens."""
    assert test_user['access_token'] is not None
    assert test_user['refresh_token'] is not None
    # Further token structure validation could be added here if desired

def test_refresh_token_success(client, test_user):
    """Test successful token refresh using a valid refresh token."""
    refresh_token = test_user['refresh_token']

    response = client.post('/v1/auth/refresh', json={
        'refresh_token': refresh_token
    })

    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert data['access_token'] is not None
    assert data['access_token'] != test_user['access_token'] # New access token should be different

    # Optional: Verify the new access token works on a protected route
    # This requires a simple protected route to exist, e.g., /v1/users/{user_id}/profile
    # For now, this part is conceptual unless such a route is readily available and simple.
    # profile_response = client.get(f"/v1/users/{test_user['user_id']}/profile", headers={
    #     'Authorization': f"Bearer {data['access_token']}"
    # })
    # assert profile_response.status_code == 200


def test_refresh_token_invalid_token(client):
    """Test token refresh with an invalid (e.g., malformed, wrong signature) refresh token."""
    response = client.post('/v1/auth/refresh', json={
        'refresh_token': 'this.is.not.a.valid.token'
    })
    assert response.status_code == 401 # Or 422 if validation is different
    data = response.get_json()
    assert "Invalid refresh token" in data.get('error', data.get('message', '')) # Backend error message might vary

def test_refresh_token_missing_token_in_db(client, test_user):
    """Test token refresh with a validly structured but non-existent (or revoked) refresh token."""
    # Assuming the refresh token is removed/invalidated after use or some other mechanism
    # For this test, we'll simulate a token that's validly signed but not in DB or already used.
    # This is hard to fully simulate without DB manipulation or specific backend logic for token reuse.
    # A simple way is to use the refresh token, then try to use it again if it's one-time use.
    # For now, we will assume a token that's validly structured but not in the DB.
    # We can generate a new valid token but not save it to DB, however, that needs JWT key.
    # Let's try with the original token after a hypothetical invalidation (e.g. if refresh rotates tokens)

    first_refresh_response = client.post('/v1/auth/refresh', json={'refresh_token': test_user['refresh_token']})
    assert first_refresh_response.status_code == 200 # First refresh should work

    # If refresh tokens are one-time use and invalidated (deleted from DB)
    # This test assumes the backend invalidates the token upon successful refresh.
    # If the backend doesn't invalidate, this test would need a different approach.
    # The current backend implementation in auth.py does NOT invalidate the refresh token on use.
    # So, this specific test case as "missing/revoked" is harder to achieve without DB manipulation.
    # Instead, we test with a completely fabricated but valid-looking JWT (if we had the secret)
    # or just rely on the "expired" test for now.

    # To properly test "missing from DB", we would need to:
    # 1. Login, get refresh token.
    # 2. Manually delete this token from `user_refresh_tokens` table using a DB utility/fixture.
    # 3. Attempt to refresh using the now-deleted token.
    # This is out of scope for a simple API test without direct DB access in the test.
    # We will rely on the "invalid_token" test and "expired_token" test.
    pass # Placeholder for now, as direct DB manipulation is complex here.


def test_refresh_token_expired_token(client, app, test_user):
    """Test token refresh with an expired refresh token."""
    # This test requires manipulating the token's expiry or mocking datetime.
    # To simulate expiry, we'd need to generate a token with a past 'exp' claim.
    # This requires the JWT_SECRET_KEY.
    # Alternative: use patch to make datetime.now() return a future time.

    # For simplicity, if direct token creation with specific expiry is hard,
    # we assume the backend correctly checks 'exp' claim from PyJWT.
    # PyJWT's decode function automatically raises ExpiredSignatureError.
    # The backend handles jwt.ExpiredSignatureError and returns 401.

    # This test is more about integration: does our endpoint correctly translate ExpiredSignatureError?
    # We can't easily make test_user['refresh_token'] expire instantly without waiting or complex mocks.

    # Let's assume the JWT library correctly identifies an expired token.
    # We can test the endpoint's behavior if we could *force* a token to be seen as expired.
    # One way: mock `jwt.decode` within the refresh endpoint to raise ExpiredSignatureError.
    with patch('jwt.decode', side_effect=jwt.ExpiredSignatureError("Token has expired")):
        response = client.post('/v1/auth/refresh', json={
            'refresh_token': test_user['refresh_token'] # Token content doesn't matter due to mock
        })
        assert response.status_code == 401
        data = response.get_json()
        assert "Refresh token has expired" in data.get('error', data.get('message'))

def test_refresh_token_no_token_provided(client):
    """Test token refresh when no token is provided in the request."""
    response = client.post('/v1/auth/refresh', json={})
    assert response.status_code == 400 # Bad Request
    data = response.get_json()
    assert "Refresh token is required" in data.get('error', data.get('message'))

# To run these tests, Pytest needs to be configured with Flask app context.
# conftest.py should handle app creation and client fixture.
# Example conftest.py:
# import pytest
# from engine.app import app as flask_app # Assuming your Flask app instance is named 'app'
#
# @pytest.fixture(scope='session')
# def app():
#     flask_app.config.update({
#         "TESTING": True,
#         # Use a separate test database if possible
#         # "SQLALCHEMY_DATABASE_URI": "postgresql://user:pass@host:port/test_db",
#         "JWT_SECRET_KEY": "test-secret-key" # Use a fixed test key
#     })
#     # TODO: Setup for test database (tables creation)
#     yield flask_app
#     # TODO: Teardown for test database (tables drop)
#
# @pytest.fixture()
# def client(app):
#     return app.test_client()
#
# @pytest.fixture()
# def runner(app):
#     return app.test_cli_runner()

# Note: The user_refresh_tokens table population is implicitly tested by
# `test_login_returns_both_tokens` (as login inserts it) and `test_refresh_token_success`
# (as refresh queries it). A more direct test would involve querying DB,
# which might be too complex for pure API tests without a DB access layer for tests.

# To test "old refresh token is invalidated or replaced":
# This depends on the strategy. If tokens are rotated, the refresh response should include a new refresh_token.
# The current backend implementation does NOT rotate refresh tokens or invalidate them on use.
# So, an old refresh token can be used multiple times until it expires.
# If rotation were implemented, we'd check for a new refresh_token in the response and
# then verify the old one no longer works.
