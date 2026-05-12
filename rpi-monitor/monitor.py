#!/usr/bin/env python3
"""Main entry point — event loop, auto-rotating tabs, background data collection."""

import copy
import os
import sys
import threading
import time

import pygame

import config
import docker_manager
import log_viewer
import network_info
from framebuffer import Framebuffer
from metrics import MetricsCollector
from renderer import Fonts, Renderer
from state import AppData
from zero_client import ZeroClient

# Max temperature history points (30 min at 1/sec = 1800)
_MAX_TEMP_HISTORY = 1800


def main():
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    pygame.init()

    surface  = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    fb       = Framebuffer("/dev/fb0")
    fonts    = Fonts()
    renderer = Renderer(surface, fonts)

    # ── Shared state ──────────────────────────────────────────────────────────
    state      = AppData()
    data_lock  = threading.Lock()
    stop_event = threading.Event()

    # ── Thread: Pi 5 metrics (every 1 s) ─────────────────────────────────────
    def _metrics_loop():
        collector = MetricsCollector()
        collector.collect()                 # prime cpu_percent
        while not stop_event.is_set():
            m = collector.collect()
            with data_lock:
                state.pi5 = m
                if m.cpu_temp is not None:
                    state.temp_history.append(m.cpu_temp)
                    if len(state.temp_history) > _MAX_TEMP_HISTORY:
                        state.temp_history = state.temp_history[-_MAX_TEMP_HISTORY:]
            stop_event.wait(config.REFRESH_SYSTEM)

    # ── Thread: Pi Zero (every 5 s) ───────────────────────────────────────────
    def _zero_loop():
        client = ZeroClient()
        while not stop_event.is_set():
            z = client.fetch()
            with data_lock:
                state.zero = z
            stop_event.wait(config.REFRESH_ZERO)
        client.close()

    # ── Thread: Docker (every 5 s) ────────────────────────────────────────────
    def _docker_loop():
        while not stop_event.is_set():
            containers, available = docker_manager.get_containers()
            with data_lock:
                state.containers       = containers
                state.docker_available = available
            stop_event.wait(config.REFRESH_DOCKER)

    # ── Thread: Network (every 5 s) ───────────────────────────────────────────
    def _network_loop():
        while not stop_event.is_set():
            net = network_info.collect()
            with data_lock:
                state.network = net
            stop_event.wait(config.REFRESH_NETWORK)

    # ── Thread: Logs (every 30 s) ─────────────────────────────────────────────
    def _log_loop():
        while not stop_event.is_set():
            logs = log_viewer.get_recent_logs(30)
            with data_lock:
                state.logs = logs
            stop_event.wait(30)

    for fn_loop in (_metrics_loop, _zero_loop, _docker_loop, _network_loop, _log_loop):
        threading.Thread(target=fn_loop, daemon=True).start()

    # ── State ─────────────────────────────────────────────────────────────────
    active_tab  = 0
    last_rotate = time.time()
    clock       = pygame.time.Clock()
    running     = True

    # ── Main loop ─────────────────────────────────────────────────────────────
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    active_tab  = (active_tab + 1) % config.TAB_COUNT
                    last_rotate = time.time()
                elif event.key == pygame.K_LEFT:
                    active_tab  = (active_tab - 1) % config.TAB_COUNT
                    last_rotate = time.time()

        # Auto-rotate
        if time.time() - last_rotate >= config.AUTO_ROTATE_INTERVAL:
            active_tab  = (active_tab + 1) % config.TAB_COUNT
            last_rotate = time.time()

        # Snapshot state for rendering (brief lock)
        with data_lock:
            snap = AppData(
                pi5              = state.pi5,
                zero             = state.zero,
                containers       = list(state.containers),
                docker_available = state.docker_available,
                network          = state.network,
                temp_history     = list(state.temp_history),
                logs             = list(state.logs),
            )

        renderer.draw(snap, active_tab, badge_counts=[0] * config.TAB_COUNT)
        fb.flush(surface)
        clock.tick(config.FPS)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    stop_event.set()
    fb.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
