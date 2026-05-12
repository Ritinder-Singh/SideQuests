"""Read recent system log entries via journalctl."""

import subprocess
from typing import List


def get_recent_logs(n: int = 30) -> List[str]:
    try:
        out = subprocess.check_output(
            ["journalctl", "-n", str(n), "--no-pager", "-o", "short"],
            stderr=subprocess.DEVNULL, text=True,
        )
        lines = [l.rstrip() for l in out.splitlines() if l.strip()]
        return lines[-n:]
    except Exception as exc:
        return [f"journalctl unavailable: {exc}"]
