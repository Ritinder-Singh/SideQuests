# Raspberry Pi 5 System Monitor & Control Panel

## Project Overview

Build a Python-based system monitoring dashboard and control panel that runs on a Raspberry Pi 5 with a 3.5-inch SPI TFT touchscreen (480×320, XPT2046 touch controller). The app displays real-time system stats for both the Pi 5 and a Pi Zero connected via USB gadget mode, Docker container management, thermal controls, network monitoring, security monitoring, and touch-based controls — all optimized for a small screen.

## Tech Stack

- Python 3 with `pygame` for rendering and touch input
- `psutil` for local system metrics
- `docker` Python SDK for container management
- `paramiko` (SSH) for Pi Zero remote metrics collection
- `RPi.GPIO` or `gpiozero` for fan control via GPIO
- No web server, no browser — direct framebuffer rendering

---

## Pi Zero USB Gadget Communication

- The Pi Zero is connected via USB gadget mode, appearing as `usb0` network interface on the Pi 5
- Pi Zero has a static IP on the USB network (e.g., `10.0.0.2`, configurable in `config.py`)
- Metrics collected over SSH using `paramiko` every 5 seconds
- A lightweight agent script (`zero_agent.py`) runs on the Pi Zero, outputs JSON with CPU, RAM, temp, disk, uptime, running services, and active SSH sessions
- If Pi Zero is unreachable, show "Offline" with last-seen timestamp and a "Retry" button
- SSH connection pooling: keep one persistent connection, reconnect on failure

---

## UI Structure

Tabbed interface with a tab bar along the bottom. Tap a tab to switch, or swipe left/right. 7 tabs total — use small icons + short labels in the tab bar to fit.

### Tab 1: System Overview (Pi 5)

- Top bar: hostname, current time, uptime
- CPU usage per core as small bar graphs + overall CPU % in large text
- CPU temperature with color coding (green < 60°C, yellow 60–75°C, red > 75°C)
- RAM usage bar + used/total in text
- Disk usage bar (SSD) + used/total for root partition
- Network stats: current upload/download speed
- IP address on the local network
- Power status from `vcgencmd`: healthy / throttled / undervoltage — show a small icon, red warning if throttled or undervoltage detected
- Alert badge count if any active alerts exist

### Tab 2: Pi Zero Status

- Connection status indicator: green dot = connected, red = offline (with last-seen time)
- Hostname and uptime
- CPU usage (single core — one bar + percentage)
- CPU temperature with color coding
- RAM usage bar + used/total
- Disk usage bar + used/total
- Running services list (whatever the Zero is running)
- Touch buttons:
  - Reboot Pi Zero (with confirmation)
  - Shutdown Pi Zero (with confirmation)
  - Restart a specific service on the Zero (configurable list in config)

### Tab 3: Docker Containers

- Scrollable list of all containers (running and stopped)
- Each container row shows: name, status (green dot = running, red = stopped, yellow = restarting), CPU %, memory usage
- Tap a container to open a detail/action overlay:
  - Start / Stop / Restart buttons
  - View last 20 lines of logs (scrollable text area)
- Per-container bandwidth usage if available
- Auto-refresh every 5 seconds

### Tab 4: Quick Actions

- Touch button grid, each button large enough to tap reliably (minimum 40×40px)
- Actions:
  - Reboot Pi 5 (with confirmation dialog)
  - Shutdown Pi 5 (with confirmation dialog)
  - Reboot Pi Zero (with confirmation)
  - Restart all Docker containers (with confirmation)
  - Toggle GPIO pin (fan manual override, relay, etc.)
  - Run custom shell commands (preconfigured list in `config.py`, e.g., "Update system", "Clear Docker cache", "Backup DB", "Sync files to Zero")
- System update badge: shows "X updates available" — fetched via `apt list --upgradable` every 6 hours in background. Security updates highlighted in red. One-tap "Update now" button
- Every destructive action requires a confirm/cancel dialog

### Tab 5: Network & Security

- Wi-Fi signal strength and SSID
- USB gadget link status (usb0 interface up/down, IP assigned)
- Connected devices on local network (ARP scan via `arp -a`)
- Public IP address (cached, refreshed every 10 minutes)
- Ping latency to key endpoints (8.8.8.8, router, Pi Zero)
- Bandwidth monitor: current speed + daily and weekly cumulative totals (stored in a local JSON file, reset weekly)
- **SSH session monitor**: active SSH connections to both Pi 5 and Pi Zero — show source IP, username, connection duration. Unexpected sessions highlighted in yellow

### Tab 6: Thermal & Fan Control

- Current CPU temperature with large display and color coding
- Temperature history graph (last 30 minutes, simple line chart in pygame)
- Fan status: current speed / on / off
- Fan mode toggle: Auto / Manual
- Auto fan curve configuration (displayed as a simple visual):
  - Off below 50°C
  - Low speed at 60°C (PWM duty cycle configurable)
  - Full speed at 70°C
  - Configurable thresholds in `config.py`
