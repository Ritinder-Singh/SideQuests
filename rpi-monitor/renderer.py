import os
import time
from typing import List, Optional, Tuple

import pygame

import config
from state import AppData, ContainerInfo, NetworkInfo, ZeroMetrics
from widgets import TabBar, draw_progress_bar, draw_status_dot

Color = Tuple[int, int, int]
CONTENT_H = config.SCREEN_HEIGHT - config.TAB_HEIGHT  # 276 px

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
]


# ── Font loader ───────────────────────────────────────────────────────────────

class Fonts:
    def __init__(self):
        pygame.font.init()
        ttf = next((p for p in _FONT_PATHS if os.path.exists(p)), None)
        if ttf:
            self.small  = pygame.font.Font(ttf, config.FONT_SIZE_SMALL)
            self.normal = pygame.font.Font(ttf, config.FONT_SIZE_NORMAL)
            self.large  = pygame.font.Font(ttf, config.FONT_SIZE_LARGE)
            self.xlarge = pygame.font.Font(ttf, config.FONT_SIZE_XLARGE)
        else:
            self.small  = pygame.font.Font(None, config.FONT_SIZE_SMALL  + 4)
            self.normal = pygame.font.Font(None, config.FONT_SIZE_NORMAL + 4)
            self.large  = pygame.font.Font(None, config.FONT_SIZE_LARGE  + 4)
            self.xlarge = pygame.font.Font(None, config.FONT_SIZE_XLARGE + 4)


