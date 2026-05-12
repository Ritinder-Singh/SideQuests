from typing import Callable, List, Optional, Tuple

import pygame

import config

Color = Tuple[int, int, int]


# ── Stateless drawing helpers ─────────────────────────────────────────────────

def draw_progress_bar(
    surface: pygame.Surface,
    x: int, y: int, width: int, height: int,
    percent: float,
    bg: Color = config.BORDER_COLOR,
    border: Color = config.BORDER_COLOR,
):
    percent = max(0.0, min(100.0, percent))
    if percent < 60:
        bar_color = config.GREEN
    elif percent < 80:
        bar_color = config.YELLOW
    else:
        bar_color = config.RED

    pygame.draw.rect(surface, bg, (x, y, width, height))
    fill = int(width * percent / 100)
    if fill > 0:
        pygame.draw.rect(surface, bar_color, (x, y, fill, height))
    pygame.draw.rect(surface, border, (x, y, width, height), 1)


def draw_status_dot(
    surface: pygame.Surface,
    cx: int, cy: int,
    color: Color,
    radius: int = 5,
):
    pygame.draw.circle(surface, color, (cx, cy), radius)
    pygame.draw.circle(surface, config.BORDER_COLOR, (cx, cy), radius, 1)


# ── Button ────────────────────────────────────────────────────────────────────

class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        callback: Optional[Callable] = None,
        color: Color = config.TAB_ACTIVE,
        text_color: Color = config.TEXT_COLOR,
        font: Optional[pygame.font.Font] = None,
    ):
        self.rect       = rect
        self.label      = label
        self.callback   = callback
        self.color      = color
        self.text_color = text_color
        self.font       = font
        self._pressed   = False

    def draw(self, surface: pygame.Surface):
        bg = config.BLUE if self._pressed else self.color
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        pygame.draw.rect(surface, config.BORDER_COLOR, self.rect, 1, border_radius=4)
        if self.font:
            text = self.font.render(self.label, True, self.text_color)
            surface.blit(text, text.get_rect(center=self.rect.center))

    def handle_tap(self, pos: Tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self._pressed = True
            if self.callback:
                self.callback()
            return True
        return False

    def release(self):
        self._pressed = False


# ── Tab bar ───────────────────────────────────────────────────────────────────

class TabBar:
    def __init__(self, labels: List[str], font: pygame.font.Font):
        self.labels  = labels
        self.font    = font
        self.active  = 0
        self._rects: List[pygame.Rect] = []
        self._build()

    def _build(self):
        tab_w = config.SCREEN_WIDTH // len(self.labels)
        y     = config.SCREEN_HEIGHT - config.TAB_HEIGHT
        self._rects = [
            pygame.Rect(i * tab_w, y, tab_w, config.TAB_HEIGHT)
            for i in range(len(self.labels))
        ]

    def draw(self, surface: pygame.Surface, badge_counts: Optional[List[int]] = None):
        bar_y = config.SCREEN_HEIGHT - config.TAB_HEIGHT
        pygame.draw.rect(surface, config.TAB_BG,
                         (0, bar_y, config.SCREEN_WIDTH, config.TAB_HEIGHT))
        pygame.draw.line(surface, config.BORDER_COLOR,
                         (0, bar_y), (config.SCREEN_WIDTH, bar_y), 1)

        for i, (rect, label) in enumerate(zip(self._rects, self.labels)):
            if i == self.active:
                pygame.draw.rect(surface, config.TAB_ACTIVE, rect)
                pygame.draw.line(surface, config.BLUE,
                                 (rect.x, bar_y), (rect.right, bar_y), 2)

            fg    = config.TEXT_COLOR if i == self.active else config.DIM_COLOR
            text  = self.font.render(label, True, fg)
            surface.blit(text, text.get_rect(center=rect.center))

            if badge_counts and i < len(badge_counts) and badge_counts[i] > 0:
                badge_surf = self.font.render(str(badge_counts[i]), True, config.BG_COLOR)
                bw = badge_surf.get_width() + 8
                bh = 14
                bx = rect.right - bw - 2
                by = rect.top   + 3
                pygame.draw.rect(surface, config.RED, (bx, by, bw, bh), border_radius=7)
                surface.blit(badge_surf, (bx + 4, by + 1))

    def handle_tap(self, pos: Tuple[int, int]) -> Optional[int]:
        for i, rect in enumerate(self._rects):
            if rect.collidepoint(pos):
                self.active = i
                return i
        return None

    def handle_swipe(self, dx: int) -> Optional[int]:
        if dx > 50 and self.active > 0:
            self.active -= 1
            return self.active
        if dx < -50 and self.active < len(self.labels) - 1:
            self.active += 1
            return self.active
        return None


# ── Confirm dialog ────────────────────────────────────────────────────────────

class ConfirmDialog:
    def __init__(
        self,
        message: str,
        on_confirm: Callable,
        on_cancel: Callable,
        font: pygame.font.Font,
    ):
        self.message    = message
        self.on_confirm = on_confirm
        self.on_cancel  = on_cancel
        self.font       = font

        w, h = 320, 140
        x = (config.SCREEN_WIDTH  - w) // 2
        y = (config.SCREEN_HEIGHT - h) // 2
        self.rect = pygame.Rect(x, y, w, h)

        btn_y = y + h - 52
        self.confirm_btn = Button(
            pygame.Rect(x + 20, btn_y, 120, 40),
            "Confirm", on_confirm, config.RED, font=font,
        )
        self.cancel_btn = Button(
            pygame.Rect(x + w - 140, btn_y, 120, 40),
            "Cancel", on_cancel, font=font,
        )

    def draw(self, surface: pygame.Surface):
        overlay = pygame.Surface(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(surface, config.TAB_BG,      self.rect, border_radius=8)
        pygame.draw.rect(surface, config.BORDER_COLOR, self.rect, 1, border_radius=8)

        for i, line in enumerate(self.message.split("\n")):
            surf = self.font.render(line, True, config.TEXT_COLOR)
            surface.blit(surf, (self.rect.x + 16, self.rect.y + 16 + i * 20))

        self.confirm_btn.draw(surface)
        self.cancel_btn.draw(surface)

    def handle_tap(self, pos: Tuple[int, int]) -> bool:
        return self.confirm_btn.handle_tap(pos) or self.cancel_btn.handle_tap(pos)


# ── Line chart ────────────────────────────────────────────────────────────────

class LineChart:
    def __init__(
        self,
        rect: pygame.Rect,
        min_value: float = 0.0,
        max_value: float = 100.0,
    ):
        self.rect      = rect
        self.min_value = min_value
        self.max_value = max_value
        self.data: List[float] = []

    def add_point(self, value: float):
        self.data.append(value)
        capacity = max(2, self.rect.width // 2)
        if len(self.data) > capacity:
            self.data = self.data[-capacity:]

    def draw(self, surface: pygame.Surface, color: Color = config.GREEN):
        pygame.draw.rect(surface, config.TAB_BG,       self.rect)
        pygame.draw.rect(surface, config.BORDER_COLOR, self.rect, 1)

        if len(self.data) < 2:
            return

        span = self.max_value - self.min_value
        if span == 0:
            return

        n = len(self.data)
        points = []
        for i, val in enumerate(self.data):
            px = self.rect.x + int(i * self.rect.width  / (n - 1))
            norm = (val - self.min_value) / span
            py = self.rect.bottom - int(norm * self.rect.height)
            py = max(self.rect.top, min(self.rect.bottom, py))
            points.append((px, py))

        pygame.draw.lines(surface, color, False, points, 2)
