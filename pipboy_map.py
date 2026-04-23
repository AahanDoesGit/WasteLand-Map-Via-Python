#!/usr/bin/env python3
"""
CONTROLS:
  P3 = Button A (small pad) → Pan UP
  P0 = Button B (big pad)   → Pan RIGHT
  P1 = Button C (big pad)   → Pan DOWN
  P2 = Button D (big pad)   → Pan LEFT

SETUP (run on Unihiker via SSH):
  pip install pillow unihiker pinpong
"""

import time
import math
import os
from PIL import Image, ImageDraw, ImageFont
from unihiker import GUI
from pinpong.board import Board, Pin

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────

COLOR_BG         = (5,   5,   5)
COLOR_AMBER      = (255, 182, 66)
COLOR_AMBER_DIM  = (120, 85,  30)
COLOR_AMBER_GLOW = (255, 210, 120)
COLOR_RED_ALERT  = (255, 60,  60)

MAP_FILE         = "map_base.png"
MAP_SIZE         = 2000
VIEWPORT_W       = 320
VIEWPORT_H       = 240
GRID_CELL        = 20
SCANLINE_STEP    = 3
SCANLINE_ALPHA   = 40

# Starting position on the map (Har Ki Pauri — centre)
START_PX         = 1000
START_PY         = 1000

# How many pixels to move per button press
PAN_SPEED        = 30

# ─────────────────────────────────────────────────────────────
#  POINTS OF INTEREST — Haridwar Wasteland
# ─────────────────────────────────────────────────────────────

# Pixel coordinates on the 2000x2000 map
POIS = {
    "Mansa Devi Hill":    {"px": 792,  "py": 843,  "type": "sniper",   "label": "MANSA DEVI"},
    "Chandi Devi Hill":   {"px": 1208, "py": 767,  "type": "sniper",   "label": "CHANDI DEVI"},
    "Aryavrat Hospital":  {"px": 1058, "py": 1019, "type": "medical",  "label": "ARYAVRAT"},
    "Prem Hospital":      {"px": 1081, "py": 981,  "type": "medical",  "label": "PREM HOSP"},
    "Healic Hospital":    {"px": 1070, "py": 1004, "type": "medical",  "label": "HEALIC"},
    "BHEL Campus":        {"px": 813,  "py": 1322, "type": "power",    "label": "BHEL-HELIOS"},
    "Har Ki Pauri Ghat":  {"px": 1000, "py": 1000, "type": "water",    "label": "HAR KI PAURI"},
    "Pathri Power House": {"px": 1312, "py": 700,  "type": "water",    "label": "PATHRI PWR"},
    "SIDCUL Industrial":  {"px": 562,  "py": 1637, "type": "industry", "label": "SIDCUL RUINS"},
}

# ─────────────────────────────────────────────────────────────
#  POI ICON RENDERERS
# ─────────────────────────────────────────────────────────────

def _icon_sniper(draw, cx, cy, col):
    pts = [(cx, cy - 9), (cx - 7, cy + 6), (cx + 7, cy + 6)]
    draw.polygon(pts, outline=col, fill=None)
    draw.line([(cx, cy - 9), (cx, cy - 14)], fill=col, width=1)

def _icon_medical(draw, cx, cy, col):
    s = 4
    draw.rectangle([cx - s, cy - 1, cx + s, cy + 1], fill=col)
    draw.rectangle([cx - 1, cy - s, cx + 1, cy + s], fill=col)
    draw.rectangle([cx - s - 1, cy - s - 1, cx + s + 1, cy + s + 1], outline=col)

def _icon_power(draw, cx, cy, col):
    pts = [(cx + 2, cy - 9), (cx - 3, cy), (cx + 1, cy),
           (cx - 2, cy + 9), (cx + 3, cy), (cx - 1, cy)]
    draw.polygon(pts, fill=col)

def _icon_water(draw, cx, cy, col):
    draw.ellipse([cx - 4, cy - 1, cx + 4, cy + 7], outline=col)
    draw.polygon([(cx, cy - 8), (cx - 4, cy - 1), (cx + 4, cy - 1)], outline=col)

def _icon_industry(draw, cx, cy, col):
    draw.rectangle([cx - 6, cy - 4, cx + 6, cy + 8], outline=col)
    draw.rectangle([cx - 2, cy + 2, cx + 2, cy + 8], fill=col)
    draw.line([(cx - 4, cy - 4), (cx - 4, cy - 10)], fill=col, width=2)
    draw.line([(cx + 4, cy - 4), (cx + 4, cy - 8)],  fill=col, width=2)

