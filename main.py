from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from pydantic import BaseModel
from db import SessionLocal, LogEntry, init_db

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
def get_logs():
    db = SessionLocal()
    logs = db.query(LogEntry).order_by(LogEntry.timestamp.desc()).limit(100).all()
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
