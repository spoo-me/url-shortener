"""
New FastAPI entry point.

Kept separate from main.py (Flask) so both can coexist during migration.
main.py will be replaced by this file in Phase 16.

Run with:
    uvicorn asgi:app --reload --no-access-log
"""

import logging

from dotenv import load_dotenv

load_dotenv()  # Must run before any module reads os.environ

from app import create_app  # noqa: E402

# Disable uvicorn's default access log — our RequestLoggingMiddleware handles it
logging.getLogger("uvicorn.access").disabled = True

app = create_app()
