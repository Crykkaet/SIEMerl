# SIEMerl

SIEMerl is a lightweight SIEM-like log viewer built with FastAPI and SQLite. Logs are ingested as JSON via the `/ingest` endpoint and can be browsed through a simple HTML interface.

## Getting Started

1. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run the FastAPI app (for example with `uvicorn`):
   ```bash
   uvicorn main:app --reload
   ```
3. Visit `http://localhost:8000/viewer` to browse logs.

## UDM / Syslog Integration via Syslog Bridge

Syslog-only devices (like the Ubiquiti UDM) can send their UDP syslog streams to SIEMerl through the `syslog_bridge.py` helper. The bridge listens on UDP and forwards received syslog messages to the existing `/ingest` endpoint.

- **Default listen address:** `0.0.0.0`
- **Default port:** `5514` (UDP)
- **Forward target:** `http://127.0.0.1:8000/ingest`

### Running with systemd

A systemd service template is provided in `systemd/siemerl-syslog-bridge.service`.

1. Copy the template to `/etc/systemd/system/`:
   ```bash
   sudo cp systemd/siemerl-syslog-bridge.service /etc/systemd/system/
   ```
2. Edit the unit file to set the correct `User`, `WorkingDirectory`, and `ExecStart` paths for your environment.
3. Reload systemd and start the bridge:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now siemerl-syslog-bridge
   ```

### Configuring a UDM

- **Syslog Server:** `<SIEMerl-IP>`
- **Port:** `5514` (UDP)

Once configured, syslog messages from the UDM (or other devices) will appear in SIEMerl with severity derived from the syslog PRI value and the raw syslog content prefixed by the sender's IP address.
