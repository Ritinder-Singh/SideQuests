import time
from typing import List, Optional, Tuple

import pygame

import config
from metrics import SystemMetrics
from widgets import (
    Button,
    ConfirmDialog,
    LineChart,
    TabBar,
    draw_progress_bar,
    draw_status_dot,
)

Color = Tuple[int, int, int]

CONTENT_H = config.SCREEN_HEIGHT - config.TAB_HEIGHT  # pixels above the tab bar


# ── Font loader ───────────────────────────────────────────────────────────────

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
]


class Fonts:
    def __init__(self):
        pygame.font.init()
        ttf = self._find_ttf()
        if ttf:
            self.small  = pygame.font.Font(ttf, config.FONT_SIZE_SMALL)
            self.normal = pygame.font.Font(ttf, config.FONT_SIZE_NORMAL)
            self.large  = pygame.font.Font(ttf, config.FONT_SIZE_LARGE)
            self.xlarge = pygame.font.Font(ttf, config.FONT_SIZE_XLARGE)
        else:
            # Last resort: pygame built-in (bitmap, will look pixelated)
            self.small  = pygame.font.Font(None, config.FONT_SIZE_SMALL  + 4)
            self.normal = pygame.font.Font(None, config.FONT_SIZE_NORMAL + 4)
            self.large  = pygame.font.Font(None, config.FONT_SIZE_LARGE  + 4)
            self.xlarge = pygame.font.Font(None, config.FONT_SIZE_XLARGE + 4)

    @staticmethod
    def _find_ttf() -> str | None:
        import os
        for path in _FONT_PATHS:
            if os.path.exists(path):
                return path
        return None


