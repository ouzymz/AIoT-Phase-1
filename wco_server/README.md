# wco_server — WCO Quality Data Collection Server

FastAPI server for the TinyML Waste Cooking Oil (WCO) quality assessment project.
Receives JPEG images from an ESP32-CAM, auto-labels them using image metrics, and
logs everything to CSV for model training.

---

## Project structure

```
wco_server/
├── main.py                        # App factory, CORS, startup, /health, /favicon
├── requirements.txt
├── routers/
│   ├── upload.py                  # POST /upload, GET /stats
│   ├── calibration.py             # POST /calibrate, POST /calibrate/image,
│   │                              # GET /calibrate/compute, GET /calibration
│   └── validation.py              # POST /validate, GET /validate/report,
│                                  # DELETE /validate/reset
├── services/
│   ├── metrics.py                 # michelson_contrast, laplacian_variance, darkening_score
│   ├── calibration.py             # threshold I/O, staging, apply_labels
│   ├── storage.py                 # file save, CSV log, path resolution
│   └── validation.py              # validation CSV log, report aggregation
└── data/
    ├── images/                    # saved JPEGs
    ├── calibration_staging/       # temporary per-image upload buffer
    ├── calibration_thresholds.json
    ├── log.csv
    └── validation_log.csv
```

---

## Setup

```bash
cd wco_server
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On startup the server prints its LAN IP and all endpoint URLs.

---

## API endpoints

### Data collection

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Accept one JPEG from ESP32. Auto-label if calibrated, else save as `raw_<ts>.jpg`. |
| `GET`  | `/stats`  | Total count, per-combination counts, per-label positives, calibration status. |

**`POST /upload` response**
```json
{
  "filename": "t0_p0_c1_0007.jpg",
  "size_bytes": 14321,
  "calibrated": true,
  "labels": {"t": 0, "p": 0, "c": 1},
  "scores": {
    "contrast": 0.812,
    "laplacian": 143.5,
    "darkening": 0.341,
    "quality": 0.287
  }
}
```

---

### Calibration

Calibration establishes baseline thresholds from **clean fresh oil** images.
Two flows are supported:

#### ESP32 flow (one image at a time)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/calibrate/image` | Stage one JPEG. Returns `{"staged": N, "filename": "..."}`. |
| `GET`  | `/calibrate/compute` | Compute thresholds from all staged images, persist, clear staging. |

Triggered automatically by `GET http://<ESP32-IP>/calibrate?n=20`.

#### Bulk flow (curl / script)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/calibrate` | Upload 10–50 JPEGs in one multipart request. |

```bash
curl -X POST http://localhost:8000/calibrate \
  -F "files=@clean1.jpg" -F "files=@clean2.jpg" ...
```

#### Status

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/calibration` | `{"calibrated": bool, "staged_pending": N, "thresholds": {...}}` |

---

### Validation

Validates labeling accuracy against known oil samples. Requires calibration first.

#### ESP32 flow

Triggered automatically by `GET http://<ESP32-IP>/validate?group=<group>&n=3`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/validate?group=<g>` | Submit one JPEG with known group. Returns per-label match and scores. |
| `GET`  | `/validate/report` | Aggregated accuracy: overall, per-label (t/p/c), per-group. |
| `DELETE` | `/validate/reset` | Clear `validation_log.csv` and start fresh. |

**Groups and default expectations:**

| group | expected_t | expected_p | expected_c |
|-------|-----------|-----------|-----------|
| `clean` | 0 | 0 | 0 |
| `turbid` | 1 | — | — |
| `turbid_particle` | 1 | 1 | — |

`—` means the label is not evaluated for that group.

**`POST /validate` response**
```json
{
  "group": "turbid",
  "expected": {"t": 1, "p": null, "c": null},
  "actual":   {"t": 1, "p": 0,   "c": 0},
  "scores":   {"contrast": 0.21, "laplacian": 4.1, "darkening": 0.43, "quality": 0.61},
  "match":    {"t": true, "p": null, "c": null},
  "correct":  true
}
```

---

### Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{"status": "ok", "uptime_seconds": float}` |

---

## Image metrics

All metrics operate on images resized to **96×96**. ROIs are derived from the physical container geometry.

| Metric | ROI | Threshold direction |
|--------|-----|-------------------|
| Michelson contrast | Reference line zone: rows 40–72, cols 33–62 | `<` threshold → turbid (t=1) |
| Laplacian variance | Circular container mask (r=34), line rows excluded | `>` threshold → particles (p=1) |
| Darkening score | Circular container mask (r=34), line rows excluded | `>` threshold → color change (c=1) |

Thresholds are set at **mean ± 2σ** of the clean-oil calibration images.

## Filename convention

Labeled images are saved as:

```
t{0|1}_p{0|1}_c{0|1}_{index:04d}.jpg
```

Example: `t1_p0_c1_0042.jpg` → turbid, no particles, color-changed, 42nd image.

Uncalibrated images are saved as `raw_<UTC-timestamp>.jpg` and logged with empty label columns.

---

## Adding Phase 2 routers

```python
# main.py
from routers import labeling
app.include_router(labeling.router, prefix="/label")
```

Create `routers/labeling.py` with an `APIRouter` and register it the same way.
