import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from engine.app import app

@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client
