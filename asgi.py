"""
New FastAPI entry point.

Kept separate from main.py (Flask) so both can coexist during migration.
main.py will be replaced by this file in Phase 16.

Run with:
    uvicorn asgi:app --reload
"""

from app import create_app

app = create_app()
