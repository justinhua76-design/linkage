import json
import os

# Test configuration must be in place before app modules read settings.
TOKENS = {
    "admin": "test-admin-token-0000000000",
    "clinician": "test-clinician-token-000000",
    "researcher": "test-researcher-token-00000",
    "viewer": "test-viewer-token-0000000000",
}
os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ["AUTH_TOKENS"] = json.dumps([{"token": t, "user_id": f"u-{r}", "role": r} for r, t in TOKENS.items()])

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402

SI_PROFILE = {
    "albumin": {"value": 45, "unit": "g/L"},
    "creatinine": {"value": 80, "unit": "µmol/L"},
    "glucose": {"value": 5.0, "unit": "mmol/L"},
    "crp": {"value": 1.0, "unit": "mg/L"},
    "lymphocyte_pct": {"value": 30, "unit": "%"},
    "mcv": {"value": 90, "unit": "fL"},
    "rdw": {"value": 13, "unit": "%"},
    "alp": {"value": 70, "unit": "U/L"},
    "wbc": {"value": 6, "unit": "10^9/L"},
}


def auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKENS[role]}"}


@pytest.fixture()
def db_sessionmaker():
    url = os.environ["DATABASE_URL"]
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
    else:  # pragma: no cover - exercised by the postgres test run
        engine = create_engine(url)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db_sessionmaker):
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()

    def _db():
        s = db_sessionmaker()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
