from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from db import SessionLocal, LogEntry, Client, Alert, init_db
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import func


app = FastAPI(title="SIEMerl")

init_db()


def evaluate_alerts(db, client_ip: str, threshold: int = 5, window_minutes: int = 5):
    """Check for error bursts and create/update alerts."""
    if not client_ip:
        return

    rule_name = "Error burst"
    window_start = datetime.utcnow() - timedelta(minutes=window_minutes)

    error_count = (
        db.query(LogEntry)
        .filter(
            LogEntry.client_ip == client_ip,
            LogEntry.level == "ERROR",
            LogEntry.timestamp >= window_start,
        )
        .count()
    )

    alert = (
        db.query(Alert)
        .filter(Alert.client_ip == client_ip, Alert.rule_name == rule_name)
        .first()
    )

    if error_count >= threshold:
        now = datetime.utcnow()
        description = f"{error_count} ERROR logs in the last {window_minutes} minutes"
        if alert:
            alert.count = error_count
            alert.last_seen = now
            alert.description = description
            if not alert.first_seen:
                alert.first_seen = now
        else:
            alert = Alert(
                client_ip=client_ip,
                rule_name=rule_name,
                description=description,
                first_seen=now,
                last_seen=now,
                count=error_count,
            )
            db.add(alert)
        db.commit()
    elif alert:
        db.delete(alert)
        db.commit()

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

    try:
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

        evaluate_alerts(db, client_ip)

        return {"status": "log stored", "client_ip": client_ip}
    finally:
        db.close()


@app.get("/logs")
def get_logs(
    level: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    client_ip: Optional[str] = None,
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
    if client_ip:
        query = query.filter(LogEntry.client_ip == client_ip)

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


@app.get("/client_ips")
def get_client_ips():
    db = SessionLocal()
    results = (
        db.query(LogEntry.client_ip, func.count(LogEntry.id))
        .filter(LogEntry.client_ip.isnot(None))
        .group_by(LogEntry.client_ip)
        .order_by(LogEntry.client_ip)
        .all()
    )
    db.close()

    return [
        {"client_ip": ip, "count": count}
        for ip, count in results
    ]


@app.get("/alerts")
def get_alerts():
    db = SessionLocal()
    alerts = db.query(Alert).order_by(Alert.last_seen.desc()).all()
    db.close()

    return [
        {
            "id": alert.id,
            "client_ip": alert.client_ip,
            "rule_name": alert.rule_name,
            "description": alert.description,
            "first_seen": alert.first_seen.isoformat() if alert.first_seen else None,
            "last_seen": alert.last_seen.isoformat() if alert.last_seen else None,
            "count": alert.count,
        }
        for alert in alerts
    ]
