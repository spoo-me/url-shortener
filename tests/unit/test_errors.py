"""Unit tests for AppError hierarchy."""

from errors import (
    AppError,
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


class TestAppErrorSubclasses:
    def test_validation_error(self):
        e = ValidationError("bad input")
        assert e.status_code == 400
        assert e.error_code == "validation_error"
        assert e.message == "bad input"

    def test_authentication_error(self):
        e = AuthenticationError("not authenticated")
        assert e.status_code == 401
        assert e.error_code == "authentication_error"

    def test_forbidden_error(self):
        e = ForbiddenError("not allowed")
        assert e.status_code == 403
        assert e.error_code == "forbidden"

    def test_not_found_error(self):
        e = NotFoundError("resource missing")
        assert e.status_code == 404
        assert e.error_code == "not_found"

    def test_conflict_error(self):
        e = ConflictError("already exists")
        assert e.status_code == 409
        assert e.error_code == "conflict"

    def test_rate_limit_error(self):
        e = RateLimitError("slow down")
        assert e.status_code == 429
        assert e.error_code == "rate_limit_exceeded"


class TestAppErrorToDict:
    def test_basic_to_dict(self):
        e = NotFoundError("url not found")
        d = e.to_dict()
        assert d == {"error": "url not found", "code": "not_found"}

    def test_to_dict_with_field(self):
        e = ValidationError("invalid alias", field="alias")
        d = e.to_dict()
        assert d["field"] == "alias"

    def test_to_dict_with_details(self):
        e = ValidationError("invalid", details={"min": 1, "max": 10})
        d = e.to_dict()
        assert d["details"] == {"min": 1, "max": 10}

    def test_to_dict_no_field_key_when_absent(self):
        e = NotFoundError("missing")
        d = e.to_dict()
        assert "field" not in d
        assert "details" not in d
