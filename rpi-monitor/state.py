"""Shared data classes passed between collector threads and the renderer."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ZeroMetrics:
    online:         bool          = False
    hostname:       str           = "pizero"
    uptime_seconds: int           = 0
    cpu_percent:    float         = 0.0
    cpu_temp:       Optional[float] = None
    ram_used_mb:    int           = 0
    ram_total_mb:   int           = 512
    disk_used_mb:   int           = 0
    disk_total_mb:  int           = 0
    services:       List[str]     = field(default_factory=list)
    ssh_sessions:   List[dict]    = field(default_factory=list)
    last_seen:      Optional[float] = None


@dataclass
class ContainerInfo:
    name:        str   = ""
    status:      str   = "stopped"  # running | stopped | restarting | exited
    cpu_percent: float = 0.0
    mem_mb:      float = 0.0


@dataclass
class PingResult:
    label:      str
    host:       str
    latency_ms: Optional[float] = None   # None = unreachable


@dataclass
class NetworkInfo:
    wifi_ssid:       str            = "N/A"
    wifi_signal_dbm: Optional[int]  = None
    public_ip:       str            = "N/A"
    usb0_up:         bool           = False
    usb0_ip:         str            = "N/A"
    ping_results:    List[PingResult] = field(default_factory=list)


@dataclass
class AppData:
    pi5:              Any                  = None   # SystemMetrics | None
    zero:             ZeroMetrics          = field(default_factory=ZeroMetrics)
    containers:       List[ContainerInfo]  = field(default_factory=list)
    docker_available: bool                 = False
    network:          NetworkInfo          = field(default_factory=NetworkInfo)
    temp_history:     List[float]          = field(default_factory=list)
    logs:             List[str]            = field(default_factory=list)