# ── Renderer ──────────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts):
        self.screen  = screen
        self.fonts   = fonts
        self.tab_bar = TabBar(config.TAB_LABELS, fonts.small)

    def draw(
        self,
        state:        AppData,
        active_tab:   int = 0,
        badge_counts: Optional[List[int]] = None,
    ):
        self.screen.fill(config.BG_COLOR)
        self.tab_bar.active = active_tab
        self._route(active_tab, state)
        self.tab_bar.draw(self.screen, badge_counts)

    # ── Tab routing ───────────────────────────────────────────────────────────

    def _route(self, tab: int, state: AppData):
        if   tab == 0: self._tab_overview(state.pi5)
        elif tab == 1: self._tab_zero(state.zero)
        elif tab == 2: self._tab_docker(state.containers, state.docker_available)
        elif tab == 3: self._tab_actions()
        elif tab == 4: self._tab_network(state.network, state.pi5)
        elif tab == 5: self._tab_thermal(state.pi5, state.zero, state.temp_history)
        elif tab == 6: self._tab_logs(state.logs)

    # ── Tab 1: System Overview ────────────────────────────────────────────────

    def _tab_overview(self, m):
        if m is None:
            self._center("Collecting metrics…", CONTENT_H // 2)
            return

        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        # header
        scr.blit(fn.normal.render(m.hostname, True, config.BLUE), (lm, y))
        ts = fn.normal.render(time.strftime("%H:%M:%S"), True, config.DIM_COLOR)
        scr.blit(ts, (config.SCREEN_WIDTH // 2 - ts.get_width() // 2, y))
        up = fn.small.render(f"up {_fmt_uptime(m.uptime_seconds)}", True, config.DIM_COLOR)
        scr.blit(up, (config.SCREEN_WIDTH - up.get_width() - lm, y + 2))

        y += 22
        self._hline(y); y += 5

        # CPU
        scr.blit(fn.small.render("CPU", True, config.DIM_COLOR), (lm, y + 3))
        cpu_s = fn.large.render(f"{m.cpu_percent:5.1f}%", True, _pct_color(m.cpu_percent))
        scr.blit(cpu_s, (lm + 28, y - 2))
        cx, cw, ch = lm + 110, 18, 16
        for i, p in enumerate(m.cpu_per_core):
            draw_progress_bar(scr, cx + i * (cw + 3), y + 2, cw, ch, p)
        t_s = fn.normal.render(
            f"{m.cpu_temp:.1f}°C" if m.cpu_temp is not None else "N/A",
            True, _temp_color(m.cpu_temp) if m.cpu_temp else config.DIM_COLOR,
        )
        scr.blit(t_s, (config.SCREEN_WIDTH - t_s.get_width() - lm, y + 2))
        y += 25

        # RAM
        bar_x, bar_w = lm + 36, config.SCREEN_WIDTH - lm - 36 - 130
        scr.blit(fn.small.render("RAM", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, m.ram_percent)
        ram_gb = f"{m.ram_used_mb/1024:.1f}G/{m.ram_total_mb/1024:.1f}G {m.ram_percent:.0f}%"
        scr.blit(fn.small.render(ram_gb, True, config.TEXT_COLOR), (bar_x + bar_w + 5, y + 3))
        y += 22

        # Disk
        scr.blit(fn.small.render("DSK", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, m.disk_percent)
        dsk = f"{m.disk_used_gb:.1f}G/{m.disk_total_gb:.1f}G {m.disk_percent:.0f}%"
        scr.blit(fn.small.render(dsk, True, config.TEXT_COLOR), (bar_x + bar_w + 5, y + 3))
        y += 22

        # Network
        net = f"↑{_fmt_kbps(m.net_upload_kbps)}  ↓{_fmt_kbps(m.net_download_kbps)}    {m.local_ip}"
        scr.blit(fn.small.render(net, True, config.DIM_COLOR), (lm, y))
        y += 18

        # Power
        pc, pt = _power_label(m)
        draw_status_dot(scr, lm + 5, y + 7, pc)
        scr.blit(fn.small.render(pt, True, pc), (lm + 14, y))

    # ── Tab 2: Pi Zero Status ─────────────────────────────────────────────────

    def _tab_zero(self, z: ZeroMetrics):
        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        # status header
        dot_color = config.GREEN if z.online else config.RED
        draw_status_dot(scr, lm + 5, y + 8, dot_color)
        status_text = "ONLINE" if z.online else "OFFLINE"
        scr.blit(fn.normal.render(status_text, True, dot_color), (lm + 16, y))

        if z.online:
            host_s = fn.normal.render(z.hostname, True, config.BLUE)
            scr.blit(host_s, (config.SCREEN_WIDTH // 2 - host_s.get_width() // 2, y))
            up = fn.small.render(f"up {_fmt_uptime(z.uptime_seconds)}", True, config.DIM_COLOR)
            scr.blit(up, (config.SCREEN_WIDTH - up.get_width() - lm, y + 2))
        elif z.last_seen:
            ago = int(time.time() - z.last_seen)
            seen = fn.small.render(f"last seen {_fmt_uptime(ago)} ago", True, config.DIM_COLOR)
            scr.blit(seen, (config.SCREEN_WIDTH - seen.get_width() - lm, y + 2))

        y += 22; self._hline(y); y += 6

        if not z.online:
            self._center("Pi Zero unreachable", CONTENT_H // 2, config.DIM_COLOR)
            return

        bar_x, bar_w = lm + 36, config.SCREEN_WIDTH - lm - 36 - 130

        # CPU
        scr.blit(fn.small.render("CPU", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, z.cpu_percent)
        scr.blit(
            fn.small.render(f"{z.cpu_percent:.1f}%", True, _pct_color(z.cpu_percent)),
            (bar_x + bar_w + 5, y + 3),
        )
        if z.cpu_temp is not None:
            t_s = fn.small.render(f"{z.cpu_temp:.1f}°C", True, _temp_color(z.cpu_temp))
            scr.blit(t_s, (config.SCREEN_WIDTH - t_s.get_width() - lm, y + 3))
        y += 20

        # RAM
        ram_pct = z.ram_used_mb / max(z.ram_total_mb, 1) * 100
        scr.blit(fn.small.render("RAM", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, ram_pct)
        ram_s = f"{z.ram_used_mb/1024:.2f}G/{z.ram_total_mb/1024:.2f}G"
        scr.blit(fn.small.render(ram_s, True, config.TEXT_COLOR), (bar_x + bar_w + 5, y + 3))
        y += 20

        # Disk
        disk_pct = z.disk_used_mb / max(z.disk_total_mb, 1) * 100
        scr.blit(fn.small.render("DSK", True, config.DIM_COLOR), (lm, y + 3))
        draw_progress_bar(scr, bar_x, y + 2, bar_w, 14, disk_pct)
        dsk_s = f"{z.disk_used_mb/1024:.1f}G/{z.disk_total_mb/1024:.1f}G"
        scr.blit(fn.small.render(dsk_s, True, config.TEXT_COLOR), (bar_x + bar_w + 5, y + 3))
        y += 22

        self._hline(y); y += 5

        # Services
        scr.blit(fn.small.render("SERVICES", True, config.DIM_COLOR), (lm, y))
        y += 15
        if z.services:
            # Lay them out in rows
            x = lm
            for svc in z.services[:12]:
                draw_status_dot(scr, x + 4, y + 6, config.GREEN, radius=3)
                s = fn.small.render(svc, True, config.TEXT_COLOR)
                scr.blit(s, (x + 11, y))
                x += s.get_width() + 22
                if x > config.SCREEN_WIDTH - 80:
                    x = lm; y += 14
        else:
            scr.blit(fn.small.render("none", True, config.DIM_COLOR), (lm, y))

    # ── Tab 3: Docker Containers ──────────────────────────────────────────────

    def _tab_docker(self, containers: list, available: bool):
        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        if not available:
            scr.blit(fn.normal.render("DOCKER", True, config.DIM_COLOR), (lm, y))
            self._center("Docker not available", CONTENT_H // 2, config.DIM_COLOR)
            return

        running = sum(1 for c in containers if c.status == "running")
        stopped = len(containers) - running
        hdr = fn.normal.render("DOCKER", True, config.TEXT_COLOR)
        scr.blit(hdr, (lm, y))
        summary = fn.small.render(
            f"{running} running  {stopped} stopped", True, config.DIM_COLOR
        )
        scr.blit(summary, (config.SCREEN_WIDTH - summary.get_width() - lm, y + 3))
        y += 20; self._hline(y); y += 4

        if not containers:
            self._center("No containers found", CONTENT_H // 2, config.DIM_COLOR)
            return

        row_h = 18
        max_rows = (CONTENT_H - y) // row_h

        for c in containers[:max_rows]:
            if c.status == "running":
                dot_c = config.GREEN
            elif c.status == "restarting":
                dot_c = config.YELLOW
            else:
                dot_c = config.RED

            draw_status_dot(scr, lm + 4, y + row_h // 2, dot_c, radius=4)

            # name (truncated)
            name = c.name[:22]
            scr.blit(fn.small.render(name, True, config.TEXT_COLOR), (lm + 13, y + 3))

            if c.status == "running":
                cpu_s = fn.small.render(f"{c.cpu_percent:4.1f}%", True, _pct_color(c.cpu_percent))
                mem_s = fn.small.render(f"{c.mem_mb:.0f}M", True, config.DIM_COLOR)
                scr.blit(cpu_s, (config.SCREEN_WIDTH - 90, y + 3))
                scr.blit(mem_s, (config.SCREEN_WIDTH - mem_s.get_width() - lm, y + 3))
            else:
                st_s = fn.small.render(c.status, True, config.DIM_COLOR)
                scr.blit(st_s, (config.SCREEN_WIDTH - st_s.get_width() - lm, y + 3))

            y += row_h

        if len(containers) > max_rows:
            more = fn.small.render(
                f"+ {len(containers) - max_rows} more", True, config.DIM_COLOR
            )
            scr.blit(more, (lm, y))

    # ── Tab 4: Quick Actions (display-only) ───────────────────────────────────

    def _tab_actions(self):
        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        scr.blit(fn.normal.render("QUICK ACTIONS", True, config.TEXT_COLOR), (lm, y))
        note = fn.small.render("add physical buttons to trigger", True, config.DIM_COLOR)
        scr.blit(note, (config.SCREEN_WIDTH - note.get_width() - lm, y + 3))
        y += 20; self._hline(y); y += 8

        sections = [
            ("System", [
                "Reboot Pi 5",
                "Shutdown Pi 5",
                "Reboot Pi Zero",
                "Restart all Docker",
            ]),
            ("Custom", [c["label"] for c in config.CUSTOM_COMMANDS]),
        ]

        for title, items in sections:
            scr.blit(fn.small.render(title, True, config.DIM_COLOR), (lm, y))
            y += 14
            for item in items:
                scr.blit(fn.small.render(f"  ▸  {item}", True, config.TEXT_COLOR), (lm, y))
                y += 14
            y += 6

    # ── Tab 5: Network & Security ─────────────────────────────────────────────

    def _tab_network(self, net: NetworkInfo, pi5):
        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        scr.blit(fn.normal.render("NETWORK", True, config.TEXT_COLOR), (lm, y))
        y += 20; self._hline(y); y += 6

        # WiFi row
        if net.wifi_signal_dbm is not None:
            sig_color = (
                config.GREEN  if net.wifi_signal_dbm > -60 else
                config.YELLOW if net.wifi_signal_dbm > -75 else
                config.RED
            )
            sig_s = fn.small.render(f"{net.wifi_signal_dbm} dBm", True, sig_color)
        else:
            sig_s = fn.small.render("N/A", True, config.DIM_COLOR)

        scr.blit(fn.small.render("WiFi", True, config.DIM_COLOR), (lm, y))
        ssid_s = fn.small.render(net.wifi_ssid, True, config.TEXT_COLOR)
        scr.blit(ssid_s, (lm + 34, y))
        scr.blit(sig_s, (config.SCREEN_WIDTH - sig_s.get_width() - lm, y))
        y += 16

        # IPs row
        scr.blit(fn.small.render("LAN", True, config.DIM_COLOR), (lm, y))
        lan_ip = pi5.local_ip if pi5 else "N/A"
        scr.blit(fn.small.render(lan_ip, True, config.TEXT_COLOR), (lm + 34, y))
        scr.blit(fn.small.render("PUB", True, config.DIM_COLOR), (240, y))
        scr.blit(fn.small.render(net.public_ip, True, config.TEXT_COLOR), (274, y))
        y += 16

        # USB0 row
        usb_dot = config.GREEN if net.usb0_up else config.RED
        draw_status_dot(scr, lm + 5, y + 7, usb_dot, radius=4)
        usb_text = f"USB0  {net.usb0_ip}" if net.usb0_up else "USB0  down"
        scr.blit(fn.small.render(usb_text, True, config.TEXT_COLOR), (lm + 14, y))

        # Bandwidth
        if pi5:
            bw = fn.small.render(
                f"↑{_fmt_kbps(pi5.net_upload_kbps)}  ↓{_fmt_kbps(pi5.net_download_kbps)}",
                True, config.DIM_COLOR,
            )
            scr.blit(bw, (config.SCREEN_WIDTH - bw.get_width() - lm, y))
        y += 20

        self._hline(y); y += 6
        scr.blit(fn.small.render("PING", True, config.DIM_COLOR), (lm, y))
        y += 14

        for pr in net.ping_results:
            label_s = fn.small.render(f"{pr.label}", True, config.DIM_COLOR)
            scr.blit(label_s, (lm, y))

            if pr.latency_ms is not None:
                ms_color = (
                    config.GREEN  if pr.latency_ms < 10  else
                    config.YELLOW if pr.latency_ms < 50  else
                    config.RED
                )
                ms_s = fn.small.render(f"{pr.latency_ms:.1f} ms", True, ms_color)
            else:
                ms_s = fn.small.render("timeout", True, config.RED)

            scr.blit(ms_s, (config.SCREEN_WIDTH - ms_s.get_width() - lm, y))
            y += 14

    # ── Tab 6: Thermal & Fan ──────────────────────────────────────────────────

    def _tab_thermal(self, pi5, zero: ZeroMetrics, temp_history: list):
        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        temp = pi5.cpu_temp if pi5 else None
        tc   = _temp_color(temp) if temp else config.DIM_COLOR

        # Large temperature display
        temp_str = f"{temp:.1f}°C" if temp is not None else "N/A"
        big = fn.xlarge.render(temp_str, True, tc)
        scr.blit(big, (lm, y))

        # Pi Zero temp for reference
        if zero.online and zero.cpu_temp is not None:
            zt = fn.small.render(
                f"Zero: {zero.cpu_temp:.1f}°C", True, _temp_color(zero.cpu_temp)
            )
            scr.blit(zt, (config.SCREEN_WIDTH - zt.get_width() - lm, y + 4))

        fan_s = fn.small.render("FAN: GPIO N/A", True, config.DIM_COLOR)
        scr.blit(fan_s, (config.SCREEN_WIDTH - fan_s.get_width() - lm, y + big.get_height() - 14))

        y += big.get_height() + 4
        self._hline(y); y += 6

        scr.blit(fn.small.render("TEMPERATURE HISTORY", True, config.DIM_COLOR), (lm, y))
        y += 14

        chart_rect = pygame.Rect(lm, y, config.SCREEN_WIDTH - lm * 2, CONTENT_H - y - 22)
        self._draw_chart(chart_rect, temp_history, min_v=30, max_v=90, color=tc)

        # Stats below chart
        if len(temp_history) >= 2:
            mn, mx, av = min(temp_history), max(temp_history), sum(temp_history) / len(temp_history)
            stats_s = fn.small.render(
                f"min {mn:.0f}°  avg {av:.0f}°  max {mx:.0f}°",
                True, config.DIM_COLOR,
            )
            scr.blit(stats_s, (lm, CONTENT_H - 18))

    # ── Tab 7: Logs & History ─────────────────────────────────────────────────

    def _tab_logs(self, logs: list):
        scr, fn, lm = self.screen, self.fonts, 8
        y = 6

        scr.blit(fn.normal.render("SYSTEM LOGS", True, config.TEXT_COLOR), (lm, y))
        y += 20; self._hline(y); y += 4

        if not logs:
            self._center("No logs available", CONTENT_H // 2, config.DIM_COLOR)
            return

        line_h = 12
        max_lines = (CONTENT_H - y) // line_h

        for line in logs[-max_lines:]:
            # Trim to fit screen width
            while fn.small.size(line)[0] > config.SCREEN_WIDTH - lm * 2 and len(line) > 10:
                line = line[:-4] + "…"
            color = (
                config.RED    if "error"   in line.lower() or "fail" in line.lower() else
                config.YELLOW if "warning" in line.lower() or "warn" in line.lower() else
                config.DIM_COLOR
            )
            scr.blit(fn.small.render(line, True, color), (lm, y))
            y += line_h

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _hline(self, y: int):
        pygame.draw.line(
            self.screen, config.BORDER_COLOR, (0, y), (config.SCREEN_WIDTH, y), 1
        )

    def _center(self, text: str, y: int, color: Color = config.TEXT_COLOR):
        s = self.fonts.normal.render(text, True, color)
        self.screen.blit(s, (config.SCREEN_WIDTH // 2 - s.get_width() // 2, y))

    def _draw_chart(
        self,
        rect: pygame.Rect,
        data: list,
        min_v: float,
        max_v: float,
        color: Color,
    ):
        pygame.draw.rect(self.screen, config.TAB_BG,       rect)
        pygame.draw.rect(self.screen, config.BORDER_COLOR, rect, 1)

        if len(data) < 2:
            return

        span = max_v - min_v
        if span == 0:
            return

        # Subsample if more points than pixels
        pts = data
        if len(pts) > rect.width:
            step = len(pts) / rect.width
            pts = [pts[int(i * step)] for i in range(rect.width)]

        n = len(pts)
        points = []
        for i, v in enumerate(pts):
            px = rect.x + int(i * rect.width / max(n - 1, 1))
            norm = (v - min_v) / span
            py = rect.bottom - int(norm * rect.height)
            py = max(rect.top, min(rect.bottom, py))
            points.append((px, py))

        pygame.draw.lines(self.screen, color, False, points, 2)


# ── Module-level helpers ──────────────────────────────────────────────────────

def _temp_color(temp) -> Color:
    if temp is None or temp < 60: return config.GREEN
    if temp < 75:                  return config.YELLOW
    return config.RED


def _pct_color(pct: float) -> Color:
    if pct < 60: return config.GREEN
    if pct < 80: return config.YELLOW
    return config.RED


def _power_label(m) -> Tuple[Color, str]:
    if m.power_status == "healthy":     return config.GREEN,  "PWR: OK"
    if m.power_status == "undervoltage": return config.RED,   "PWR: UNDERVOLTAGE"
    if m.power_status in ("throttled", "warning"): return config.YELLOW, "PWR: " + m.power_status.upper()
    return config.DIM_COLOR, "PWR: --"


def _fmt_uptime(s: int) -> str:
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m     = s // 60
    if d: return f"{d}d {h}h"
    if h: return f"{h}h {m}m"
    return f"{m}m"


def _fmt_kbps(kbps: float) -> str:
    return f"{kbps/1024:.1f}M/s" if kbps >= 1024 else f"{kbps:.0f}K/s"
