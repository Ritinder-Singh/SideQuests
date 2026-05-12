#!/usr/bin/env python3
"""Runs on the Pi Zero. Prints a JSON metrics snapshot to stdout and exits."""

import json
import socket
import subprocess
import time

import psutil


def cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        for key in ("cpu_thermal", "coretemp", "k10temp"):
            if key in temps and temps[key]:
                return temps[key][0].current
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000.0
    except Exception:
        return None


def running_services():
    try:
        out = subprocess.check_output(
            ["systemctl", "list-units", "--type=service", "--state=running",
             "--no-pager", "--no-legend"],
            text=True,
        )
        return [
            line.split()[0].removesuffix(".service")
            for line in out.splitlines()
            if line.strip()
        ]
    except Exception:
        return []


def ssh_sessions():
    try:
        out = subprocess.check_output(["who"], text=True)
        sessions = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and "(" in line:
                ip = line[line.rfind("(") + 1: line.rfind(")")]
                sessions.append({"user": parts[0], "source_ip": ip})
        return sessions
    except Exception:
        return []


def main():
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    data = {
        "hostname":       socket.gethostname(),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "cpu_percent":    psutil.cpu_percent(interval=0.5),
        "cpu_temp":       cpu_temp(),
        "ram_total_mb":   ram.total   // (1024 * 1024),
        "ram_used_mb":    ram.used    // (1024 * 1024),
        "disk_total_mb":  disk.total  // (1024 * 1024),
        "disk_used_mb":   disk.used   // (1024 * 1024),
        "services":       running_services(),
        "ssh_sessions":   ssh_sessions(),
    }
    print(json.dumps(data))


if __name__ == "__main__":
    main()
