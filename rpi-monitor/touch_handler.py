import time
from typing import Optional, Tuple


class TouchHandler:
    SWIPE_MIN_PX   = 50    # horizontal pixels to count as a swipe
    DEBOUNCE_MS    = 200   # ignore taps faster than this
    LONG_PRESS_SEC = 1.5

    def __init__(self):
        self._down_pos:       Optional[Tuple[int, int]] = None
        self._down_time:      float = 0.0
        self._last_tap_time:  float = 0.0
        self._last_activity:  float = time.time()

    # ── Public ────────────────────────────────────────────────────────────────

    @property
    def idle_seconds(self) -> float:
        return time.time() - self._last_activity

    def record_activity(self):
        self._last_activity = time.time()

    def on_mouse_down(self, pos: Tuple[int, int]):
        self._down_pos  = pos
        self._down_time = time.time()
        self.record_activity()

    def on_mouse_up(self, pos: Tuple[int, int]) -> dict:
        """Return a gesture dict: {type, pos, dx, dy}.

        type is one of: "tap", "swipe", "long_press", or None.
        """
        result = {"type": None, "pos": pos, "dx": 0, "dy": 0}
        if self._down_pos is None:
            return result

        now      = time.time()
        dx       = pos[0] - self._down_pos[0]
        dy       = pos[1] - self._down_pos[1]
        duration = now - self._down_time

        result["dx"] = dx
        result["dy"] = dy

        if abs(dx) >= self.SWIPE_MIN_PX and abs(dx) > abs(dy):
            result["type"] = "swipe"
        elif duration >= self.LONG_PRESS_SEC:
            result["type"] = "long_press"
            result["pos"]  = self._down_pos
        elif (now - self._last_tap_time) * 1000 >= self.DEBOUNCE_MS:
            result["type"]       = "tap"
            self._last_tap_time  = now

        self._down_pos = None
        return result
