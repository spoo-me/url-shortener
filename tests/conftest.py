import pytest
from flask import Flask
from blueprints.url_shortener import url_shortener

@pytest.fixture
def client():
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(url_shortener)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
