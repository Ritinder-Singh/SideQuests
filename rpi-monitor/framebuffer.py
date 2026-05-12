"""Write a pygame Surface to /dev/fb0 as RGB565."""

import pygame

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False


class Framebuffer:
    def __init__(self, path: str = "/dev/fb0"):
        self.path = path
        self._fb = None
        try:
            self._fb = open(path, "wb")
        except PermissionError:
            raise PermissionError(
                f"Cannot open {path} — run with sudo or add your user to the 'video' group"
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"{path} not found — is the SPI display driver loaded?\n"
                "Check /boot/firmware/config.txt contains:\n"
                "  dtparam=spi=on\n"
                "  dtoverlay=waveshare35a"
            )

    def flush(self, surface: pygame.Surface):
        import config
        if config.DISPLAY_ROTATE:
            surface = pygame.transform.rotate(surface, -config.DISPLAY_ROTATE)
        if _NUMPY:
            self._flush_numpy(surface)
        else:
            self._flush_pure(surface)

    def _flush_numpy(self, surface: pygame.Surface):
        # surfarray gives (W, H, 3) uint8; framebuffer wants row-major (H, W)
        arr = pygame.surfarray.array3d(surface).transpose(1, 0, 2)
        r = arr[:, :, 0].astype(np.uint16)
        g = arr[:, :, 1].astype(np.uint16)
        b = arr[:, :, 2].astype(np.uint16)
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        self._fb.seek(0)
        self._fb.write(rgb565.astype("<u2").tobytes())
        self._fb.flush()

    def _flush_pure(self, surface: pygame.Surface):
        # Fallback: slower pure-Python conversion
        import array as _array
        raw = pygame.image.tostring(surface, "RGB")
        n = len(raw) // 3
        out = _array.array("H", bytes(2 * n))
        for i in range(n):
            r = raw[i * 3]     >> 3
            g = raw[i * 3 + 1] >> 2
            b = raw[i * 3 + 2] >> 3
            out[i] = (r << 11) | (g << 5) | b
        self._fb.seek(0)
        self._fb.write(out.tobytes())
        self._fb.flush()

    def close(self):
        if self._fb and not self._fb.closed:
            self._fb.close()

    def __del__(self):
        self.close()
