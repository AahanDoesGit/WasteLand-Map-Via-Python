#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  HARIDWAR MAP GENERATOR                                     ║
║  Stitches OpenStreetMap tiles into a 2000x2000 map_base.png ║
║  Run this ONCE on a PC (not the Unihiker) then transfer     ║
║  the output map_base.png to your device.                    ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  pip install requests pillow
  python generate_map.py

Output:
  map_base.png  — 2000x2000 greyscale Haridwar map
                  centered on Har Ki Pauri, ~25km radius

Then transfer to Unihiker:
  scp map_base.png root@unihiker.local:/root/
"""

import math
import os
import time
import requests
from PIL import Image, ImageDraw, ImageFilter

# ─────────────────────────────────────────────────────────────
#  MAP CENTER & SCALE
# ─────────────────────────────────────────────────────────────

CENTER_LAT   = 29.9457   # Har Ki Pauri, Haridwar
CENTER_LON   = 78.1642
ZOOM_LEVEL   = 14        # OSM zoom — higher = more detail, more tiles
OUTPUT_SIZE  = 2000      # Final image size in pixels (square)
OUTPUT_FILE  = "map_base.png"

# User-Agent required by OSM tile servers
HEADERS = {"User-Agent": "HaridwarWasteland/1.0 PipBoyMap (educational project)"}

# ─────────────────────────────────────────────────────────────
#  OSM TILE MATH
# ─────────────────────────────────────────────────────────────

TILE_SIZE = 256  # OSM standard tile size

def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to OSM tile numbers at given zoom."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def tile_to_lat_lon(tx: int, ty: int, zoom: int) -> tuple[float, float]:
    """Convert OSM tile numbers back to lat/lon (top-left corner)."""
    n = 2 ** zoom
    lon = tx / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ty / n)))
    lat = math.degrees(lat_rad)
    return lat, lon

def download_tile(tx: int, ty: int, zoom: int, cache_dir: str = ".tile_cache") -> Image.Image | None:
    """Download a single OSM tile, using disk cache to avoid re-downloading."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{zoom}_{tx}_{ty}.png")

    if os.path.exists(cache_path):
        return Image.open(cache_path).convert("RGB")

    url = f"https://tile.openstreetmap.org/{zoom}/{tx}/{ty}.png"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            with open(cache_path, "wb") as f:
                f.write(resp.content)
            time.sleep(0.1)  # Be polite to OSM servers
            return Image.open(cache_path).convert("RGB")
        else:
            print(f"  [WARN] Tile {tx},{ty} returned HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [ERROR] Failed to download tile {tx},{ty}: {e}")
        return None

# ─────────────────────────────────────────────────────────────
#  MAIN MAP BUILDER
# ─────────────────────────────────────────────────────────────

