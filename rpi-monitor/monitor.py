#!/usr/bin/env python3
"""Main entry point — event loop, tab management, screensaver."""

import os
import sys
import threading

import pygame

import config
from framebuffer import Framebuffer
from metrics import MetricsCollector
from renderer import Fonts, Renderer
from touch_handler import TouchHandler


def main():
    # Render offscreen — display output goes to /dev/fb1 via Framebuffer
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    pygame.init()

    surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    fb       = Framebuffer("/dev/fb1")
    fonts    = Fonts()
    renderer = Renderer(surface, fonts)
    touch    = TouchHandler()

    # ── Background metrics thread ─────────────────────────────────────────────
    stop_event   = threading.Event()
    metrics_lock = threading.Lock()
    latest: list = [None]

    def _metrics_loop():
        collector = MetricsCollector()
        collector.collect()                 # prime cpu_percent counters
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

        # ── Render to surface, then push to display ───────────────────────────
        with metrics_lock:
            metrics = latest[0]

        renderer.draw(
            metrics      = metrics,
            active_tab   = active_tab,
            screensaver  = screensaver,
            badge_counts = [0] * config.TAB_COUNT,
            dialog       = dialog,
        )
        fb.flush(surface)

        clock.tick(config.FPS)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    stop_event.set()
    metrics_thread.join(timeout=3)
    fb.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
