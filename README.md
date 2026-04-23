# HARIDWAR WASTELAND — PIP-BOY 3000 MkV
## Complete Setup & Deployment Guide

```
╔══════════════════════════════════════════════════════════╗
║  "War never changes. But at least now you have GPS."    ║
╚══════════════════════════════════════════════════════════╝
```

---

## HARDWARE CHECKLIST

| Component | Spec |
|-----------|------|
| **MCU** | Unihiker M10 (Debian Linux) |
| **Display** | Built-in 240×320 touch LCD |
| **GPS** | GY-NEO6MV2 (u-blox NEO-6M) |
| **Connection** | Hardware UART |

### Wiring Diagram

```
  GY-NEO6MV2          Unihiker M10
  ──────────          ────────────
     VCC  ──────────►  3.3V
     GND  ──────────►  GND
      TX  ──────────►  P19 (RX)
      RX  ◄──────────  P20 (TX)
```

> ⚠️ The GPS must have a **clear view of the sky** to acquire a fix.
> First fix after cold boot can take **2–10 minutes**.

---

## STEP 1 — FREE UP THE UART PORT

The Unihiker uses `/dev/ttyS0` as a console by default. You must disable this:

```bash
# SSH into your Unihiker first:
ssh root@unihiker.local   # or use its IP address

# Disable the serial console getty service
sudo systemctl stop serial-getty@ttyS0.service
sudo systemctl disable serial-getty@ttyS0.service

# Verify the port is free (should show nothing):
fuser /dev/ttyS0

# Also ensure your user has permission:
sudo usermod -a -G dialout root
```

---

## STEP 2 — INSTALL PYTHON DEPENDENCIES

```bash
# On the Unihiker (via SSH or the built-in Jupyter terminal):
pip install pyserial pillow

# The 'unihiker' library is pre-installed on the device.
# If not:
pip install unihiker
```

---

## STEP 3 — GENERATE THE BASE MAP (run on PC first!)

The Unihiker doesn't have enough RAM to download & stitch OSM tiles efficiently.
Run the map generator on your PC or laptop:

```bash
# On your PC:
pip install requests pillow
python generate_map.py
```

This will:
1. Download ~25 OpenStreetMap tiles covering Haridwar (cached locally)
2. Stitch them into a 2000×2000 pixel image
3. Apply the Pip-Boy dark/grey filter
4. Save as `map_base.png`
5. **Print exact calibration pixel values** for your specific map

> 🗺️ The generator prints calibration output like this:
> ```
> CAL_A: Har Ki Pauri → Pixel (1000, 1000)
>        Lat/Lon: 29.9457, 78.1642
> CAL_B: Chandi Devi → Pixel (1187, 823)
>        Lat/Lon: 29.963, 78.182
> ```
> **Copy these values into `pipboy_map.py`** (the CAL_A/CAL_B section).

---

## STEP 4 — TRANSFER FILES TO UNIHIKER

```bash
# From your PC, copy both files to Unihiker:
scp map_base.png root@unihiker.local:/root/
scp pipboy_map.py root@unihiker.local:/root/

# Verify transfer:
ssh root@unihiker.local "ls -lh /root/map_base.png"
# Expected: something like "-rw-r--r-- 1 root root 1.8M ..."
```

---

## STEP 5 — UPDATE CALIBRATION IN pipboy_map.py

Open `pipboy_map.py` on the Unihiker and update the calibration section:

```python
# Find these lines (~line 80) and update with your printed values:
CAL_A_LAT, CAL_A_LON = 29.9457, 78.1642
CAL_A_PX,  CAL_A_PY  = 1000, 1000      # ← Always center

CAL_B_LAT, CAL_B_LON = 29.9630, 78.1820
CAL_B_PX,  CAL_B_PY  = 1187, 823       # ← Replace with your printed values
```

> Better calibration = more accurate POI placement.
> If you want to improve further, add a third calibration point and
> implement bilinear interpolation.

---

## STEP 6 — RUN IT!

```bash
# On the Unihiker:
cd /root
python pipboy_map.py

# To run at boot (create a systemd service):
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

### "No GPS fix" — Red blinking crosshair
- Take the device **outdoors** with clear sky view
- Wait up to 10 minutes for cold start fix
- Verify wiring: TX→P19, RX→P20 (not crossed wrong)
- Check serial port: `python3 -c "import serial; s=serial.Serial('/dev/ttyS0',9600); print(s.readline())"`

### "Permission denied: /dev/ttyS0"
```bash
sudo chmod 666 /dev/ttyS0
# Or permanently:
sudo usermod -a -G dialout root
```

### "map_base.png not found" — Placeholder grid shown
- Run `generate_map.py` on your PC and transfer the result
- The placeholder still works for testing GPS and UI

### Screen shows nothing / display errors
```bash
# Check unihiker library is installed:
python3 -c "from unihiker import GUI; print('OK')"
# If fails: pip install unihiker
```

### GPS reads but coordinates look wrong / POIs misplaced
- Your calibration values need updating
- Run `generate_map.py` again — it prints exact pixel coordinates
- Or manually open `map_base.png` in GIMP and note the pixel position of
  two landmarks you can find on-ground with GPS

---

## ADDING YOUR OWN POIs

Edit the `POIS` dictionary in `pipboy_map.py`:

```python
POIS = {
    # Add your own:
    "My House":  {"lat": 29.9XXX, "lon": 78.1XXX, "type": "medical", "label": "SAFE HOUSE"},
    "Your POI":  {"lat": 29.9XXX, "lon": 78.1XXX, "type": "sniper",  "label": "OVERLOOK"},
}
```

**Available icon types:** `sniper`, `medical`, `power`, `water`, `industry`

---

## FILE STRUCTURE

```
/root/
├── pipboy_map.py       ← Main application (this is the one to run)
├── generate_map.py     ← Map generator (run on PC, not Unihiker)
├── map_base.png        ← 2000×2000 Haridwar base map (generated)
└── README.md           ← This file
```

---

## PERFORMANCE NOTES

The render loop targets **15 FPS** on the Unihiker M10.
PIL image operations are the bottleneck. If it's too slow:

```python
# In pipboy_map.py, reduce target FPS:
target_fps = 10   # Try 10 or even 5

# Or disable scanlines (comment out section 6 in render_frame)
# Or reduce GRID_CELL from 20 to 40 (fewer grid lines)
```

---

*"Vault-Tec wishes you a pleasant journey through the Haridwar Wasteland."*