- Manual override: slider or buttons to set fan speed (0%, 25%, 50%, 75%, 100%)
- Pi Zero temperature shown for reference

### Tab 7: Logs & History

- **Log viewer**: scrollable view of recent syslog or journalctl output, filtered by error/warning level. Touch to scroll. Filter buttons: All / Error / Warning
- **Alert history**: chronological list of all triggered alerts with timestamps
  - Container crashed at 14:32
  - CPU temp exceeded 75°C at 09:15
  - Pi Zero went offline at 22:41
  - Undervoltage detected at 11:03
- **Uptime & reliability tracker**:
  - Pi 5 uptime history: "Running 42 days, last reboot May 1"
  - Pi Zero uptime history: "Rebooted 3 days ago, before that ran 28 days"
  - Per-container uptime: "nginx: 12 days, postgres: 12 days, redis: restarted 6 hours ago"
  - Data persisted to a local JSON file so it survives reboots
- **SSD health**: total bytes written (from `/proc/diskstats`), SMART data if available via `smartctl`, estimated remaining lifespan based on drive TBW rating (configurable in `config.py`)

---

## Alerts & Notifications System

A global alert system that works across all tabs:

**Alert triggers (all configurable thresholds in `config.py`):**
- CPU temperature > 75°C (warning) or > 80°C (critical)
- CPU usage > 90% sustained for 30 seconds
- RAM usage > 90%
- Disk usage > 85%
- Docker container crashed or stopped unexpectedly
- Pi Zero went offline
- Undervoltage or throttling detected via `vcgencmd`
- SSD health warning (bytes written approaching TBW limit)
- Unknown SSH session detected
- Network interface down

**Alert behavior:**
- Screen border flashes red for critical alerts, yellow for warnings
- Alert icon + count badge on the tab bar, visible from any tab
- Alert history stored persistently (JSON file) with timestamps
- Alerts auto-dismiss after being acknowledged (tap to dismiss)
- Audible beep option via GPIO buzzer (configurable, off by default)

---

## Quick-Glance Screensaver / Dashboard Mode

After 60 seconds of no touch input, switch to a minimal "glance" mode:
- Large clock display
- CPU temp in large text with color
- Container summary: "8 running / 0 stopped"
- Pi Zero status: "Online" or "Offline"
- Active alert count
- Power status icon
- Fan status icon
- All in large, readable text — visible from across the room
- Tap anywhere to return to full UI
- Dims the display slightly to reduce power and wear

---

## Design Requirements

- Dark background (`#0d1117`) with light text
- Monospace font (DejaVu Sans Mono, bundled with Raspbian)
- Color-coded bars: green for low usage, yellow for medium, red for high
- Touch targets minimum 40×40px for reliable finger tapping
- Dirty rect rendering — only redraw changed areas, no full-screen redraws except tab switches
- Confirmation dialogs for ALL destructive actions (two-tap confirm, no exceptions)
- Smooth tab switching with minimal latency
- Visual touch feedback: brief color flash on button press

**Refresh rates:**
- System metrics: every 1 second
- Docker containers: every 5 seconds
- Pi Zero stats: every 5 seconds
- Network/bandwidth: every 5 seconds for speed, cumulative totals saved every 60 seconds
- System updates check: every 6 hours
- SSD health: every hour
- SSH sessions: every 10 seconds
- Screensaver timeout: 60 seconds of no touch

---

## File Structure

