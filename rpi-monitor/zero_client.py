"""SSH client for Pi Zero — connects, runs zero_agent.py, returns ZeroMetrics."""

import json
import time
from typing import Optional

import config
from state import ZeroMetrics


class ZeroClient:
    def __init__(self):
        self._client = None

    def fetch(self) -> ZeroMetrics:
        try:
            if not self._connected():
                self._connect()
            raw = self._run_agent()
            return self._parse(raw)
        except Exception:
            self._disconnect()
            return ZeroMetrics(online=False)

    def close(self):
        self._disconnect()

    # ── private ──────────────────────────────────────────────────────────────

    def _connected(self) -> bool:
        try:
            t = self._client and self._client.get_transport()
            return bool(t and t.is_active())
        except Exception:
            return False

    def _connect(self):
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(
            config.ZERO_IP,
            port=config.ZERO_SSH_PORT,
            username=config.ZERO_SSH_USER,
            key_filename=config.ZERO_SSH_KEY,
            timeout=5,
            banner_timeout=10,
        )
        self._client = c

    def _run_agent(self) -> str:
        _, stdout, _ = self._client.exec_command(
            "python3 /usr/local/bin/zero_agent.py", timeout=8
        )
        return stdout.read().decode()

    def _parse(self, raw: str) -> ZeroMetrics:
        d = json.loads(raw)
        return ZeroMetrics(
            online         = True,
            hostname       = d.get("hostname", "pizero"),
            uptime_seconds = d.get("uptime_seconds", 0),
            cpu_percent    = d.get("cpu_percent", 0.0),
            cpu_temp       = d.get("cpu_temp"),
            ram_used_mb    = d.get("ram_used_mb", 0),
            ram_total_mb   = d.get("ram_total_mb", 512),
            disk_used_mb   = d.get("disk_used_mb", 0),
            disk_total_mb  = d.get("disk_total_mb", 0),
            services       = d.get("services", []),
            ssh_sessions   = d.get("ssh_sessions", []),
            last_seen      = time.time(),
        )

    def _disconnect(self):
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
        self._client = None