ICON_DRAW = {
    "sniper":   _icon_sniper,
    "medical":  _icon_medical,
    "power":    _icon_power,
    "water":    _icon_water,
    "industry": _icon_industry,
}

# ─────────────────────────────────────────────────────────────
#  RENDERER
# ─────────────────────────────────────────────────────────────

class PipBoyRenderer:
    def __init__(self):
        self._map       = self._load_map()
        self._scanlines = self._build_scanlines()

        try:
            self._font_sm = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 7)
            self._font_md = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9)
            self._font_lg = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 11)
        except (IOError, OSError):
            self._font_sm = ImageFont.load_default()
            self._font_md = ImageFont.load_default()
            self._font_lg = ImageFont.load_default()

        self._pulse_phase = 0.0
        self._tick        = 0

        # Current map view centre (pixel coordinates on 2000x2000 map)
        self.cam_x = START_PX
        self.cam_y = START_PY

    # ── Map loading ───────────────────────────────────────────

    def _load_map(self):
        if os.path.exists(MAP_FILE):
            print(f"[MAP] Loaded {MAP_FILE}")
            img = Image.open(MAP_FILE).convert("RGB")
            if img.size != (MAP_SIZE, MAP_SIZE):
                img = img.resize((MAP_SIZE, MAP_SIZE), Image.LANCZOS)
            # Amber tint: keep red channel, scale G and B
            r, g, b = img.split()
            img = Image.merge("RGB", (r, g, Image.new("L", img.size, 0)))
            return img
        else:
            print("[MAP] map_base.png not found — generating placeholder")
            return self._generate_placeholder_map()

    def _generate_placeholder_map(self):
        img = Image.new("RGB", (MAP_SIZE, MAP_SIZE), COLOR_BG)
        d   = ImageDraw.Draw(img)
        for x in range(0, MAP_SIZE, 100):
            d.line([(x, 0), (x, MAP_SIZE)], fill=(15, 10, 5), width=1)
        for y in range(0, MAP_SIZE, 100):
            d.line([(0, y), (MAP_SIZE, y)], fill=(15, 10, 5), width=1)
        river_pts = []
        for y in range(0, MAP_SIZE, 5):
            wave = int(30 * math.sin(y * 0.015) + 20 * math.sin(y * 0.033))
            river_pts.append((980 + wave, y))
        d.line(river_pts, fill=(30, 60, 50), width=18)
        d.line(river_pts, fill=(20, 40, 35), width=8)
        d.line([(0, 1050), (MAP_SIZE, 980)], fill=(25, 20, 10), width=12)
        for row in range(850, 1150, 25):
            d.line([(870, row), (1150, row)], fill=(18, 15, 8), width=1)
        for col in range(870, 1150, 25):
            d.line([(col, 850), (col, 1150)], fill=(18, 15, 8), width=1)
        return img

    def _build_scanlines(self):
        overlay = Image.new("RGBA", (VIEWPORT_W, VIEWPORT_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for y in range(0, VIEWPORT_H, SCANLINE_STEP):
            d.line([(0, y), (VIEWPORT_W, y)], fill=(0, 0, 0, SCANLINE_ALPHA))
        return overlay

    # ── Landscape rotation ────────────────────────────────────

    @staticmethod
    def _to_landscape(frame):
        """Rotate the 320x240 frame 90° CW so it fills the Unihiker screen."""
        return frame.rotate(-90, expand=True)

    # ── Pan control ───────────────────────────────────────────

    def pan(self, dx, dy):
        """Move the camera by dx/dy pixels, clamped to map bounds."""
        half_w = VIEWPORT_W // 2
        half_h = VIEWPORT_H // 2
        self.cam_x = max(half_w, min(MAP_SIZE - half_w, self.cam_x + dx))
        self.cam_y = max(half_h, min(MAP_SIZE - half_h, self.cam_y + dy))

    # ── Render ────────────────────────────────────────────────

    def render_frame(self):
        self._tick += 1
        self._pulse_phase = (self._pulse_phase + 0.04) % 1.0

        cx = self.cam_x
        cy = self.cam_y

        half_w = VIEWPORT_W // 2
        half_h = VIEWPORT_H // 2
        x0 = cx - half_w
        y0 = cy - half_h

        # Crop viewport from map
        viewport = self._map.crop((x0, y0, x0 + VIEWPORT_W, y0 + VIEWPORT_H))
        frame = viewport.convert("RGBA")

        # Amber colorise
        r_ch, g_ch, b_ch, a_ch = frame.split()
        frame = Image.merge("RGBA", (
            r_ch,
            r_ch.point(lambda v: int(v * 0.71)),
            r_ch.point(lambda v: int(v * 0.26)),
            a_ch
        ))
        draw = ImageDraw.Draw(frame)

        # CRT grid
        grid_col = (*COLOR_AMBER_DIM, 55)
        for gx in range(0, VIEWPORT_W, GRID_CELL):
            draw.line([(gx, 0), (gx, VIEWPORT_H)], fill=grid_col)
        for gy in range(0, VIEWPORT_H, GRID_CELL):
            draw.line([(0, gy), (VIEWPORT_W, gy)], fill=grid_col)

        # POI icons
        for name, data in POIS.items():
            sx = data["px"] - x0
            sy = data["py"] - y0
            if -20 < sx < VIEWPORT_W + 20 and -20 < sy < VIEWPORT_H + 20:
                ICON_DRAW.get(data["type"], _icon_sniper)(draw, sx, sy, COLOR_AMBER)
                if 5 < sx < VIEWPORT_W - 30 and 5 < sy < VIEWPORT_H - 10:
                    draw.text((sx + 9, sy - 4), data["label"],
                              fill=COLOR_AMBER, font=self._font_sm)

        # Scanlines
        frame.paste(self._scanlines, (0, 0), self._scanlines)
        draw = ImageDraw.Draw(frame)

        # Crosshair cursor at screen centre
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * 2 * math.pi)
        alpha = int(160 + 95 * pulse)
        col   = (*COLOR_AMBER_GLOW, alpha)
        pcx, pcy = VIEWPORT_W // 2, VIEWPORT_H // 2
        r = int(5 + 2 * pulse)
        draw.ellipse([pcx - r, pcy - r, pcx + r, pcy + r], outline=col)
        draw.line([(pcx - r - 4, pcy), (pcx - 2, pcy)], fill=col, width=1)
        draw.line([(pcx + 2, pcy), (pcx + r + 4, pcy)], fill=col, width=1)
        draw.line([(pcx, pcy - r - 4), (pcx, pcy - 2)], fill=col, width=1)
        draw.line([(pcx, pcy + 2), (pcx, pcy + r + 4)], fill=col, width=1)

        # HUD bars
        self._draw_hud(draw)

        return self._to_landscape(frame.convert("RGB"))

    def _draw_hud(self, draw):
        # Top bar
        draw.rectangle([0, 0, VIEWPORT_W, 14], fill=(5, 5, 5, 210))
        # Bottom bar
        draw.rectangle([0, VIEWPORT_H - 14, VIEWPORT_W, VIEWPORT_H], fill=(5, 5, 5, 210))

        draw.text((4, 2), "PIP-BOY 3000 MkV", fill=COLOR_AMBER, font=self._font_sm)

        # Map coords in bottom bar
        coord_str = f"X:{self.cam_x:04d}  Y:{self.cam_y:04d}"
        draw.text((4, VIEWPORT_H - 12), coord_str,
                  fill=COLOR_AMBER_DIM, font=self._font_sm)

        # Corner brackets
        s = 6
        for bx, by in [(0, 0), (VIEWPORT_W - s, 0),
                       (0, VIEWPORT_H - s), (VIEWPORT_W - s, VIEWPORT_H - s)]:
            draw.rectangle([bx, by, bx + s, by + s], outline=COLOR_AMBER)


# ─────────────────────────────────────────────────────────────
#  BOOT SPLASH
# ─────────────────────────────────────────────────────────────

def _show_boot_splash(gui):
    # Draw splash in landscape (320x240) then rotate 90° for the physical screen
    splash = Image.new("RGB", (VIEWPORT_W, VIEWPORT_H), COLOR_BG)
    d = ImageDraw.Draw(splash)
    d.rectangle([2, 2, VIEWPORT_W - 3, VIEWPORT_H - 3], outline=COLOR_AMBER)
    d.rectangle([4, 4, VIEWPORT_W - 5, VIEWPORT_H - 5], outline=COLOR_AMBER_DIM)

    cx, cy = VIEWPORT_W // 2, VIEWPORT_H // 2 - 30
    d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=COLOR_AMBER, width=2)
    d.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], outline=COLOR_AMBER_DIM)
    d.polygon([(cx, cy - 15), (cx - 13, cy + 8), (cx + 13, cy + 8)], fill=COLOR_AMBER)

    try:
        font_title = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 12)
        font_sub = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 8)
    except (IOError, OSError):
        font_title = font_sub = ImageFont.load_default()

    d.text((cx - 60, cy + 40), "PIP-BOY 3000 MkV",    fill=COLOR_AMBER,     font=font_title)
    d.text((cx - 55, cy + 58), "HARIDWAR WASTELAND",   fill=COLOR_AMBER_DIM, font=font_sub)
    d.text((cx - 55, cy + 80), "A=UP  C=DOWN  D=LEFT  B=RIGHT", fill=COLOR_AMBER, font=font_sub)
    d.text((cx - 30, cy + 100), "STAND BY",            fill=COLOR_AMBER_GLOW, font=font_sub)

    # Rotate to portrait orientation for the physical Unihiker screen
    splash = splash.rotate(-90, expand=True)
    splash.save("/tmp/pipboy_splash.png")
    gui.draw_image(x=0, y=0, image="/tmp/pipboy_splash.png")


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════╗")
    print("║   HARIDWAR WASTELAND — BOOTING...    ║")
    print("╚══════════════════════════════════════╝")

    # ── Hardware initialization ───────────────────────────────
    Board("unihiker").begin()
    
    # --- Compatibility Fix (Ensures your preferred syntax works) ---
    if not hasattr(Pin, "PULLUP") and hasattr(Pin, "PULL_UP"):
        Pin.PULLUP = Pin.PULL_UP
    if not hasattr(Pin, "read_digital") and hasattr(Pin, "value"):
        Pin.read_digital = Pin.value
    # -------------------------------------------------------------

    # Buzzer for audio feedback
    buzzer = Pin(Pin.P26, Pin.OUT)

    # Setup pins (Using your exact requested variable names)
    btn_p3 = Pin(Pin.P3, Pin.IN, Pin.PULLUP) # UP
    btn_p0 = Pin(Pin.P0, Pin.IN, Pin.PULLUP) # RIGHT
    btn_p1 = Pin(Pin.P1, Pin.IN, Pin.PULLUP) # DOWN
    btn_p2 = Pin(Pin.P2, Pin.IN, Pin.PULLUP) # LEFT

    print("[BOOT] Buttons Ready: P3(Up) P0(Right) P1(Down) P2(Left)")

    # ── GUI init ──────────────────────────────────────────────
    gui = GUI()
    gui.clear()
    _show_boot_splash(gui)
    time.sleep(2)

    display_img = gui.draw_image(x=0, y=0, image="/tmp/pipboy_splash.png")

    # ── Renderer ──────────────────────────────────────────────
    renderer = PipBoyRenderer()
    print("[BOOT] Renderer ready — entering loop")

    target_fps = 15
    frame_time = 1.0 / target_fps
    temp_path  = "/tmp/pipboy_frame.png"

    # ── Main loop ─────────────────────────────────────────────
    try:
        while True:
            t0 = time.time()

            # Read buttons (Using your exact requested syntax)
            move_x, move_y = 0, 0
            if btn_p3.read_digital() == 0: 
                move_y = -PAN_SPEED
            elif btn_p1.read_digital() == 0: 
                move_y =  PAN_SPEED
            
            if btn_p2.read_digital() == 0: 
                move_x = -PAN_SPEED
            elif btn_p0.read_digital() == 0: 
                move_x =  PAN_SPEED

            if move_x != 0 or move_y != 0:
                renderer.pan(move_x, move_y)
                # Quick audio feedback
                buzzer.value(1); time.sleep(0.002); buzzer.value(0)

            # Render and display
            frame = renderer.render_frame()
            frame.save(temp_path)
            display_img.config(image=temp_path)

            # High-speed refresh
            elapsed = time.time() - t0
            sleep_t = frame_time - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

    except KeyboardInterrupt:
        print("\n[EXIT] Shutdown requested")
    finally:
        gui.clear()
        print("[EXIT] Clean shutdown complete")


if __name__ == "__main__":
    main()
