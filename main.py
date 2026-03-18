"""
FastAPI application entry point.

Run with:
    uvicorn main:app --reload --no-access-log
"""

import logging
from dotenv import load_dotenv

load_dotenv()  # Must run before any module reads os.environ

from app import create_app  # noqa: E402

# Disable uvicorn's default access log — our RequestLoggingMiddleware handles it
logging.getLogger("uvicorn.access").disabled = True

app = create_app()
