"""
Syslog bridge that listens for UDP syslog messages and forwards them to the
existing SIEMerl /ingest endpoint.
"""
import logging
import os
import re
import socket
from typing import Optional

import requests

DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 5514
DEFAULT_INGEST_URL = "http://127.0.0.1:8000/ingest"

LISTEN_HOST = os.getenv("SYSLOG_BRIDGE_HOST", DEFAULT_LISTEN_HOST)
LISTEN_PORT = int(os.getenv("SYSLOG_BRIDGE_PORT", DEFAULT_LISTEN_PORT))
INGEST_URL = os.getenv("SIEMERL_INGEST_URL", DEFAULT_INGEST_URL)
HTTP_TIMEOUT = float(os.getenv("SYSLOG_BRIDGE_HTTP_TIMEOUT", "2"))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("siemerl-syslog-bridge")


def parse_pri(message: str) -> tuple[Optional[int], str]:
    """Extract the PRI value and return remaining message body."""
    match = re.match(r"^<(\d+)>", message)
    if not match:
        return None, message

    pri_value = int(match.group(1))
    body = message[match.end() :].lstrip()
    return pri_value, body


def severity_to_level(pri_value: Optional[int]) -> str:
    if pri_value is None:
        return "INFO"

    severity = pri_value & 0x7
    if severity <= 3:
        return "ERROR"
    if severity == 4:
        return "WARN"
    return "INFO"


def parse_source(body: str) -> Optional[str]:
    """Attempt to parse a hostname/app from the syslog body."""
    # RFC5424 style: <PRI>1 TIMESTAMP HOST APP PROCID MSGID MSG
    match = re.match(r"^(\d)\s+\S+\s+(\S+)\s+(\S+)", body)
    if match:
        return match.group(3)

    # RFC3164 style: <PRI>MMM DD HH:MM:SS HOST TAG: MSG
    match = re.match(r"^[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)(?:\s+(\S+))?", body)
    if match:
        return match.group(2) or match.group(1)

    return None


def forward_log(payload: dict) -> None:
    try:
        response = requests.post(INGEST_URL, json=payload, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to forward log: %s", exc)


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    logger.info("Syslog bridge listening on %s:%s", LISTEN_HOST, LISTEN_PORT)
    logger.info("Forwarding logs to %s", INGEST_URL)

    while True:
        try:
            data, addr = sock.recvfrom(8192)
            client_ip, _ = addr
            message = data.decode(errors="replace").strip()

            pri_value, body = parse_pri(message)
            level = severity_to_level(pri_value)
            source = parse_source(body) or "syslog"

            payload = {
                "source": source,
                "level": level,
                "message": f"[{client_ip}] {message}",
            }

            logger.debug("Received from %s: %s", client_ip, message)
            forward_log(payload)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error processing syslog message: %s", exc)


if __name__ == "__main__":
    main()
