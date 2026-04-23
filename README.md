# HARIDWAR WASTELAND — PIP-BOY 3000 MkV
## Setup & Deployment Guide

```
╔══════════════════════════════════════════════════════════╗
║  "War never changes. But at least now you have a map."  ║
╚══════════════════════════════════════════════════════════╝
```

---

## HARDWARE

| Component | Spec |
|-----------|------|
| **Board** | Unihiker M10 (Debian Linux) |
| **Display** | Built-in 240×320 touch LCD |
| **Buttons** | 4× tactile switches on custom PCB |

### Button Wiring

```
  Button      Unihiker Pin    Action
  ────────    ────────────    ──────
  Button A    P3              Pan UP
  Button B    P0              Pan RIGHT
  Button C    P1              Pan DOWN
  Button D    P2              Pan LEFT
  Buzzer      P26             Click feedback
```

> All button pins use internal pull-up resistors — buttons connect pin to GND.

---

## STEP 1 — INSTALL DEPENDENCIES

```bash
# On the Unihiker (via SSH or built-in Jupyter terminal):
pip install pillow

# These come pre-installed on the Unihiker:
# unihiker, pinpong
```

---

## STEP 2 — GENERATE THE BASE MAP (run on PC first)

The Unihiker doesn't have enough RAM to download & stitch OSM tiles.
Run the map generator on your PC or laptop:

```bash
# On your PC:
pip install requests pillow
python generate_map.py
```

This will:
1. Download ~25 OpenStreetMap tiles covering Haridwar
2. Stitch them into a 2000×2000 pixel image
3. Apply dark greyscale filter (amber tint applied at runtime)
4. Save as `map_base.png`

---

## STEP 3 — TRANSFER FILES TO UNIHIKER

```bash
# From your PC:
scp map_base.png root@unihiker.local:/root/
scp pipboy_map.py root@unihiker.local:/root/
```

---

## STEP 4 — RUN IT

```bash
# On the Unihiker:
cd /root
python pipboy_map.py
```

### Run at boot (optional)

```bash
sudo tee /etc/systemd/system/pipboy.service > /dev/null << 'EOF'
[Unit]
Description=Pip-Boy Map
After=multi-user.target

[Service]
User=root
WorkingDirectory=/root
ExecStart=/usr/bin/python3 /root/pipboy_map.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable pipboy.service
sudo systemctl start pipboy.service
```

---

## TROUBLESHOOTING

### Screen shows nothing
```bash
python3 -c "from unihiker import GUI; print('OK')"
# If fails: pip install unihiker
```

### Buttons not responding
- Check wiring: each button connects its pin to GND
- Verify pinpong version supports `Pin.PULLUP` — the code includes a compatibility shim for older versions

### `map_base.png` not found — placeholder grid shown
- Run `generate_map.py` on your PC and transfer the result
- The placeholder still works for testing buttons and UI

### Display too slow
```python
# In pipboy_map.py, reduce target FPS:
target_fps = 10   # default is 15

# Or increase grid spacing (fewer lines drawn):
GRID_CELL = 40    # default is 20
```

---

## ADDING YOUR OWN POIs

Edit the `POIS` dictionary in `pipboy_map.py`:

```python
POIS = {
    "My Spot": {"px": 1050, "py": 980, "type": "medical", "label": "SAFE HOUSE"},
}
```

`px`/`py` are pixel coordinates on the 2000×2000 map.
**Available icon types:** `sniper`, `medical`, `power`, `water`, `industry`

---

## FILE STRUCTURE

```
/root/
├── pipboy_map.py     ← Main app (run this)
├── generate_map.py   ← Map tile downloader (run on PC)
└── map_base.png      ← 2000×2000 Haridwar map (generated)
```

---

## PERFORMANCE

Target: **15 FPS** on Unihiker M10. PIL image operations are the bottleneck.
\
---

*"Vault-Tec wishes you a pleasant journey through the Haridwar Wasteland."*
