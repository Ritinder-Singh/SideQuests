"""Network stats: WiFi, public IP, ping, usb0 status."""

import re
import socket
import subprocess
import time
from typing import Optional, Tuple

import psutil

import config
from state import NetworkInfo, PingResult

_pub_ip_cache: Tuple[str, float] = ("", 0.0)
_PUB_IP_TTL = 600  # seconds


def collect() -> NetworkInfo:
    info = NetworkInfo()
    info.wifi_ssid, info.wifi_signal_dbm = _wifi()
    info.public_ip   = _public_ip()
    info.usb0_up, info.usb0_ip = _usb0()
    info.ping_results = _ping_all()
    return info


# ── private ───────────────────────────────────────────────────────────────────

def _wifi() -> Tuple[str, Optional[int]]:
    try:
        out = subprocess.check_output(
            ["iw", "wlan0", "link"], stderr=subprocess.DEVNULL, text=True
        )
        ssid   = re.search(r"SSID: (.+)",    out)
        signal = re.search(r"signal: (-\d+)", out)
        return (
            ssid.group(1).strip() if ssid else "N/A",
            int(signal.group(1))  if signal else None,
        )
    except Exception:
        return "N/A", None


def _public_ip() -> str:
    global _pub_ip_cache
    ip, ts = _pub_ip_cache
    if ip and time.time() - ts < _PUB_IP_TTL:
        return ip
    try:
        import urllib.request
        ip = urllib.request.urlopen(
            "https://api.ipify.org", timeout=5
        ).read().decode().strip()
        _pub_ip_cache = (ip, time.time())
        return ip
    except Exception:
        return _pub_ip_cache[0] or "N/A"


def _usb0() -> Tuple[bool, str]:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    if "usb0" in addrs and stats.get("usb0") and stats["usb0"].isup:
        for addr in addrs["usb0"]:
            if addr.family == socket.AF_INET:
                return True, addr.address
        return True, "N/A"
    return False, "N/A"


def _ping(host: str, timeout: int = 1) -> Optional[float]:
    try:
        out = subprocess.check_output(
            ["ping", "-c", "1", "-W", str(timeout), host],
            stderr=subprocess.DEVNULL, text=True,
        )
        m = re.search(r"time=([\d.]+)", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def _ping_all():
    return [
        PingResult(label=label, host=host, latency_ms=_ping(host))
        for host, label in config.PING_TARGETS
    ]
