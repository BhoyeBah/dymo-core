import os
os.environ["ENVIRONMENT"] = "testing"
test_db_path = f"./.dymo_test_{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.pop("ASYNC_DATABASE_URL", None)

try:
    os.remove(test_db_path)
except FileNotFoundError:
    pass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from dymo_saas_core.core.config import settings
from dymo_saas_core.core.database import Base, get_db
from dymo_saas_core.main import create_app
from dymo_saas_core.modules.cash_register_simple import manifest as cash_register_manifest, router as cash_register_router

app = create_app(modules=[{"manifest": cash_register_manifest, "router": cash_register_router}])

engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

@pytest.fixture(autouse=True)
def setup_database():
    db_url = settings.DATABASE_URL.lower()
    if "test" not in db_url and settings.ENVIRONMENT != "testing":
        raise RuntimeError(
            f"CRITICAL SAFETY WARNING: Prevented running database migrations/destructions against "
            f"non-test database connection: '{settings.DATABASE_URL}'. Environment is '{settings.ENVIRONMENT}'."
        )
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    else:
        Base.metadata.drop_all(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db_session):
    # Override get_db dependency to use the transactional test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
