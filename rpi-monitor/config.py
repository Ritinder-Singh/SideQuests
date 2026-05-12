# Screen
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
FPS = 30

# Colors
BG_COLOR       = (13,  17,  23)
TEXT_COLOR     = (230, 237, 243)
DIM_COLOR      = (139, 148, 158)
GREEN          = (63,  185, 80)
YELLOW         = (210, 153, 34)
RED            = (248, 81,  73)
BLUE           = (88,  166, 255)
TAB_BG         = (22,  27,  34)
TAB_ACTIVE     = (33,  38,  45)
BORDER_COLOR   = (48,  54,  61)

# Fonts
FONT_MONO       = "DejaVu Sans Mono"
FONT_SIZE_SMALL  = 11
FONT_SIZE_NORMAL = 14
FONT_SIZE_LARGE  = 20
FONT_SIZE_XLARGE = 32

# Tab bar
TAB_HEIGHT = 44
TAB_COUNT  = 7
TAB_LABELS = ["Overview", "Pi Zero", "Docker", "Actions", "Network", "Thermal", "Logs"]

# Refresh rates (seconds)
REFRESH_SYSTEM         = 1
REFRESH_DOCKER         = 5
REFRESH_ZERO           = 5
REFRESH_NETWORK        = 5
REFRESH_BANDWIDTH_SAVE = 60
REFRESH_UPDATES        = 6 * 3600
REFRESH_SSD            = 3600
REFRESH_SSH            = 10
SCREENSAVER_TIMEOUT    = 60

# Pi Zero
ZERO_IP       = "10.0.0.2"
ZERO_SSH_USER = "pi"
ZERO_SSH_KEY  = "/home/pi/.ssh/id_rsa"
ZERO_SSH_PORT = 22

# Fan control
FAN_GPIO_PIN = 18
FAN_CURVE = [
    (0,   50),   # (duty_cycle_pct, temp_celsius)
    (25,  60),
    (100, 70),
]

# Alert thresholds
ALERT_CPU_TEMP_WARN      = 75
ALERT_CPU_TEMP_CRIT      = 80
ALERT_CPU_USAGE_WARN     = 90
ALERT_CPU_USAGE_DURATION = 30
ALERT_RAM_WARN           = 90
ALERT_DISK_WARN          = 85

# SSD TBW rating (terabytes written)
SSD_TBW_TB = 150

# Docker
DOCKER_SOCKET = "unix://var/run/docker.sock"

# Buzzer — set to a GPIO pin number to enable, None to disable
BUZZER_GPIO_PIN = None

# Touch (XPT2046 / ads7846)
# Path to the evdev input device — adjust if evtest shows a different eventX
TOUCH_DEVICE  = "/dev/input/event7"
# Raw ADC calibration range from the ads7846 overlay
TOUCH_X_MIN   = 200
TOUCH_X_MAX   = 3900
TOUCH_Y_MIN   = 200
TOUCH_Y_MAX   = 3900
# Axis transforms for landscape orientation — tweak if tap coordinates are wrong
TOUCH_SWAP_XY = False
TOUCH_FLIP_X  = False
TOUCH_FLIP_Y  = False

# Ping targets
PING_TARGETS = [
    ("8.8.8.8",    "Google DNS"),
    ("192.168.1.1","Router"),
    (ZERO_IP,      "Pi Zero"),
]

# Custom shell commands shown on the Quick Actions tab
CUSTOM_COMMANDS = [
    {"label": "Update system",      "command": "sudo apt-get update && sudo apt-get upgrade -y"},
    {"label": "Clear Docker cache", "command": "docker system prune -f"},
    {"label": "Sync to Zero",       "command": f"rsync -avz /home/pi/shared/ pi@{ZERO_IP}:/home/pi/shared/"},
]

# Data directory (persistent JSON files)
DATA_DIR              = "data"
ALERT_HISTORY_FILE    = f"{DATA_DIR}/alert_history.json"
UPTIME_HISTORY_FILE   = f"{DATA_DIR}/uptime_history.json"
BANDWIDTH_FILE        = f"{DATA_DIR}/bandwidth_totals.json"
SSD_LOG_FILE          = f"{DATA_DIR}/ssd_write_log.json"
