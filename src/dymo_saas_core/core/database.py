from typing import AsyncGenerator, Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from dymo_saas_core.core.config import settings

# Sync DB Config
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine
)

# Async DB Config
# Some local/test environments use SQLite, which may not have an async driver
# installed. In that case, keep the package importable and make async access opt-in.
async_engine: Optional[object]
AsyncSessionLocal: Optional[sessionmaker] = None
if not settings.DATABASE_URL.startswith("sqlite"):
    async_engine = create_async_engine(
        settings.async_db_url,
        pool_pre_ping=True,
        echo=False
    )
    AsyncSessionLocal = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
else:
    async_engine = None

class Base(DeclarativeBase):
    pass

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database access is not configured for this database URL.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
