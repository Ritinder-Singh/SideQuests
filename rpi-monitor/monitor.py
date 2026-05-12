#!/usr/bin/env python3
"""Main entry point — event loop, tab management, screensaver."""

import os
import sys
import threading
import time

import pygame

import config
from metrics import MetricsCollector, SystemMetrics
from renderer import Fonts, Renderer
from touch_handler import TouchHandler


_HEADLESS_DRIVERS = ["kmsdrm", "fbcon", "directfb", "offscreen"]


def _init_display() -> pygame.Surface:
    """Initialize pygame display, trying multiple SDL video drivers as needed."""
    # Also detect a display server that's running locally but not exported (e.g. SSH session)
    if not os.environ.get("DISPLAY") and os.path.exists("/tmp/.X11-unix/X0"):
        os.environ["DISPLAY"] = ":0"
    if not os.environ.get("WAYLAND_DISPLAY"):
        for uid_dir in ("/run/user/1000", "/run/user/0"):
            if os.path.exists(f"{uid_dir}/wayland-1"):
                os.environ["WAYLAND_DISPLAY"] = "wayland-1"
                os.environ.setdefault("XDG_RUNTIME_DIR", uid_dir)
                break

    has_display_server = bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )

    if has_display_server:
        pygame.init()
        return pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    # Headless (SPI TFT / framebuffer) — set touch/fb env then probe drivers
    os.environ.setdefault("SDL_FBDEV",    "/dev/fb1")
    os.environ.setdefault("SDL_MOUSEDEV", "/dev/input/touchscreen")
    os.environ.setdefault("SDL_MOUSEDRV", "TSLIB")

    flags = pygame.FULLSCREEN | pygame.NOFRAME
    last_err: Exception = RuntimeError("no drivers tried")

    for driver in _HEADLESS_DRIVERS:
        os.environ["SDL_VIDEODRIVER"] = driver
        try:
            pygame.display.init()
            screen = pygame.display.set_mode(
                (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), flags
            )
            print(f"[display] using SDL_VIDEODRIVER={driver}")
            return screen
        except pygame.error as exc:
            last_err = exc
            pygame.display.quit()
            # also try /dev/fb0 if fb1 failed on this driver
            if os.environ.get("SDL_FBDEV") == "/dev/fb1":
                os.environ["SDL_FBDEV"] = "/dev/fb0"
                try:
                    pygame.display.init()
                    screen = pygame.display.set_mode(
                        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), flags
                    )
                    print(f"[display] using SDL_VIDEODRIVER={driver} SDL_FBDEV=/dev/fb0")
                    return screen
                except pygame.error as exc2:
                    last_err = exc2
                    pygame.display.quit()
                finally:
                    os.environ["SDL_FBDEV"] = "/dev/fb1"

    raise RuntimeError(
        f"Could not open a display with any driver {_HEADLESS_DRIVERS}. "
        f"Last error: {last_err}"
    )


def main():
    screen = _init_display()
    pygame.display.set_caption("RPi Monitor")
    pygame.mouse.set_visible(False)

    fonts    = Fonts()
    renderer = Renderer(screen, fonts)
    touch    = TouchHandler()

    # ── Background metrics thread ─────────────────────────────────────────────
    stop_event     = threading.Event()
    metrics_lock   = threading.Lock()
    latest: list   = [None]   # latest[0] = SystemMetrics | None

    def _metrics_loop():
        collector = MetricsCollector()
        collector.collect()                      # prime cpu_percent counters
        while not stop_event.is_set():
            m = collector.collect()
            with metrics_lock:
                latest[0] = m
            stop_event.wait(config.REFRESH_SYSTEM)

    metrics_thread = threading.Thread(target=_metrics_loop, daemon=True)
    metrics_thread.start()

    # ── State ─────────────────────────────────────────────────────────────────
    active_tab  = 0
    screensaver = False
    dialog      = None
    clock       = pygame.time.Clock()
    running     = True

    # ── Main loop ─────────────────────────────────────────────────────────────
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            elif event.type == pygame.KEYDOWN:
                touch.record_activity()
                screensaver = False
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    active_tab = min(active_tab + 1, config.TAB_COUNT - 1)
                elif event.key == pygame.K_LEFT:
                    active_tab = max(active_tab - 1, 0)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                touch.on_mouse_down(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                gesture = touch.on_mouse_up(event.pos)

                if screensaver:
                    screensaver = False
                    continue

                if dialog:
                    dialog.handle_tap(gesture["pos"])
                    continue

                if gesture["type"] == "tap":
                    hit = renderer.tab_bar.handle_tap(gesture["pos"])
                    if hit is not None:
                        active_tab = hit

                elif gesture["type"] == "swipe":
                    new = renderer.tab_bar.handle_swipe(gesture["dx"])
                    if new is not None:
                        active_tab = new

        # ── Screensaver ───────────────────────────────────────────────────────
        if not screensaver and touch.idle_seconds >= config.SCREENSAVER_TIMEOUT:
            screensaver = True

        # ── Render ────────────────────────────────────────────────────────────
        with metrics_lock:
            metrics = latest[0]

        renderer.draw(
            metrics      = metrics,
            active_tab   = active_tab,
            screensaver  = screensaver,
            badge_counts = [0] * config.TAB_COUNT,
            dialog       = dialog,
        )

        clock.tick(config.FPS)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    stop_event.set()
    metrics_thread.join(timeout=3)
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
