import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil


@dataclass
class SystemMetrics:
    cpu_percent:      float         = 0.0
    cpu_per_core:     List[float]   = field(default_factory=list)
    cpu_temp:         Optional[float] = None
    ram_used_mb:      int           = 0
    ram_total_mb:     int           = 0
    ram_percent:      float         = 0.0
    disk_used_gb:     float         = 0.0
    disk_total_gb:    float         = 0.0
    disk_percent:     float         = 0.0
    net_upload_kbps:  float         = 0.0
    net_download_kbps: float        = 0.0
    local_ip:         str           = "N/A"
    hostname:         str           = "N/A"
    uptime_seconds:   int           = 0
    # "healthy" | "throttled" | "undervoltage" | "warning" | "unknown"
    power_status:     str           = "unknown"
    is_throttled:     bool          = False
    is_undervoltage:  bool          = False


class MetricsCollector:
    def __init__(self):
        self._last_net_io   = None
        self._last_net_time = None
        # Prime psutil's non-blocking cpu_percent
        psutil.cpu_percent(percpu=False)
        psutil.cpu_percent(percpu=True)

    def collect(self) -> SystemMetrics:
        m = SystemMetrics()

        m.cpu_percent  = psutil.cpu_percent(interval=None)
        m.cpu_per_core = psutil.cpu_percent(percpu=True, interval=None)
        m.cpu_temp     = self._cpu_temp()

        ram = psutil.virtual_memory()
        m.ram_used_mb  = ram.used   // (1024 * 1024)
        m.ram_total_mb = ram.total  // (1024 * 1024)
        m.ram_percent  = ram.percent

        disk = psutil.disk_usage("/")
        m.disk_used_gb  = disk.used  / (1024 ** 3)
        m.disk_total_gb = disk.total / (1024 ** 3)
        m.disk_percent  = disk.percent

        m.net_upload_kbps, m.net_download_kbps = self._net_speed()
        m.local_ip        = self._local_ip()
        m.hostname        = socket.gethostname()
        m.uptime_seconds  = int(time.time() - psutil.boot_time())

        throttle = self._vcgencmd_throttle()
        m.power_status  = throttle["status"]
        m.is_throttled  = throttle["throttled"]
        m.is_undervoltage = throttle["undervoltage"]

        return m

    # ── private ──────────────────────────────────────────────────────────────

    def _cpu_temp(self) -> Optional[float]:
        try:
            temps = psutil.sensors_temperatures()
            for key in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
                if key in temps and temps[key]:
                    return temps[key][0].current
        except Exception:
            pass
        # Pi fallback via sysfs
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            return None

    def _net_speed(self):
        now = time.time()
        try:
            net = psutil.net_io_counters()
        except Exception:
            return 0.0, 0.0

        if self._last_net_io is None or self._last_net_time is None:
            self._last_net_io   = net
            self._last_net_time = now
            return 0.0, 0.0

        elapsed = now - self._last_net_time
        if elapsed < 0.05:
            return 0.0, 0.0

        upload   = (net.bytes_sent - self._last_net_io.bytes_sent) / elapsed / 1024
        download = (net.bytes_recv - self._last_net_io.bytes_recv) / elapsed / 1024

        self._last_net_io   = net
        self._last_net_time = now
        return max(0.0, upload), max(0.0, download)

    def _local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "N/A"

    def _vcgencmd_throttle(self) -> dict:
        base = {"status": "unknown", "throttled": False, "undervoltage": False}
        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True, text=True, timeout=2
            )
            # output: "throttled=0x0" or "throttled=0x50005"
            raw = result.stdout.strip()
            val = int(raw.split("=")[1], 16)

            undervoltage = bool(val & 0x1)
            throttled    = bool(val & 0x4)

            if val == 0:
                status = "healthy"
            elif undervoltage:
                status = "undervoltage"
            elif throttled:
                status = "throttled"
            else:
                status = "warning"

            return {"status": status, "throttled": throttled, "undervoltage": undervoltage}
        except FileNotFoundError:
            # vcgencmd not present (dev machine)
            return {**base, "status": "healthy"}
        except Exception:
            return base
