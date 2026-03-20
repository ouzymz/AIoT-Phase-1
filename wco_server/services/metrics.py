import cv2
import numpy as np


def _decode_resize(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")
    return cv2.resize(img, (96, 96))


def michelson_contrast(image_bytes: bytes) -> float:
    img = _decode_resize(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi = gray[64:96, 8:88]
    i_max = float(roi.max())
    i_min = float(roi.min())
    return (i_max - i_min) / (i_max + i_min + 1e-6)


def laplacian_variance(image_bytes: bytes) -> float:
    img = _decode_resize(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def darkening_score(image_bytes: bytes) -> float:
    img = _decode_resize(image_bytes)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mean_v = hsv[:, :, 2].mean() / 255.0
    mean_s = hsv[:, :, 1].mean() / 255.0
    return (1.0 - mean_v) * 0.7 + mean_s * 0.3
