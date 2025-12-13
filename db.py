from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
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