```
rpi-monitor/
├── monitor.py              # Main entry point, event loop, tab management, screensaver logic
├── metrics.py              # psutil wrapper for local Pi 5 system metrics
├── zero_client.py          # SSH client for Pi Zero: connect, fetch metrics, send commands
├── zero_agent.py           # Deployed ON the Pi Zero: collects metrics, outputs JSON
├── docker_manager.py       # Docker SDK wrapper: list, start, stop, restart, logs
├── network_info.py         # Network stats, ARP scan, public IP, ping, usb0 status,
│                           #   bandwidth tracking with daily/weekly totals
├── thermal_manager.py      # CPU temp monitoring, fan control via GPIO PWM,
│                           #   fan curves, manual override, temp history buffer
├── power_monitor.py        # vcgencmd wrapper: throttle status, undervoltage detection
├── ssd_health.py           # SSD health via /proc/diskstats and smartctl,
│                           #   bytes written tracking, lifespan estimation
├── update_checker.py       # Background apt update check, parse upgradable packages,
│                           #   identify security updates
├── ssh_monitor.py          # Parse active SSH sessions on Pi 5 and Pi Zero,
│                           #   flag unknown sessions
├── uptime_tracker.py       # Track and persist uptime history for Pi 5, Pi Zero,
│                           #   and all Docker containers
├── alert_manager.py        # Central alert system: trigger, store, dismiss, persist,
│                           #   alert history, threshold checks
├── log_viewer.py           # Read and filter journalctl/syslog output,
│                           #   buffer recent entries for display
├── renderer.py             # Pygame rendering: layout engine, tab system, dirty rects,
│                           #   screensaver/glance mode
├── widgets.py              # Reusable UI components:
│                           #   - Buttons, progress bars, status dots
│                           #   - Confirmation dialogs, modal overlays
│                           #   - Scrollable lists, scrollable text areas
│                           #   - Tab bar with icons and badge counts
│                           #   - Line chart (for temp history)
│                           #   - Toggle switches, sliders
├── touch_handler.py        # Touch input processing:
│                           #   - Tap detection with 200ms debounce
│                           #   - Swipe detection (horizontal > 50px = tab switch)
│                           #   - Long press (1.5s) for context menus
│                           #   - Map screen coordinates to UI elements
│                           #   - Inactivity timer for screensaver
├── actions.py              # Quick action definitions and execution with confirmation flow
├── config.py               # All configurables:
│                           #   - Colors, fonts, dimensions
│                           #   - Refresh rates per data source
│                           #   - Pi Zero IP, SSH user, key path
│                           #   - Fan curve thresholds and GPIO pin
│                           #   - Alert thresholds
│                           #   - SSD TBW rating for lifespan estimation
│                           #   - Custom command list [{label, command}]
│                           #   - Ping targets list
│                           #   - Docker socket path
│                           #   - Screensaver timeout
│                           #   - Buzzer GPIO pin (optional)
├── data/                   # Persistent data directory
│                           #   - alert_history.json
│                           #   - uptime_history.json
│                           #   - bandwidth_totals.json
│                           #   - ssd_write_log.json
├── install.sh              # Setup script for the Pi 5
├── install_zero.sh         # Setup script for the Pi Zero
└── rpi-monitor.service     # systemd unit file for auto-start on Pi 5
```

---

## Install Scripts

### install.sh (runs on Pi 5)

- Install system packages: `python3-pygame`, `python3-pip`, `fonts-dejavu`, `smartmontools`
- Pip install: `psutil`, `docker`, `paramiko`, `gpiozero` (or `RPi.GPIO`)
- Create `/home/pi/rpi-monitor/data/` directory for persistent data files
- Generate SSH key pair if not present
- Print instructions to copy pubkey to Pi Zero
- Copy `rpi-monitor.service` to `/etc/systemd/system/`
- Enable and start the service
- Add service user to the `docker` group and `gpio` group

### install_zero.sh (runs on Pi Zero)

- Copy `zero_agent.py` to `/usr/local/bin/`
- Pip install `psutil` on the Zero
- Set up authorized_keys for passwordless SSH from Pi 5
- Optionally configure static IP for usb0 interface
- Print confirmation message

### rpi-monitor.service

- Run as root (needed for framebuffer, GPIO, docker socket)
- Environment: `SDL_FBDEV=/dev/fb1`, `SDL_MOUSEDEV=/dev/input/touchscreen`
- Restart on failure with 5-second delay
- Start after `docker.service` and `network-online.target`
- WorkingDirectory: `/home/pi/rpi-monitor`

---

## zero_agent.py Behavior

When invoked via `python3 /usr/local/bin/zero_agent.py`, prints a single JSON object to stdout and exits:

```json
{
  "hostname": "pizero",
  "uptime_seconds": 84200,
  "cpu_percent": 23.5,
  "cpu_temp": 48.2,
  "ram_total_mb": 512,
  "ram_used_mb": 210,
  "disk_total_mb": 16000,
  "disk_used_mb": 4200,
  "services": ["pihole-FTL", "nginx", "sensor-logger"],
  "ssh_sessions": [
    {"user": "pi", "source_ip": "10.0.0.1", "duration_seconds": 3600}
  ]
}
```

The Pi 5 calls this over SSH every 5 seconds, parses the JSON, and updates Tab 2.

---

## Error Handling

- Docker socket missing → Tab 3 shows "Docker not available" with a retry button
- Pi Zero unreachable → Tab 2 shows "Offline" with last-seen timestamp and a "Retry" button
- Missing sensors (e.g., CPU temp not available) → show "N/A"
- Framebuffer fallback: try `/dev/fb1`, then `/dev/fb0`
- GPIO not available (running in dev mode) → fan control shows "GPIO unavailable"
- smartctl not installed or SSD doesn't support SMART → show "N/A" for SSD health
- SSH connection drops → auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)
- Corrupt persistent data files → recreate with defaults, log a warning
- Keep total CPU usage of the monitor itself under 5%

---

## Key Constraints

- Screen is 480×320 — prioritize readability over cramming data. Use tabs to spread information across screens rather than making any one tab too dense
- All text must be legible at arm's length — minimum font size 12px equivalent
- Touch targets 40×40px minimum — fat fingers on a small screen
- SPI displays are slow — no animations, no transparency blending, no anti-aliased rendering. Keep draw calls minimal
- The monitor itself must not become a resource hog — lazy refresh, dirty rects only, sleep between frames
- All persistent data stored as JSON in `data/` directory — no database dependency