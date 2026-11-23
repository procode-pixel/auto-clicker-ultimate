"""Screen capture. A grab happens only while a recognition step is running."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class ScreenSource(Protocol):
    def grab(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray: ...


class ArrayScreen:
    """Fixed frame for tests and for previews of a captured sample."""

    def __init__(self, image: np.ndarray):
        self.image = np.asarray(image)

    def grab(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray:
        if region is None:
            return self.image.copy()
        x, y, w, h = region
        return self.image[int(y) : int(y) + int(h), int(x) : int(x) + int(w)].copy()


class MssScreen:
    def grab(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray:
        import mss

        with mss.mss() as sct:
            if region is None:
                monitor = sct.monitors[1]
                box = {
                    "left": monitor["left"],
                    "top": monitor["top"],
                    "width": monitor["width"],
                    "height": monitor["height"],
                }
            else:
                x, y, w, h = region
                box = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
            frame = np.array(sct.grab(box))
        return frame[:, :, 2::-1].copy()  # BGRA -> RGB


def create_screen() -> ScreenSource:
    try:
        return MssScreen()
    except Exception:
        return ArrayScreen(np.zeros((32, 32, 3), dtype=np.uint8))
