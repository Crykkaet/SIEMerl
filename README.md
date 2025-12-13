# SIEMerl

## Inbetriebnahme-Voraussetzungen
- **Laufzeitumgebung:** Python 3.10 oder höher, `venv`/`pip` und Zugriff auf SQLite (lokale Datei `siem.db`).
- **Python-Module:** `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic`, `requests` (Installation siehe unten).
- **Netzwerk & Firewall:**
  - TCP-Port **8000** eingehend zulassen (REST-API und Log-Viewer).
  - UDP-Port **5514** eingehend zulassen, wenn die Syslog Bridge genutzt wird.
- **Optionale Dienste:** systemd zum Betrieb als Hintergrunddienst.

## Installation und Start in der Umgebung
1. Virtuelle Umgebung anlegen und Abhängigkeiten installieren:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install fastapi "uvicorn[standard]" sqlalchemy pydantic requests
   ```
2. FastAPI-Anwendung starten (Beispiel mit `uvicorn`):
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Log-Viewer im Browser öffnen: `http://<host>:8000/viewer`.

## Integration als Systemdienst
### SIEMerl (FastAPI)
1. Beispielhafte systemd-Unit erstellen `/etc/systemd/system/siemerl.service`:
   ```ini
   [Unit]
   Description=SIEMerl FastAPI Service
   After=network.target

   [Service]
   User=siemerl
   WorkingDirectory=/opt/siemerl
   Environment="PATH=/opt/siemerl/venv/bin"
   ExecStart=/opt/siemerl/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
2. Dienst aktivieren und starten:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now siemerl.service
   ```

### Syslog Bridge
1. Mitgelieferte Vorlage kopieren:
   ```bash
   sudo cp systemd/siemerl-syslog-bridge.service /etc/systemd/system/
   ```
2. In der Unit `User`, `WorkingDirectory` und `ExecStart` auf lokale Pfade/Umgebung anpassen.
3. Dienst laden und starten:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now siemerl-syslog-bridge
   ```

### Archivierung per Cron oder systemd-timer
- ## Log-Archivierung & Aufbewahrung (Retention)

SIEMerl verwendet eine zeitgesteuerte Archivierung, um die Größe der SQLite-Datenbank zu begrenzen und gleichzeitig eine langfristige Aufbewahrung von Logdaten zu ermöglichen.

### Funktionsweise

- Neue Logeinträge werden in der SQLite-Datenbank (`siem.db`) gespeichert.
- Logeinträge, die älter als **30 Tage** sind, werden automatisch:
  1. in **monatliche CSV-Dateien** exportiert  
     (`Archiv/<Jahr>/<Jahr>-<Monat>.csv`)
  2. anschließend **aus der Datenbank gelöscht**
- Die erzeugten CSV-Dateien können langfristig archiviert oder extern gesichert werden.

Dieses Verfahren hält die Datenbank performant, während historische Daten weiterhin verfügbar bleiben.

---

### Automatisierung über systemd Timer

Die Archivierung wird bewusst **nicht im FastAPI-Backend** ausgeführt, sondern über einen separaten systemd-Timer.  
So bleibt das Backend schlank und frei von Wartungs- oder Batch-Aufgaben.

- **Ausführung:** täglich um **23:45 Uhr**
- **Service-Typ:** `oneshot`
- **Scheduler:** systemd timer (`Persistent=true`)
- **Archiv-Skript:** `archive.py`

#### Verwendete systemd Units

- `siemerl-archive.service`  
  Führt das Archivierungs-Skript einmalig aus

- `siemerl-archive.timer`  
  Startet den Service zeitgesteuert

#### Status und Logs prüfen

```bash
systemctl list-timers | grep siemerl
journalctl -u siemerl-archive.service

  ```

## Funktionsbeschreibung
### SIEMerl
- Leichtgewichtiges Log-Backend mit FastAPI und SQLite.
- `/ingest` nimmt JSON-Logs entgegen, speichert sie in der SQLite-Datenbank und erzeugt einfache Alerts bei Fehlerspitzen.
- `/viewer` liefert ein HTML-Frontend zur Ansicht der Logs, weitere Endpunkte liefern Clients, Alerts und gefilterte Logdaten.

### Syslog Bridge
- UDP-Syslog-Empfänger (Standard: `0.0.0.0:5514`), der Nachrichten in das `/ingest`-Endpoint weiterleitet.
- Liest das PRI-Feld, ordnet daraus ein Log-Level zu und ergänzt den Ursprungs-Client in der Nachricht.
- Ziel-Endpoint standardmäßig `http://127.0.0.1:8000/ingest`, konfigurierbar über Umgebungsvariablen.

### Archiver
- Exportiert Log-Einträge, die älter als 30 Tage sind, nach `Archiv/<Jahr>/<Jahr>-<Monat>.csv` und entfernt sie aus der Datenbank.
- Unterstützt monatliche Gruppierung, schreibt Header bei neuen CSV-Dateien und gibt die Anzahl archivierter Einträge aus.
