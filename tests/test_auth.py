import uuid
from unittest.mock import patch, MagicMock
import bcrypt
import jwt
from engine.app import app


@patch('engine.app.get_db_connection')
def test_login_returns_tokens(mock_get_db_conn, client):
    user_id = str(uuid.uuid4())
    password = 'secretpw'
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {'id': user_id, 'password_hash': hashed}

    response = client.post('/v1/auth/login', json={'email': 'a@example.com', 'password': password})
    data = response.get_json()
    assert response.status_code == 200
    assert 'access_token' in data
    assert 'refresh_token' in data
    # decode refresh token to ensure correct type
    payload = jwt.decode(data['refresh_token'], app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    assert payload['type'] == 'refresh'
    assert payload['user_id'] == user_id


@patch('engine.app.get_db_connection')
def test_refresh_endpoint(mock_get_db_conn, client):
    user_id = str(uuid.uuid4())
    password = 'secretpw'
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_conn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {'id': user_id, 'password_hash': hashed}

    login_resp = client.post('/v1/auth/login', json={'email': 'a@example.com', 'password': password})
    tokens = login_resp.get_json()

    refresh_resp = client.post('/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    data = refresh_resp.get_json()
    assert refresh_resp.status_code == 200
    assert 'access_token' in data
    assert data['access_token'] != tokens['access_token']

