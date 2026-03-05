import pytest


@pytest.fixture
def client():
    from flask import Flask  # noqa: PLC0415
    from blueprints.url_shortener import url_shortener  # noqa: PLC0415
    from blueprints.stats import stats  # noqa: PLC0415

    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(url_shortener)
    app.register_blueprint(stats)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db():
    import mongomock  # noqa: PLC0415

    return mongomock.MongoClient().db
