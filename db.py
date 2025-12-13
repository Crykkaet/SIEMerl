from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./siem.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String(50), unique=True, index=True)
    name = Column(String(100), nullable=True)
    mac = Column(String(50), nullable=True)
    client_id = Column(String(50), unique=True, nullable=True)
    tags = Column(String(250), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(100))
    level = Column(String(20))
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    client_ip = Column(String(50), nullable=True)
    client_name = Column(String(100), nullable=True)
    client_identifier = Column(String(50), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    client_ip = Column(String(50), index=True)
    rule_name = Column(String(100))
    description = Column(Text)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    count = Column(Integer, default=0)

def init_db():
    Base.metadata.create_all(bind=engine)
    _upgrade_schema()


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))


def _upgrade_schema():
    if engine.dialect.name != "sqlite":
        return

    with engine.connect() as conn:
        _ensure_column(conn, "clients", "client_id", "VARCHAR(50)")
        _ensure_column(conn, "clients", "tags", "VARCHAR(250)")
        _ensure_column(conn, "clients", "description", "TEXT")
        _ensure_column(conn, "clients", "created_at", "DATETIME")
        _ensure_column(conn, "clients", "last_seen", "DATETIME")

        _ensure_column(conn, "logs", "client_name", "VARCHAR(100)")
        _ensure_column(conn, "logs", "client_identifier", "VARCHAR(50)")
