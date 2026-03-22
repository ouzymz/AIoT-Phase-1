import cv2
import numpy as np

# ── ROI Constants (800x600 coordinate space) ──────────────────────────────────
#
# Derived from physical image analysis of the WCO container setup.
#
# Container circle (Laplacian + HSV clean oil zone):
#   centre (400, 288), safe inner radius 248 px
#
# Reference grid zone (turbidity / FFT frequency power):
#   rows 186-382, cols 297-493  — 3x3 black grid lives here
#
# Laplacian and HSV use the circular container mask with the
# reference grid rows excluded, so the grid pattern does not
# corrupt particle or colour metrics.

_IMG_W = 800
_IMG_H = 600

_CIRCLE_CX  = 400
_CIRCLE_CY  = 288
_CIRCLE_R   = 248

_LINE_ROW_START = 186
_LINE_ROW_END   = 382
_LINE_COL_START = 297
_LINE_COL_END   = 493


def _decode(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")
    # Ensure consistent 800x600 — handles any resolution from ESP32
    if img.shape[1] != _IMG_W or img.shape[0] != _IMG_H:
        img = cv2.resize(img, (_IMG_W, _IMG_H))
    return img


def _oil_mask() -> np.ndarray:
    """
    Circular mask covering the container interior,
    with the reference grid rows zeroed out.
    Used by laplacian_variance and darkening_score.
    """
    mask = np.zeros((_IMG_H, _IMG_W), dtype=np.uint8)
    cv2.circle(mask, (_CIRCLE_CX, _CIRCLE_CY), _CIRCLE_R, 255, -1)
    mask[_LINE_ROW_START:_LINE_ROW_END, :] = 0
    return mask


def michelson_contrast(image_bytes: bytes) -> float:
    """
    Turbidity metric — measures visibility of the reference grid pattern
    using normalised FFT-based frequency power analysis.

    High power -> grid clearly visible -> oil is clear.
    Low power  -> grid blurred/obscured -> oil is turbid.

    ROI: reference grid zone only (rows 186-382, cols 297-493).
    """
    img = _decode(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(float)
    roi = gray[_LINE_ROW_START:_LINE_ROW_END, _LINE_COL_START:_LINE_COL_END]

    roi_norm = (roi - roi.mean()) / (roi.std() + 1e-6)

    fft = np.fft.fft2(roi_norm)
    fft_shift = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shift)

    center_r = magnitude.shape[0] // 2
    band = magnitude[center_r - 2:center_r + 2, :]
    return float(band.mean())


def laplacian_variance(image_bytes: bytes) -> float:
    """
    Particle metric — measures high-frequency edge content in clean oil zone.
    High variance -> sharp edges from particles present.
    Low variance  -> smooth, particle-free oil.
    ROI: circular container mask, reference grid rows excluded.
    """
    img = _decode(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = _oil_mask()
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    oil_pixels = lap[mask > 0]
    return float(oil_pixels.var())


def darkening_score(image_bytes: bytes) -> float:
    """
    Colour degradation metric — low V (dark) + high S (saturated) = degraded oil.
    Score near 0 -> fresh, light oil.
    Score near 1 -> dark, heavily degraded oil.
    ROI: circular container mask, reference grid rows excluded.
    """
    img = _decode(image_bytes)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = _oil_mask()
    v_pixels = hsv[:, :, 2][mask > 0].astype(float) / 255.0
    s_pixels = hsv[:, :, 1][mask > 0].astype(float) / 255.0
    mean_v = float(v_pixels.mean())
    mean_s = float(s_pixels.mean())
    return (1.0 - mean_v) * 0.7 + mean_s * 0.3