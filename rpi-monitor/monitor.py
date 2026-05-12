#!/usr/bin/env python3
"""Main entry point — event loop, tab management, screensaver."""

import os
import queue
import sys
import threading

import pygame

import config
from framebuffer import Framebuffer
from metrics import MetricsCollector
from renderer import Fonts, Renderer
from touch_handler import TouchHandler


def _start_touch_thread(
    event_queue: queue.Queue,
    stop_event: threading.Event,
) -> bool:
    """Read XPT2046 touch events via evdev and push (type, pos) onto event_queue.

    Returns True if the device was opened successfully, False otherwise.
    """
    try:
        import evdev  # type: ignore
    except ImportError:
        print("[touch] evdev not installed — run: uv add evdev")
        return False

    # Resolve device path: try config path, then scan for ads7846
    dev_path = config.TOUCH_DEVICE
    if not os.path.exists(dev_path):
        for d in evdev.list_devices():
            dev = evdev.InputDevice(d)
            if "ads7846" in dev.name.lower() or "xpt2046" in dev.name.lower():
                dev_path = d
                break
        else:
            print(f"[touch] device not found at {config.TOUCH_DEVICE} — "
                  "check dtoverlay=ads7846 in /boot/firmware/config.txt")
            return False

    def _map(raw_x: int, raw_y: int):
        if config.TOUCH_SWAP_XY:
            raw_x, raw_y = raw_y, raw_x

        x = (raw_x - config.TOUCH_X_MIN) / (config.TOUCH_X_MAX - config.TOUCH_X_MIN)
        y = (raw_y - config.TOUCH_Y_MIN) / (config.TOUCH_Y_MAX - config.TOUCH_Y_MIN)

        if config.TOUCH_FLIP_X:
            x = 1.0 - x
        if config.TOUCH_FLIP_Y:
            y = 1.0 - y

        sx = int(x * config.SCREEN_WIDTH)
        sy = int(y * config.SCREEN_HEIGHT)
        sx = max(0, min(config.SCREEN_WIDTH  - 1, sx))
        sy = max(0, min(config.SCREEN_HEIGHT - 1, sy))
        return sx, sy

    def _loop():
        import evdev
        try:
            dev = evdev.InputDevice(dev_path)
            print(f"[touch] reading from {dev_path} ({dev.name})")
        except Exception as exc:
            print(f"[touch] failed to open {dev_path}: {exc}")
            return

        raw_x = raw_y = 0
        for event in dev.read_loop():
            if stop_event.is_set():
                break
            if event.type == evdev.ecodes.EV_ABS:
                if event.code == evdev.ecodes.ABS_X:
                    raw_x = event.value
                elif event.code == evdev.ecodes.ABS_Y:
                    raw_y = event.value
            elif event.type == evdev.ecodes.EV_KEY:
                if event.code == evdev.ecodes.BTN_TOUCH:
                    pos = _map(raw_x, raw_y)
                    kind = "down" if event.value == 1 else "up"
                    event_queue.put((kind, pos))

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return True


def _process_gesture(gesture, touch, renderer, active_tab, screensaver, dialog):
    """Apply a resolved gesture to UI state. Returns updated (active_tab, screensaver)."""
    if screensaver:
        return active_tab, False

    if dialog:
        dialog.handle_tap(gesture["pos"])
        return active_tab, screensaver

    if gesture["type"] == "tap":
        hit = renderer.tab_bar.handle_tap(gesture["pos"])
        if hit is not None:
            active_tab = hit

    elif gesture["type"] == "swipe":
        new = renderer.tab_bar.handle_swipe(gesture["dx"])
        if new is not None:
            active_tab = new

    return active_tab, screensaver


def main():
    # Render offscreen — display output goes to /dev/fb1 via Framebuffer
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    pygame.init()

    surface  = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    fb       = Framebuffer("/dev/fb1")
    fonts    = Fonts()
    renderer = Renderer(surface, fonts)
    touch    = TouchHandler()

    # ── Touch input thread ────────────────────────────────────────────────────
    touch_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()
    _start_touch_thread(touch_queue, stop_event)

    # ── Background metrics thread ─────────────────────────────────────────────
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
    active_tab  = 0
    screensaver = False
    dialog      = None
    clock       = pygame.time.Clock()
    running     = True

    # ── Main loop ─────────────────────────────────────────────────────────────
    while running:
        # pygame events (keyboard on dev machine)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
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
                active_tab, screensaver = _process_gesture(
                    gesture, touch, renderer, active_tab, screensaver, dialog
                )

        # hardware touch events from evdev thread
        while not touch_queue.empty():
            kind, pos = touch_queue.get_nowait()
            if kind == "down":
                touch.on_mouse_down(pos)
            else:
                gesture = touch.on_mouse_up(pos)
                active_tab, screensaver = _process_gesture(
                    gesture, touch, renderer, active_tab, screensaver, dialog
                )

        # ── Screensaver ───────────────────────────────────────────────────────
        if not screensaver and touch.idle_seconds >= config.SCREENSAVER_TIMEOUT:
            screensaver = True

        # ── Render → framebuffer ──────────────────────────────────────────────
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
    fb.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
