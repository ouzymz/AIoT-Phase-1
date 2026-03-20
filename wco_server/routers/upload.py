from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile

from services.calibration import apply_labels, is_calibrated, load_thresholds
from services.storage import append_log, read_stats, resolve_path

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    Accept any JPEG. If calibrated, auto-label and name the file;
    otherwise save as raw_{timestamp}.jpg with empty labels.
    """
    content = await file.read()
    calibrated = is_calibrated()

    if calibrated:
        thresholds = load_thresholds()
        label_result = apply_labels(content, thresholds)
        t, p, c = label_result["t"], label_result["p"], label_result["c"]
        scores = label_result["scores"]

        index = read_stats()["total"] + 1
        generated_name = f"t{t}_p{p}_c{c}_{index:04d}.jpg"
        labels = {"t": t, "p": p, "c": c}
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        generated_name = f"raw_{ts}.jpg"
        labels = {"t": "", "p": "", "c": ""}
        scores = None

    dest = resolve_path(generated_name)
    dest.write_bytes(content)
    append_log(dest.name, labels)

    return {
        "filename": dest.name,
        "size_bytes": len(content),
        "calibrated": calibrated,
        "labels": {"t": labels["t"], "p": labels["p"], "c": labels["c"]} if calibrated else None,
        "scores": scores,
    }


@router.get("/stats")
def stats():
    """
    Total image count, per-(t,p,c) combination counts, per-label positives,
    and calibration status.
    """
    data = read_stats()
    data["calibrated"] = is_calibrated()
    return data
