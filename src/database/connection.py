from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, Engine, event
from sqlalchemy.orm import sessionmaker, Session

from src.database.models import Base

DEFAULT_DB_PATH = Path.home() / "schichtplanung" / "schichtplan.db"

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_db(db_path: Path = DEFAULT_DB_PATH) -> Engine:
    """
    Initialisiert die SQLite-Datenbank und erstellt alle Tabellen.
    Muss einmal beim Programmstart aufgerufen werden.
    """
    global _engine, _SessionLocal

    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Foreign-Key-Unterstützung für SQLite aktivieren
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Datenbank nicht initialisiert. init_db() zuerst aufrufen.")
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context-Manager für Datenbank-Sessions.

    Verwendung:
        with get_session() as session:
            session.add(obj)
    """
    if _SessionLocal is None:
        raise RuntimeError("Datenbank nicht initialisiert. init_db() zuerst aufrufen.")
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