def build_map():
    print("=" * 60)
    print("  HARIDWAR WASTELAND — MAP GENERATOR")
    print("=" * 60)
    print(f"  Center:  {CENTER_LAT}°N, {CENTER_LON}°E")
    print(f"  Zoom:    {ZOOM_LEVEL}")
    print(f"  Output:  {OUTPUT_FILE} ({OUTPUT_SIZE}×{OUTPUT_SIZE}px)")
    print()

    # ── How many tiles do we need? ────────────────────────────
    # We want OUTPUT_SIZE pixels across, each tile is TILE_SIZE px
    tiles_needed = math.ceil(OUTPUT_SIZE / TILE_SIZE) + 2  # +2 for padding
    half_tiles   = tiles_needed // 2

    # Center tile
    cx_tile, cy_tile = lat_lon_to_tile(CENTER_LAT, CENTER_LON, ZOOM_LEVEL)

    tile_x_min = cx_tile - half_tiles
    tile_x_max = cx_tile + half_tiles
    tile_y_min = cy_tile - half_tiles
    tile_y_max = cy_tile + half_tiles

    total_tiles = (tile_x_max - tile_x_min + 1) * (tile_y_max - tile_y_min + 1)
    canvas_w = (tile_x_max - tile_x_min + 1) * TILE_SIZE
    canvas_h = (tile_y_max - tile_y_min + 1) * TILE_SIZE

    print(f"  Downloading {total_tiles} tiles ({tiles_needed}×{tiles_needed} grid)...")
    print(f"  Raw canvas before crop: {canvas_w}×{canvas_h}px")
    print()

    # ── Download and stitch tiles ─────────────────────────────
    canvas = Image.new("RGB", (canvas_w, canvas_h), (20, 18, 15))

    downloaded = 0
    for ty in range(tile_y_min, tile_y_max + 1):
        for tx in range(tile_x_min, tile_x_max + 1):
            tile_img = download_tile(tx, ty, ZOOM_LEVEL)
            if tile_img:
                paste_x = (tx - tile_x_min) * TILE_SIZE
                paste_y = (ty - tile_y_min) * TILE_SIZE
                canvas.paste(tile_img, (paste_x, paste_y))
            downloaded += 1
            print(f"\r  Progress: {downloaded}/{total_tiles} tiles", end="", flush=True)

    print(f"\n\n  All tiles downloaded. Compositing...")

    # ── Find pixel position of center lat/lon on the canvas ──
    # The top-left tile's top-left corner corresponds to tile (tile_x_min, tile_y_min)
    center_tile_offset_x = (cx_tile - tile_x_min) * TILE_SIZE
    center_tile_offset_y = (cy_tile - tile_y_min) * TILE_SIZE

    # Fractional position within the center tile
    center_frac_x = (CENTER_LON + 180.0) / 360.0 * (2 ** ZOOM_LEVEL) - cx_tile
    center_frac_y = (
        (1.0 - math.asinh(math.tan(math.radians(CENTER_LAT))) / math.pi) / 2.0
        * (2 ** ZOOM_LEVEL)
    ) - cy_tile

    canvas_cx = int(center_tile_offset_x + center_frac_x * TILE_SIZE)
    canvas_cy = int(center_tile_offset_y + center_frac_y * TILE_SIZE)

    print(f"  Center point on canvas: ({canvas_cx}, {canvas_cy})")

    # ── Crop to OUTPUT_SIZE centered on Har Ki Pauri ─────────
    half = OUTPUT_SIZE // 2
    crop_x0 = max(0, canvas_cx - half)
    crop_y0 = max(0, canvas_cy - half)
    crop_x1 = crop_x0 + OUTPUT_SIZE
    crop_y1 = crop_y0 + OUTPUT_SIZE

    # Ensure we don't exceed canvas bounds
    if crop_x1 > canvas_w:
        crop_x0 = canvas_w - OUTPUT_SIZE
        crop_x1 = canvas_w
    if crop_y1 > canvas_h:
        crop_y0 = canvas_h - OUTPUT_SIZE
        crop_y1 = canvas_h

    result = canvas.crop((crop_x0, crop_y0, crop_x1, crop_y1))

    # Ensure exactly OUTPUT_SIZE × OUTPUT_SIZE
    if result.size != (OUTPUT_SIZE, OUTPUT_SIZE):
        result = result.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS)

    # ── Apply Pip-Boy stylization ─────────────────────────────
    print("  Applying Pip-Boy filter (desaturate + contrast)...")
    result = _apply_pipboy_filter(result)

    # ── Save ──────────────────────────────────────────────────
    result.save(OUTPUT_FILE, "PNG", optimize=True)
    print(f"\n  ✓ Saved: {OUTPUT_FILE}")
    print(f"  File size: {os.path.getsize(OUTPUT_FILE) / 1024:.0f} KB")

    # ── Print calibration points ──────────────────────────────
    print()
    print("=" * 60)
    print("  CALIBRATION DATA FOR pipboy_map.py")
    print("=" * 60)
    # The center of the cropped image IS Har Ki Pauri
    print(f"  CAL_A: Har Ki Pauri → Pixel ({OUTPUT_SIZE//2}, {OUTPUT_SIZE//2})")
    print(f"         Lat/Lon: {CENTER_LAT}, {CENTER_LON}")
    print()

    # Compute second calibration point (Chandi Devi)
    chandi_lat, chandi_lon = 29.9630, 78.1820
    chandi_tx, chandi_ty = lat_lon_to_tile(chandi_lat, chandi_lon, ZOOM_LEVEL)
    chandi_frac_x = (chandi_lon + 180.0) / 360.0 * (2 ** ZOOM_LEVEL) - chandi_tx
    chandi_frac_y = (
        (1.0 - math.asinh(math.tan(math.radians(chandi_lat))) / math.pi) / 2.0
        * (2 ** ZOOM_LEVEL)
    ) - chandi_ty
    chandi_canvas_x = (chandi_tx - tile_x_min) * TILE_SIZE + int(chandi_frac_x * TILE_SIZE)
    chandi_canvas_y = (chandi_ty - tile_y_min) * TILE_SIZE + int(chandi_frac_y * TILE_SIZE)
    chandi_map_x = chandi_canvas_x - crop_x0
    chandi_map_y = chandi_canvas_y - crop_y0
    print(f"  CAL_B: Chandi Devi → Pixel ({chandi_map_x}, {chandi_map_y})")
    print(f"         Lat/Lon: {chandi_lat}, {chandi_lon}")
    print()
    print("  → Update CAL_A_PX/PY and CAL_B_PX/PY in pipboy_map.py")
    print("    with the values above.")
    print("=" * 60)


def _apply_pipboy_filter(img: Image.Image) -> Image.Image:
    """
    Convert colorful OSM map to dark Pip-Boy aesthetic:
    1. Desaturate (greyscale)
    2. Invert (dark roads on darker background)
    3. Apply slight blur for that slightly-soft CRT look
    4. Increase contrast / darken overall
    """
    from PIL import ImageOps, ImageEnhance

    # Convert to greyscale
    grey = img.convert("L")

    # Enhance contrast — roads should be visible
    grey = ImageEnhance.Contrast(grey).enhance(1.4)
    grey = ImageEnhance.Brightness(grey).enhance(0.6)  # Darken

    # Light blur for CRT softness
    grey = grey.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Back to RGB (app will do amber colorization at runtime)
    return grey.convert("RGB")


if __name__ == "__main__":
    build_map()
