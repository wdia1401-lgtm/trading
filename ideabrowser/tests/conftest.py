import os
import tempfile

# Point the app at a throwaway database BEFORE any app module is imported.
_tmpdir = tempfile.mkdtemp(prefix="ideabrowser-test-")
os.environ["IDEABROWSER_DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ.pop("ANTHROPIC_API_KEY", None)  # force the deterministic AI backend

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, init_db
from app.main import app


@pytest.fixture()
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    init_db()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
