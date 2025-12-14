from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
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
    client_name: Optional[str] = None
    client_id: Optional[str] = None


class ClientIn(BaseModel):
    ip: str
    name: Optional[str] = None
    mac: Optional[str] = None
    client_id: Optional[str] = None
    tags: Optional[str] = None
    description: Optional[str] = None

@app.get("/")
def root():
    return {"status": "SIEMerl backend running"}

@app.post("/ingest")
def ingest_log(log: LogIn, request: Request):
    client_ip = request.client.host

    db = SessionLocal()

    try:
        # Client-Verzeichnis pflegen
        client = None
        if log.client_id:
            client = db.query(Client).filter(Client.client_id == log.client_id).first()

        if client is None:
            client = db.query(Client).filter(
                Client.ip == client_ip,
                Client.name == (log.client_name or log.source)
            ).first()

        if client is None:
            client = db.query(Client).filter(Client.ip == client_ip).first()

        if client is None:
            client = Client(
                ip=client_ip,
                name=log.client_name or log.source or "N.N.",
                client_id=log.client_id,
                last_seen=datetime.utcnow(),
            )
            db.add(client)
            db.flush()
            if not client.client_id:
                client.client_id = f"C{client.id:05d}"

        if client:
            if log.client_name:
                client.name = log.client_name
            if log.client_id:
                client.client_id = log.client_id
            client.last_seen = datetime.utcnow()
            db.commit()

        # Log speichern
        entry = LogEntry(
            source=log.source,
            level=log.level,
            message=log.message,
            client_ip=client_ip,
            client_name=client.name if client else "N.N.",
            client_identifier=client.client_id if client and client.client_id else "N.N.",
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
            "client_name": log.client_name or "N.N.",
            "client_id": log.client_identifier or "N.N.",
        }
        for log in logs
    ]


@app.get("/viewer", response_class=HTMLResponse)
def viewer():
    with open("logs.html") as f:
        return f.read()

@app.get("/api/clients")
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
            "client_id": c.client_id,
            "tags": c.tags,
            "description": c.description,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "last_seen": c.last_seen.isoformat() if c.last_seen else None
        } for c in clients
    ]
@app.post("/api/clients")
def create_or_update_client(client_in: ClientIn):
    db = SessionLocal()
    try:
        client = None
        if client_in.client_id:
            client = db.query(Client).filter(Client.client_id == client_in.client_id).first()

        if client is None:
            client = db.query(Client).filter(Client.ip == client_in.ip).first()

        if client is None:
            client = Client(
                ip=client_in.ip,
                name=client_in.name,
                mac=client_in.mac,
                client_id=client_in.client_id,
                tags=client_in.tags,
                description=client_in.description,
            )
            db.add(client)
            db.flush()
            if not client.client_id:
                client.client_id = f"C{client.id:05d}"
        else:
            client.ip = client_in.ip
            client.name = client_in.name or client.name or "N.N."
            client.mac = client_in.mac or client.mac
            client.client_id = client_in.client_id or client.client_id
            client.tags = client_in.tags if client_in.tags is not None else client.tags
            client.description = client_in.description if client_in.description is not None else client.description

        if not client.client_id:
            client.client_id = f"C{client.id:05d}" if client.id else None

        client.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(client)

        return {
            "id": client.id,
            "ip": client.ip,
            "name": client.name,
            "mac": client.mac,
            "client_id": client.client_id,
            "tags": client.tags,
            "description": client.description,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "last_seen": client.last_seen.isoformat() if client.last_seen else None,
        }
    finally:
        db.close()


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
@app.get("/clients", response_class=HTMLResponse)
@app.get("/clients.html", response_class=HTMLResponse)
def clients_view():
    return FileResponse("clients.html", media_type="text/html")
