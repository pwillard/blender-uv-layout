# ============================================================================ 
# blender-uv-layout.py
# Generates UV map guides for a rectangular shape with real-world units.
# Outputs:
#   - uv-layout.png (transparent PNG with guides)
#   - uv_meta.json  (pixels + normalized UVs)
#
# Requirements: Pillow (pip install pillow)
# Author: Pete Willard
# Version: 0.1
# License: MIT
# Date: 2025-10-29
# Updated:
# ============================================================================ 

from PIL import Image, ImageDraw, ImageFont
import json, math

# ----------------------
# Configuration
# ----------------------

# Real-world box dimensions (meters)
L = 12.2    # length
W = 3.048   # width
H = 3.1     # height

# Canvas (pixels)
CANVAS_W, CANVAS_H = 2048, 2048

# Layout spacing (pixels)
MARGIN_PX   = 60    # outer margin
COL_GAP_PX  = 40    # gap between columns
ROW_GAP_PX  = 40    # gap between rows

# Guide styling (millimeters, converted to pixels by scale)
SAFE_INSET_MM  = 50.0   # dashed "safe" inset from cut
TICK_LEN_MM    = 30.0
TICK_THICK_MM  = 6.0
CUT_THICK_MM   = 8.0
DASH_LEN_MM    = 25.0
GAP_LEN_MM     = 15.0

# Colors (RGBA)
BG     = (0, 0, 0, 0)             # transparent
FG     = (255, 255, 255, 255)     # main outline
ACCENT = (180, 180, 180, 255)     # labels and dashed

# Output paths
PNG_PATH  = "uv-layout.png"
JSON_PATH = "uv_meta.json"

# ----------------------
# Faces and layout grid
# ----------------------
# Faces defined as (name, width_m, height_m).
# Layout (rows x cols = 3 x 2):
# Row 0: [SIDE A][END A]    -> END A butts to SIDE A right edge
# Row 1: [TOP][BOTTOM]      -> both centered in their cells
# Row 2: [SIDE B][END B]    -> END B butts to SIDE B right edge

faces = [
    ("SIDE A",   L, H),
    ("END A",    W, H),
    ("TOP",      L, W),
    ("BOTTOM",   L, W),
    ("SIDE B",   L, H),
    ("END B",    W, H),
]

grid = [
    [faces[0], faces[1]],
    [faces[2], faces[3]],
    [faces[4], faces[5]],
]

# ----------------------
# Helpers
# ----------------------

def dashed_line(draw, p1, p2, dash_len, gap_len, fill, width):
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 0:
        return
    ux, uy = dx / length, dy / length
    dist = 0.0
    while dist < length:
        seg = min(dash_len, length - dist)
        xs = x1 + ux * dist
        ys = y1 + uy * dist
        xe = x1 + ux * (dist + seg)
        ye = y1 + uy * (dist + seg)
        draw.line([(xs, ys), (xe, ye)], fill=fill, width=width)
        dist += dash_len + gap_len

def dashed_rect(draw, rect, dash_len, gap_len, fill, width):
    x0, y0, x1, y1 = rect
    dashed_line(draw, (x0, y0), (x1, y0), dash_len, gap_len, fill, width)  # top
    dashed_line(draw, (x1, y0), (x1, y1), dash_len, gap_len, fill, width)  # right
    dashed_line(draw, (x1, y1), (x0, y1), dash_len, gap_len, fill, width)  # bottom
    dashed_line(draw, (x0, y1), (x0, y0), dash_len, gap_len, fill, width)  # left