# ── Renderer ──────────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts):
        self.screen  = screen
        self.fonts   = fonts
        self.tab_bar = TabBar(config.TAB_LABELS, fonts.small)

        self._flash_color: Optional[Color] = None
        self._flash_until: float = 0.0

    def flash_border(self, color: Color, duration: float = 0.5):
        self._flash_color = color
        self._flash_until = time.time() + duration

    def draw(
        self,
        metrics:      Optional[SystemMetrics],
        active_tab:   int = 0,
        badge_counts: Optional[List[int]] = None,
    ):
        self.screen.fill(config.BG_COLOR)

        self.tab_bar.active = active_tab
        self._draw_content(active_tab, metrics)
        self.tab_bar.draw(self.screen, badge_counts)

        if self._flash_color and time.time() < self._flash_until:
            pygame.draw.rect(
                self.screen, self._flash_color,
                (0, 0, config.SCREEN_WIDTH, config.SCREEN_HEIGHT), 4,
            )

        # Caller (monitor.py) is responsible for flushing surface to /dev/fb1

    # ── Tab routing ───────────────────────────────────────────────────────────

    def _draw_content(self, tab: int, metrics: Optional[SystemMetrics]):
        if tab == 0:
            self._draw_overview(metrics)
        else:
            self._draw_placeholder(config.TAB_LABELS[tab])

    # ── Tab 1: System Overview ────────────────────────────────────────────────

    def _draw_overview(self, m: Optional[SystemMetrics]):
        if m is None:
            self._center_text("Collecting metrics…", CONTENT_H // 2)
            return

        scr = self.screen
        fn  = self.fonts
        lm  = 8   # left margin
        y   = 6

        # ── header row ───────────────────────────────────────────────────────
        host_surf = fn.normal.render(m.hostname, True, config.BLUE)
        scr.blit(host_surf, (lm, y))

        ts = fn.normal.render(time.strftime("%H:%M:%S"), True, config.DIM_COLOR)
        scr.blit(ts, (config.SCREEN_WIDTH // 2 - ts.get_width() // 2, y))

        up_surf = fn.small.render(f"up {_fmt_uptime(m.uptime_seconds)}", True, config.DIM_COLOR)
        scr.blit(up_surf, (config.SCREEN_WIDTH - up_surf.get_width() - lm, y + 2))

        y += 22
        pygame.draw.line(scr, config.BORDER_COLOR, (0, y), (config.SCREEN_WIDTH, y), 1)
        y += 5

        # ── CPU row ───────────────────────────────────────────────────────────
        scr.blit(fn.small.render("CPU", True, config.DIM_COLOR), (lm, y + 3))

        cpu_color = _pct_color(m.cpu_percent)
        cpu_surf  = fn.large.render(f"{m.cpu_percent:5.1f}%", True, cpu_color)
        scr.blit(cpu_surf, (lm + 28, y - 2))

        # per-core mini bars
        core_x, core_w, core_h, core_gap = lm + 110, 18, 16, 3
        for i, pct in enumerate(m.cpu_per_core):
            draw_progress_bar(scr, core_x + i * (core_w + core_gap), y + 2,
                              core_w, core_h, pct)

        # temperature (right side)
        if m.cpu_temp is not None:
            tc = _temp_color(m.cpu_temp)
            t_surf = fn.normal.render(f"{m.cpu_temp:.1f}°C", True, tc)
        else:
            t_surf = fn.normal.render("N/A", True, config.DIM_COLOR)
        scr.blit(t_surf, (config.SCREEN_WIDTH - t_surf.get_width() - lm, y + 2))

        y += 25

        # ── RAM row ───────────────────────────────────────────────────────────
        bar_x = lm + 36
        bar_w = config.SCREEN_WIDTH - bar_x - 130

        scr.blit(fn.small.render("RAM", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, m.ram_percent)
        ram_used_gb  = m.ram_used_mb  / 1024
        ram_total_gb = m.ram_total_mb / 1024
        ram_label = f"{ram_used_gb:.1f}G/{ram_total_gb:.1f}G {m.ram_percent:.0f}%"
        scr.blit(fn.small.render(ram_label, True, config.TEXT_COLOR),
                 (bar_x + bar_w + 5, y + 3))
        y += 22

        # ── Disk row ──────────────────────────────────────────────────────────
        scr.blit(fn.small.render("DSK", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, m.disk_percent)
        dsk_label = f"{m.disk_used_gb:.1f}G/{m.disk_total_gb:.1f}G {m.disk_percent:.0f}%"
        scr.blit(fn.small.render(dsk_label, True, config.TEXT_COLOR),
                 (bar_x + bar_w + 5, y + 3))
        y += 22

        # ── Network row ───────────────────────────────────────────────────────
        net_line = (
            f"↑{_fmt_kbps(m.net_upload_kbps)}"
            f"  ↓{_fmt_kbps(m.net_download_kbps)}"
            f"    {m.local_ip}"
        )
        scr.blit(fn.small.render(net_line, True, config.DIM_COLOR), (lm, y))
        y += 18

        # ── Power status ──────────────────────────────────────────────────────
        pwr_color, pwr_text = _power_label(m)
        draw_status_dot(scr, lm + 5, y + 7, pwr_color)
        scr.blit(fn.small.render(pwr_text, True, pwr_color), (lm + 14, y))

    # ── Screensaver / Glance mode ─────────────────────────────────────────────

    def _draw_screensaver(self, m: Optional[SystemMetrics]):
        if m is None:
            self._center_text("Loading…", config.SCREEN_HEIGHT // 2)
            return

        scr = self.screen
        fn  = self.fonts
        cx  = config.SCREEN_WIDTH // 2
        y   = 10

        # Clock
        clock_surf = fn.xlarge.render(time.strftime("%H:%M"), True, config.TEXT_COLOR)
        scr.blit(clock_surf, (cx - clock_surf.get_width() // 2, y))
        y += clock_surf.get_height() + 4

        date_surf = fn.small.render(time.strftime("%a %d %b"), True, config.DIM_COLOR)
        scr.blit(date_surf, (cx - date_surf.get_width() // 2, y))
        y += date_surf.get_height() + 14

        # CPU temp
        if m.cpu_temp is not None:
            tc   = _temp_color(m.cpu_temp)
            t_s  = fn.large.render(f"CPU  {m.cpu_temp:.1f}°C", True, tc)
        else:
            t_s  = fn.large.render("CPU  N/A", True, config.DIM_COLOR)
        scr.blit(t_s, (cx - t_s.get_width() // 2, y))
        y += t_s.get_height() + 6

        # Load
        load_surf = fn.normal.render(f"Load  {m.cpu_percent:.0f}%", True, config.DIM_COLOR)
        scr.blit(load_surf, (cx - load_surf.get_width() // 2, y))
        y += load_surf.get_height() + 8

        # Power warning (only if bad)
        if m.is_throttled or m.is_undervoltage:
            w_surf = fn.normal.render(
                "⚠ " + m.power_status.upper(), True, config.RED
            )
            scr.blit(w_surf, (cx - w_surf.get_width() // 2, y))

    # ── Placeholder ───────────────────────────────────────────────────────────

    def _draw_placeholder(self, name: str):
        self._center_text(f"[ {name} ]",  CONTENT_H // 2 - 20)
        self._center_text("Coming soon",  CONTENT_H // 2 + 10, config.DIM_COLOR)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _center_text(self, text: str, y: int, color: Color = config.TEXT_COLOR):
        surf = self.fonts.normal.render(text, True, color)
        self.screen.blit(surf, (config.SCREEN_WIDTH // 2 - surf.get_width() // 2, y))


# ── Module-level helpers ──────────────────────────────────────────────────────

def _temp_color(temp: float) -> Color:
    if temp < 60:
        return config.GREEN
    elif temp < 75:
        return config.YELLOW
    return config.RED


def _pct_color(pct: float) -> Color:
    if pct < 60:
        return config.GREEN
    elif pct < 80:
        return config.YELLOW
    return config.RED


def _power_label(m: SystemMetrics) -> Tuple[Color, str]:
    if m.power_status == "healthy":
        return config.GREEN, "PWR: OK"
    elif m.power_status == "undervoltage":
        return config.RED,    "PWR: UNDERVOLTAGE"
    elif m.power_status == "throttled":
        return config.YELLOW, "PWR: THROTTLED"
    elif m.power_status == "warning":
        return config.YELLOW, "PWR: WARNING"
    return config.DIM_COLOR, "PWR: --"


def _fmt_uptime(seconds: int) -> str:
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600)  // 60
    if d > 0:
        return f"{d}d {h}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _fmt_kbps(kbps: float) -> str:
    if kbps >= 1024:
        return f"{kbps / 1024:.1f}M/s"
    return f"{kbps:.0f}K/s"
