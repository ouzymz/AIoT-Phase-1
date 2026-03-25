"""
roi.py
------
Resimdeki kırmızı noktayı bulur, oradan 310px sola giderek
çemberin merkezini hesaplar. Çember ve ROI çizgilerini çizer.

Sabitler:
    CIRCLE_R       = 280 px  (çember yarı çapı)
    RED_OFFSET     = 310 px  (kırmızı nokta -> merkez mesafesi)
    LINE_ROW_HALF  = 280 px  (merkez y'den yukarı/aşağı)
    LINE_COL_HALF  =  95 px  (merkez x'ten sağ/sol)

Kullanım:
    python roi.py resim.jpg
    python roi.py resim.jpg --output sonuc.jpg --show
"""

import cv2
import numpy as np
import argparse
import sys

# --- Sabitler ---
CIRCLE_R      = 250
RED_OFFSET    = 310   # kırmızı noktadan sola kaç px
LINE_ROW_HALF = 100   # yukarı / aşağı
LINE_COL_HALF = 100    # sağ / sol


def find_red_dot(img_bgr):
    """Resimdeki kırmızı noktanın merkez koordinatını döner."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    r = img_rgb[:, :, 0].astype(int)
    g = img_rgb[:, :, 1].astype(int)
    b = img_rgb[:, :, 2].astype(int)

    mask = (r > 150) & (g < 80) & (b < 80)
    coords = np.where(mask)

    if len(coords[0]) == 0:
        return None, None

    red_y = int(coords[0].mean())
    red_x = int(coords[1].mean())
    return red_x, red_y


def compute_roi(red_x, red_y):
    """Kırmızı noktadan ROI parametrelerini hesaplar."""
    cx = red_x - RED_OFFSET
    cy = red_y

    params = {
        "CIRCLE_CX":       cx,
        "CIRCLE_CY":       cy,
        "CIRCLE_R":        CIRCLE_R,
        "LINE_ROW_START":  cy - LINE_ROW_HALF,
        "LINE_ROW_END":    cy + LINE_ROW_HALF,
        "LINE_COL_START":  cx - LINE_COL_HALF,
        "LINE_COL_END":    cx + LINE_COL_HALF,
    }
    return params


def visualize(img_bgr, red_x, red_y, params, output_path=None):
    vis = img_bgr.copy()
    cx = params["CIRCLE_CX"]
    cy = params["CIRCLE_CY"]

    # Çember - mavi
    cv2.circle(vis, (cx, cy), CIRCLE_R, (255, 100, 0), 2)

    # Merkez nokta - mavi
    cv2.circle(vis, (cx, cy), 5, (255, 100, 0), -1)

    # Dikey çizgi (col sabit, row değişiyor)
    cv2.line(vis,
             (params["LINE_COL_START"], cy),
             (params["LINE_COL_END"],   cy),
             (0, 255, 0), 2)

    # Yatay çizgi (row sabit, col değişiyor)
    cv2.line(vis,
             (cx, params["LINE_ROW_START"]),
             (cx, params["LINE_ROW_END"]),
             (0, 255, 0), 2)

    # Kırmızı nokta
    cv2.circle(vis, (red_x, red_y), 6, (0, 0, 255), -1)
    cv2.circle(vis, (red_x, red_y), 10, (0, 0, 255), 2)

    # Kırmızı noktadan merkeze yatay çizgi (referans)
    cv2.line(vis, (cx, cy), (red_x, red_y), (0, 0, 255), 1)

    # Etiketler
    cv2.putText(vis, f"Merkez ({cx},{cy})",
                (cx + 8, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 2)
    cv2.putText(vis, f"Kirmizi ({red_x},{red_y})",
                (red_x + 8, red_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    if output_path:
        cv2.imwrite(output_path, vis)
        print(f"Kaydedildi: {output_path}")

    return vis


def main():
    parser = argparse.ArgumentParser(description="Kirmizi noktadan ROI hesapla")
    parser.add_argument("image", help="Giris resmi")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f"HATA: Resim yuklenemedi -> {args.image}")
        sys.exit(1)

    h, w = img.shape[:2]
    print(f"Resim: {args.image}  ({w}x{h})")

    # Kırmızı nokta bul
    red_x, red_y = find_red_dot(img)
    if red_x is None:
        print("HATA: Kirmizi nokta bulunamadi!")
        sys.exit(1)
    print(f"Kirmizi nokta  : x={red_x}, y={red_y}")

    # ROI hesapla
    p = compute_roi(red_x, red_y)

    print(f"\n_CIRCLE_CX      = {p['CIRCLE_CX']}")
    print(f"_CIRCLE_CY      = {p['CIRCLE_CY']}")
    print(f"_CIRCLE_R       = {p['CIRCLE_R']}")
    print(f"_LINE_ROW_START = {p['LINE_ROW_START']}")
    print(f"_LINE_ROW_END   = {p['LINE_ROW_END']}")
    print(f"_LINE_COL_START = {p['LINE_COL_START']}")
    print(f"_LINE_COL_END   = {p['LINE_COL_END']}")

    # Çıktı yolu
    out_path = args.output
    if out_path is None:
        base = args.image.rsplit(".", 1)[0]
        out_path = base + "_roi.jpg"

    vis = visualize(img, red_x, red_y, p, output_path=out_path)

    if args.show:
        cv2.imshow("ROI", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return p


if __name__ == "__main__":
    main()