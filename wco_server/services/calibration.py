import json
import statistics
from pathlib import Path
from typing import Optional

from services.metrics import darkening_score, laplacian_variance, michelson_contrast

CALIBRATION_FILE = Path("data/calibration_thresholds.json")
STAGING_DIR      = Path("data/calibration_staging")


# ─── Staging (one-image-at-a-time flow from ESP32) ───────────────────────────

def ensure_staging() -> None:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)


def clear_staging() -> None:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    for f in STAGING_DIR.glob("*.jpg"):
        f.unlink()


def stage_image(image_bytes: bytes, filename: str) -> int:
    """Save one image into the staging dir. Returns total staged count."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    (STAGING_DIR / filename).write_bytes(image_bytes)
    return staged_count()


def staged_count() -> int:
    if not STAGING_DIR.exists():
        return 0
    return len(list(STAGING_DIR.glob("*.jpg")))


def staged_images() -> list[bytes]:
    """Return bytes of all staged images sorted by filename."""
    if not STAGING_DIR.exists():
        return []
    return [f.read_bytes() for f in sorted(STAGING_DIR.glob("*.jpg"))]


def is_calibrated() -> bool:
    return CALIBRATION_FILE.exists()


def load_thresholds() -> Optional[dict]:
    if not CALIBRATION_FILE.exists():
        return None
    with open(CALIBRATION_FILE) as f:
        return json.load(f)


def save_thresholds(thresholds: dict) -> None:
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(thresholds, f, indent=2)


def compute_thresholds(image_bytes_list: list[bytes]) -> dict:
    contrasts, laplacians, darkenings = [], [], []

    for img_bytes in image_bytes_list:
        contrasts.append(michelson_contrast(img_bytes))
        laplacians.append(laplacian_variance(img_bytes))
        darkenings.append(darkening_score(img_bytes))

    def _mean_std(values: list[float]) -> tuple[float, float]:
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        return mean, std

    c_mean, c_std = _mean_std(contrasts)
    l_mean, l_std = _mean_std(laplacians)
    d_mean, d_std = _mean_std(darkenings)

    return {
        "turbidity_contrast_threshold": c_mean - 2 * c_std,
        "particle_laplacian_threshold": l_mean + 2 * l_std,
        "color_darkening_threshold":    d_mean + 2 * d_std,
        "calibration_stats": {
            "n_images":       len(image_bytes_list),
            "contrast_mean":  c_mean,
            "contrast_std":   c_std,
            "laplacian_mean": l_mean,
            "laplacian_std":  l_std,
            "darkening_mean": d_mean,
            "darkening_std":  d_std,
        },
    }


def apply_labels(image_bytes: bytes, thresholds: dict) -> dict:
    contrast  = michelson_contrast(image_bytes)
    laplacian = laplacian_variance(image_bytes)
    darkening = darkening_score(image_bytes)

    t_thresh = thresholds["turbidity_contrast_threshold"]
    p_thresh = thresholds["particle_laplacian_threshold"]
    c_thresh = thresholds["color_darkening_threshold"]

    t = 1 if contrast  < t_thresh else 0
    p = 1 if laplacian > p_thresh else 0
    c = 1 if darkening > c_thresh else 0

    # Normalised degradation (0 = clean side, 1 = far past threshold), clamped [0, 1]
    t_norm = min(1.0, max(0.0, (t_thresh - contrast)  / (abs(t_thresh) + 1e-6)))
    p_norm = min(1.0, max(0.0, (laplacian - p_thresh) / (abs(p_thresh) + 1e-6)))
    c_norm = min(1.0, max(0.0, (darkening - c_thresh) / (abs(c_thresh) + 1e-6)))

    quality = min(1.0, max(0.0, 0.4 * t_norm + 0.4 * c_norm + 0.2 * p_norm))

    return {
        "t": t,
        "p": p,
        "c": c,
        "scores": {
            "contrast":  round(contrast,  6),
            "laplacian": round(laplacian, 6),
            "darkening": round(darkening, 6),
            "quality":   round(quality,   6),
        },
    }
