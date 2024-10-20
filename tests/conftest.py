import pytest
from flask import Flask
import mongomock
from blueprints.url_shortener import url_shortener
from blueprints.stats import stats


@pytest.fixture
def client():
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(url_shortener)
    app.register_blueprint(stats)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db():
    # Create a mock database
    mock_db = mongomock.MongoClient().db
    return mock_db
