from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from db import SessionLocal, LogEntry, Client, init_db
from typing import Optional
from datetime import datetime


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
def ingest_log(log: LogIn, request: Request):
    client_ip = request.client.host

    db = SessionLocal()

    # Client-Verzeichnis pflegen
    client = db.query(Client).filter(Client.ip == client_ip).first()
    if client is None:
        client = Client(
            ip=client_ip,
            name=log.source  # als Default nehmen wir erstmal "source"
        )
        db.add(client)
    client.last_seen = datetime.utcnow()

    # Log speichern
    entry = LogEntry(
        source=log.source,
        level=log.level,
        message=log.message,
        client_ip=client_ip
    )
    db.add(entry)
    db.commit()
    db.close()

    return {"status": "log stored", "client_ip": client_ip}


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
            "timestamp": log.timestamp.isoformat(),
            "client_ip": log.client_ip,
        }
        for log in logs
    ]


@app.get("/viewer", response_class=HTMLResponse)
def viewer():
    with open("logs.html") as f:
        return f.read()

@app.get("/clients")
def get_clients():
    db = SessionLocal()
    clients = db.query(Client).order_by(Client.ip).all()
    db.close()

    return [
        {
            "id": c.id,
            "ip": c.ip,
            "name": c.name,
            "mac": c.mac,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "last_seen": c.last_seen.isoformat() if c.last_seen else None
        } for c in clients
    ]
