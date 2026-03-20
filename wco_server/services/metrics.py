import cv2
import numpy as np

# ── ROI Constants (96x96 coordinate space) ────────────────────────────────────
#
# Derived from physical image analysis of the WCO container setup.
#
# Container circle (Laplacian + HSV clean oil zone):
#   centre (49, 52), safe inner radius 34 px
#
# Reference line zone (Michelson contrast / turbidity):
#   rows 40–72, cols 33–62  — 4 horizontal black lines live here
#
# Laplacian and HSV use the circular container mask with the
# reference line rows excluded, so the reference pattern does not
# corrupt particle or colour metrics.

_CIRCLE_CX  = 49
_CIRCLE_CY  = 52
_CIRCLE_R   = 34

_LINE_ROW_START = 40
_LINE_ROW_END   = 72
_LINE_COL_START = 33
_LINE_COL_END   = 62


def _decode_resize(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")
    return cv2.resize(img, (96, 96))


def _oil_mask() -> np.ndarray:
    """
    Circular mask covering the container interior,
    with the reference line rows zeroed out.
    Used by laplacian_variance and darkening_score.
    """
    mask = np.zeros((96, 96), dtype=np.uint8)
    cv2.circle(mask, (_CIRCLE_CX, _CIRCLE_CY), _CIRCLE_R, 255, -1)
    mask[_LINE_ROW_START:_LINE_ROW_END, :] = 0
    return mask


def michelson_contrast(image_bytes: bytes) -> float:
    """
    Turbidity metric — measures visibility of the reference line pattern.
    High contrast  → lines clearly visible → oil is clear.
    Low contrast   → lines obscured        → oil is turbid.
    ROI: reference line zone only (rows 40–72, cols 33–62).
    """
    img = _decode_resize(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi = gray[_LINE_ROW_START:_LINE_ROW_END, _LINE_COL_START:_LINE_COL_END]
    i_max = float(roi.max())
    i_min = float(roi.min())
    return (i_max - i_min) / (i_max + i_min + 1e-6)


def laplacian_variance(image_bytes: bytes) -> float:
    """
    Particle metric — measures high-frequency edge content in clean oil zone.
    High variance → sharp edges from particles present.
    Low variance  → smooth, particle-free oil.
    ROI: circular container mask, reference line rows excluded.
    """
    img = _decode_resize(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = _oil_mask()
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    oil_pixels = lap[mask > 0]
    return float(oil_pixels.var())


def darkening_score(image_bytes: bytes) -> float:
    """
    Colour degradation metric — low V (dark) + high S (saturated) = degraded oil.
    Score near 0 → fresh, light oil.
    Score near 1 → dark, heavily degraded oil.
    ROI: circular container mask, reference line rows excluded.
    """
    img = _decode_resize(image_bytes)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = _oil_mask()
    v_pixels = hsv[:, :, 2][mask > 0].astype(float) / 255.0
    s_pixels = hsv[:, :, 1][mask > 0].astype(float) / 255.0
    mean_v = float(v_pixels.mean())
    mean_s = float(s_pixels.mean())
    return (1.0 - mean_v) * 0.7 + mean_s * 0.3