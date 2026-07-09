import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base

# Import all models so SQLAlchemy registers them before create_all
import app.models.user          # noqa: F401
import app.models.vehicle       # noqa: F401
import app.models.trip          # noqa: F401
import app.models.booking       # noqa: F401
import app.models.payment       # noqa: F401
import app.models.review        # noqa: F401
import app.models.notification  # noqa: F401
import app.models.message       # noqa: F401
import app.models.device        # noqa: F401
import app.models.ticket        # noqa: F401


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def reset_db(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def db_session(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
