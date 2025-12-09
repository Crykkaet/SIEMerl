from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from db import SessionLocal, LogEntry, init_db
from typing import Optional

app = FastAPI(title="SIEMerl")

init_db()

class LogIn(BaseModel):
    source: str
    level: str
    message: str

@app.get("/")
def root():
    return {"status": "SIEMerl backend running"}

@app.post("/ingest")
def ingest_log(log: LogIn):
    db = SessionLocal()
    entry = LogEntry(
        source=log.source,
        level=log.level,
        message=log.message
    )
    db.add(entry)
    db.commit()
    db.close()
    return {"status": "log stored"}

@app.get("/logs")
def get_logs(
    level: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    db = SessionLocal()
    query = db.query(LogEntry)

    if level:
        query = query.filter(LogEntry.level == level)
    if source:
        query = query.filter(LogEntry.source == source)
    if search:
        like = f"%{search}%"
        query = query.filter(LogEntry.message.ilike(like))

    logs = query.order_by(LogEntry.timestamp.desc()).limit(limit).all()
    db.close()

    return [
        {
            "id": log.id,
            "source": log.source,
            "level": log.level,
            "message": log.message,
            "timestamp": log.timestamp.isoformat()
        } for log in logs
    ]

@app.get("/viewer", response_class=HTMLResponse)
def viewer():
    with open("logs.html") as f:
        return f.read()
