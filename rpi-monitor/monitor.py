#!/usr/bin/env python3
"""Main entry point — event loop, auto-rotating tab display."""

import os
import sys
import threading
import time

import pygame

import config
from framebuffer import Framebuffer
from metrics import MetricsCollector
from renderer import Fonts, Renderer


def main():
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    pygame.init()

    surface  = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    fb       = Framebuffer("/dev/fb1")
    fonts    = Fonts()
    renderer = Renderer(surface, fonts)

    # ── Background metrics thread ─────────────────────────────────────────────
    stop_event   = threading.Event()
    metrics_lock = threading.Lock()
    latest: list = [None]

    def _metrics_loop():
        collector = MetricsCollector()
        collector.collect()
        while not stop_event.is_set():
            m = collector.collect()
            with metrics_lock:
                latest[0] = m
            stop_event.wait(config.REFRESH_SYSTEM)

    threading.Thread(target=_metrics_loop, daemon=True).start()

    # ── State ─────────────────────────────────────────────────────────────────
    active_tab     = 0
    last_rotate    = time.time()
    clock          = pygame.time.Clock()
    running        = True

    # ── Main loop ─────────────────────────────────────────────────────────────
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    active_tab = (active_tab + 1) % config.TAB_COUNT
                    last_rotate = time.time()
                elif event.key == pygame.K_LEFT:
                    active_tab = (active_tab - 1) % config.TAB_COUNT
                    last_rotate = time.time()

        # ── Auto-rotate tabs ──────────────────────────────────────────────────
        if time.time() - last_rotate >= config.AUTO_ROTATE_INTERVAL:
            active_tab = (active_tab + 1) % config.TAB_COUNT
            last_rotate = time.time()

        # ── Render → framebuffer ──────────────────────────────────────────────
        with metrics_lock:
            metrics = latest[0]

        renderer.draw(
            metrics      = metrics,
            active_tab   = active_tab,
            badge_counts = [0] * config.TAB_COUNT,
        )
        fb.flush(surface)

        clock.tick(config.FPS)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    stop_event.set()
    fb.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
