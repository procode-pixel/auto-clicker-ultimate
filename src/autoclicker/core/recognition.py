"""Pixel and template matching. Capture stays behind a screen source so tests need no display."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - opencv is a required dependency
    cv2 = None


@dataclass
class Match:
    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


def pixel_matches(image: np.ndarray, x: int, y: int, color: tuple[int, int, int], tolerance: int) -> bool:
    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("Image must be RGB")
    height, width = image.shape[:2]
    if not 0 <= x < width or not 0 <= y < height:
        return False
    if not 0 <= tolerance <= 255:
        raise ValueError("Tolerance must be between 0 and 255")
    pixel = image[y, x, :3].astype(int)
    target = np.array(color, dtype=int)
    return bool(np.all(np.abs(pixel - target) <= tolerance))


def find_template(
    haystack: np.ndarray,
    needle: np.ndarray,
    confidence: float,
    offset: tuple[int, int] = (0, 0),
) -> Match | None:
    if not 0.1 <= float(confidence) <= 0.99:
        raise ValueError("Confidence must be between 0.10 and 0.99")
    if haystack.ndim != 3 or needle.ndim != 3:
        raise ValueError("Images must be RGB")
    scene = haystack[:, :, :3]
    probe = needle[:, :, :3]
    if probe.shape[0] > scene.shape[0] or probe.shape[1] > scene.shape[1]:
        return None
    if float(probe.std()) < 2.0:
        return None
    if cv2 is None:
        score, origin = _sad_match(scene, probe)
    else:
        result = cv2.matchTemplate(scene, probe, cv2.TM_CCOEFF_NORMED)
        _, score, _, origin = cv2.minMaxLoc(result)
    if float(score) < float(confidence):
        return None
    return Match(
        x=int(origin[0]) + int(offset[0]),
        y=int(origin[1]) + int(offset[1]),
        width=int(probe.shape[1]),
        height=int(probe.shape[0]),
        confidence=float(score),
    )


def _sad_match(scene: np.ndarray, probe: np.ndarray) -> tuple[float, tuple[int, int]]:
    """Fallback normalized match used only if OpenCV is missing."""
    sh, sw = scene.shape[:2]
    ph, pw = probe.shape[:2]
    best = -1.0
    origin = (0, 0)
    probe_f = probe.astype(np.float32)
    step = max(1, min(4, ph // 8 or 1))
    for y in range(0, sh - ph + 1, step):
        for x in range(0, sw - pw + 1, step):
            window = scene[y : y + ph, x : x + pw].astype(np.float32)
            mad = np.mean(np.abs(window - probe_f)) / 255.0
            score = 1.0 - mad
            if score > best:
                best = score
                origin = (x, y)
    return best, origin


def crop(image: np.ndarray, region: tuple[int, int, int, int]) -> tuple[np.ndarray, tuple[int, int]]:
    x, y, w, h = region
    if w <= 0 or h <= 0:
        raise ValueError("Region must have a positive size")
    height, width = image.shape[:2]
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(width, x0 + int(w))
    y1 = min(height, y0 + int(h))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Region is outside the image")
    return image[y0:y1, x0:x1], (x0, y0)