def corner_ticks(draw, rect, tick_len, width, fill):
    x0, y0, x1, y1 = rect
    # top-left
    draw.line([(x0, y0), (x0 + tick_len, y0)], fill=fill, width=width)
    draw.line([(x0, y0), (x0, y0 + tick_len)], fill=fill, width=width)
    # top-right
    draw.line([(x1, y0), (x1 - tick_len, y0)], fill=fill, width=width)
    draw.line([(x1, y0), (x1, y0 + tick_len)], fill=fill, width=width)
    # bottom-right
    draw.line([(x1, y1), (x1 - tick_len, y1)], fill=fill, width=width)
    draw.line([(x1, y1), (x1, y1 - tick_len)], fill=fill, width=width)
    # bottom-left
    draw.line([(x0, y1), (x0 + tick_len, y1)], fill=fill, width=width)
    draw.line([(x0, y1), (x0, y1 - tick_len)], fill=fill, width=width)

def rect_to_uv(rect, canvas_w, canvas_h):
    x0, y0, x1, y1 = rect
    return {
        "px": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
        "uv": {
            "u0": x0 / canvas_w, "v0": y0 / canvas_h,
            "u1": x1 / canvas_w, "v1": y1 / canvas_h,
        }
    }

# ----------------------
# Compute layout scale
# ----------------------

# Column and row maxima (meters)
cols_m = [0.0, 0.0]
rows_m = [0.0, 0.0, 0.0]
for r in range(3):
    for c in range(2):
        _, wm, hm = grid[r][c]
        cols_m[c] = max(cols_m[c], wm)
        rows_m[r] = max(rows_m[r], hm)

sum_cols_m = sum(cols_m)
sum_rows_m = sum(rows_m)

# Available pixel area for faces (excluding margins and gaps)
avail_w_px = CANVAS_W - 2 * MARGIN_PX - (2 - 1) * COL_GAP_PX
avail_h_px = CANVAS_H - 2 * MARGIN_PX - (3 - 1) * ROW_GAP_PX

# Scale (pixels per meter), uniform to preserve proportions
s_w = avail_w_px / sum_cols_m
s_h = avail_h_px / sum_rows_m
s = min(s_w, s_h)

def mm_to_px(mm):
    return max(1, int(round((mm / 1000.0) * s)))

# Precompute pixel column/row sizes for grid cells
cols_px = [int(round(wm * s)) for wm in cols_m]
rows_px = [int(round(hm * s)) for hm in rows_m]

# Grid origin in canvas
grid_w_px = sum(cols_px) + COL_GAP_PX
grid_h_px = sum(rows_px) + (len(rows_px) - 1) * ROW_GAP_PX
grid_x0 = (CANVAS_W - grid_w_px) // 2
grid_y0 = (CANVAS_H - grid_h_px) // 2

# Stroke widths and spacings in pixels
CUT_W    = mm_to_px(CUT_THICK_MM)
TICK_W   = mm_to_px(TICK_THICK_MM)
TICK_LEN = mm_to_px(TICK_LEN_MM)
SAFE_INSET = mm_to_px(SAFE_INSET_MM)
DASH_LEN = mm_to_px(DASH_LEN_MM)
GAP_LEN  = mm_to_px(GAP_LEN_MM)

# ----------------------
# Render
# ----------------------
img = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG)
draw = ImageDraw.Draw(img)
font = ImageFont.load_default()

metadata = {
    "canvas_px": [CANVAS_W, CANVAS_H],
    "scale_px_per_meter": s,
    "faces": [],
}

y = grid_y0
for r in range(3):
    x_left = grid_x0
    cell_w_left  = cols_px[0]
    cell_w_right = cols_px[1]
    cell_h       = rows_px[r]

    # LEFT column face (SIDE or TOP)
    name0, wm0, hm0 = grid[r][0]
    fw0, fh0 = int(round(wm0 * s)), int(round(hm0 * s))
    fx0_0 = x_left + (cell_w_left - fw0) // 2
    fy0_0 = y + (cell_h - fh0) // 2
    fx1_0, fy1_0 = fx0_0 + fw0, fy0_0 + fh0

    # RIGHT column face (END or BOTTOM)
    x_right = x_left + cell_w_left + COL_GAP_PX
    name1, wm1, hm1 = grid[r][1]
    fw1, fh1 = int(round(wm1 * s)), int(round(hm1 * s))
    if name1.startswith("END") and name0.startswith("SIDE"):
        # Butt END's left edge to SIDE's right edge
        fx0_1 = fx1_0
    else:
        # Center in right cell
        fx0_1 = x_right + (cell_w_right - fw1) // 2
    fy0_1 = y + (cell_h - fh1) // 2
    fx1_1, fy1_1 = fx0_1 + fw1, fy0_1 + fh1

    # Solid cut outlines
    draw.rectangle([fx0_0, fy0_0, fx1_0, fy1_0], outline=FG, width=CUT_W)
    draw.rectangle([fx0_1, fy0_1, fx1_1, fy1_1], outline=FG, width=CUT_W)

    # Dashed safe areas (inset)
    safe0 = (fx0_0 + SAFE_INSET, fy0_0 + SAFE_INSET, fx1_0 - SAFE_INSET, fy1_0 - SAFE_INSET)
    safe1 = (fx0_1 + SAFE_INSET, fy0_1 + SAFE_INSET, fx1_1 - SAFE_INSET, fy1_1 - SAFE_INSET)
    dashed_rect(draw, safe0, DASH_LEN, GAP_LEN, ACCENT, max(1, CUT_W // 2))
    dashed_rect(draw, safe1, DASH_LEN, GAP_LEN, ACCENT, max(1, CUT_W // 2))

    # Corner ticks
    corner_ticks(draw, (fx0_0, fy0_0, fx1_0, fy1_0), TICK_LEN, TICK_W, FG)
    corner_ticks(draw, (fx0_1, fy0_1, fx1_1, fy1_1), TICK_LEN, TICK_W, FG)

    # Labels
    label0 = f"{name0} ({wm0:g}m x {hm0:g}m)"
    label1 = f"{name1} ({wm1:g}m x {hm1:g}m)"
    draw.text((fx0_0 + SAFE_INSET, fy0_0 + SAFE_INSET - 14), label0, fill=ACCENT, font=font)
    draw.text((fx0_1 + SAFE_INSET, fy0_1 + SAFE_INSET - 14), label1, fill=ACCENT, font=font)

    # Seam ID where END meets SIDE (rows 0 and 2)
    if name1.startswith("END") and name0.startswith("SIDE"):
        seam_mid_y = (max(fy0_0, fy0_1) + min(fy1_0, fy1_1)) // 2
        seam_x = fx1_0
        draw.text((seam_x + 6, seam_mid_y - 6), "SEAM S->E", fill=FG, font=font)

    # Metadata capture
    metadata["faces"].append({
        "name": name0,
        "meters": {"w": wm0, "h": hm0},
        "cut_rect":  rect_to_uv((fx0_0, fy0_0, fx1_0, fy1_0), CANVAS_W, CANVAS_H),
        "safe_rect": rect_to_uv(safe0, CANVAS_W, CANVAS_H),
    })
    metadata["faces"].append({
        "name": name1,
        "meters": {"w": wm1, "h": hm1},
        "cut_rect":  rect_to_uv((fx0_1, fy0_1, fx1_1, fy1_1), CANVAS_W, CANVAS_H),
        "safe_rect": rect_to_uv(safe1, CANVAS_W, CANVAS_H),
        "butted_to_side_right_edge": bool(name1.startswith("END") and name0.startswith("SIDE")),
    })

    y += cell_h + ROW_GAP_PX

# Optional title
draw.text((grid_x0, grid_y0 - 24), "UV Map Guides (cuts, safe area, ticks, seam IDs)", fill=FG, font=font)
draw.text((grid_x0, grid_y0 - 10), f"L={L}m, W={W}m, H={H}m | SAFE_INSET={SAFE_INSET_MM}mm", fill=ACCENT, font=font)

# Save outputs
img.save(PNG_PATH, "PNG")
with open(JSON_PATH, "w") as f:
    json.dump(metadata, f, indent=2)

print("Wrote:", PNG_PATH)
print("Wrote:", JSON_PATH)
