# Airpoint

**Touchless cursor control powered by computer vision.**

Move your mouse, click, scroll, and drag — all with hand gestures. No hardware modifications. No cloud processing. Just your webcam.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)](https://github.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## Demo

> Raise your index finger to move. Pinch to click. Close your fist to drag.

## Features

- **15+ hand gestures** — click, double-click, right-click, scroll, drag, volume control
- **Full GUI control panel** — sensitivity/smoothing sliders, gesture toggles, live preview
- **Privacy-first** — no network calls, no data storage, no telemetry
- **Cross-platform** — Linux, macOS, Windows
- **Low-end optimized** — configurable frame skip, model complexity, resolution
- **Plug and play** — works with any USB or built-in webcam

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/airpoint.git
cd airpoint

# Install (one-liner for your OS)
./scripts/install/linux.sh   # Linux
./scripts/install/macos.sh   # macOS
# Windows: powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1

# Run
./run.sh                     # Linux/macOS
```

## Gesture Map

| Gesture | Action |
|---|---|
| ☝️ Index finger up | Move cursor |
| 👌 Thumb + index pinch | Left click |
| ⚡ Double pinch (quick) | Double click |
| 🤏 Thumb + middle pinch | Right click |
| 🤌 Thumb + ring pinch | Middle click |
| ✌️ Two fingers up/down | Vertical scroll |
| ↔️ Two finger spread | Horizontal scroll |
| ✊ Closed fist | Drag mode |
| 🖐️ Open palm (hold 1s) | Pause system |
| 👍 Thumb wave right | Volume up |
| 👈 Thumb wave left | Volume down |
| 🙌 Two hands detected | Shortcut mode |

## Installation

### Requirements

- Python 3.10+
- Webcam (720p minimum, 1080p recommended)
- ~200 MB disk space (includes ML model download)

### Linux (Arch, Ubuntu, Debian, Fedora)

```bash
git clone https://github.com/YOUR_USERNAME/airpoint.git
cd airpoint
./scripts/install/linux.sh
./run.sh
```

### macOS

```bash
git clone https://github.com/YOUR_USERNAME/airpoint.git
cd airpoint
./scripts/install/macos.sh
./run.sh
```

> macOS will prompt for camera access on first run. Click **Allow**.

### Windows

```powershell
git clone https://github.com/YOUR_USERNAME/airpoint.git
cd airpoint
powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1
.\venv\Scripts\Activate.ps1
python app\main.py
```

### Manual Install

```bash
git clone https://github.com/YOUR_USERNAME/airpoint.git
cd airpoint

python -m venv venv
source venv/bin/activate          # Linux/macOS
# or: venv\Scripts\Activate.ps1   # Windows

pip install -r requirements.txt
python app/main.py
```

## Configuration

All settings live in `app/config/settings.json`. Edit to your liking:

### Camera

```json
{
  "camera": {
    "device_index": 0,
    "resolution": [1280, 720],
    "fps": 30,
    "frame_skip": 2
  }
}
```

| Key | Default | Description |
|---|---|---|
| `device_index` | `0` | Webcam device number (`0` = default) |
| `resolution` | `[1280, 720]` | Camera resolution `[width, height]` |
| `fps` | `30` | Target frames per second |
| `frame_skip` | `2` | Process every Nth frame (higher = less CPU) |

### Cursor

```json
{
  "cursor": {
    "sensitivity": 1.5,
    "smoothing_alpha": 0.3,
    "deadzone": 0.02,
    "invert_x": false,
    "invert_y": false
  }
}
```

| Key | Default | Description |
|---|---|---|
| `sensitivity` | `1.5` | Cursor speed multiplier |
| `smoothing_alpha` | `0.3` | EMA smoothing (lower = smoother, 0.1-0.9) |
| `deadzone` | `0.02` | Ignore movements below this threshold |

### Gestures

```json
{
  "gestures": {
    "pinch_threshold": 0.04,
    "scroll_threshold": 0.015,
    "click_debounce_ms": 200
  }
}
```

| Key | Default | Description |
|---|---|---|
| `pinch_threshold` | `0.04` | Max distance for pinch detection (normalized) |
| `scroll_threshold` | `0.015` | Minimum movement to register scroll |
| `click_debounce_ms` | `200` | Minimum ms between clicks |

## Troubleshooting

### Camera not detected

```bash
# Linux: list video devices
v4l2-ctl --list-devices

# Test camera feed
ffplay /dev/video0
```

If your camera is on a different device, set `device_index` in `settings.json`.

### Low FPS

- Increase `frame_skip` in `settings.json` (`3` or `4`)
- Lower resolution to `[640, 480]`
- Set `model_complexity` to `0` in `hand_tracking`
- Close other CPU-intensive applications

### Cursor jittery

- Increase the **Smoothing** slider in the GUI
- Lower the **Sensitivity** slider
- Increase `deadzone` in `settings.json`
- Ensure good, even lighting on your hand

### PyQt5 display issues

```bash
# Force X11 backend (Linux)
export QT_QPA_PLATFORM=xcb

# Force Wayland backend (Linux)
export QT_QPA_PLATFORM=wayland
```

### Permission denied on webcam (Linux)

```bash
sudo usermod -aG video $USER
# Log out and back in
```

### `ImportError: libGL.so.1` (Linux)

```bash
# Arch
sudo pacman -S libgl
# Ubuntu/Debian
sudo apt-get install libgl1-mesa-glx
# Fedora
sudo dnf install mesa-libGL
```

### Mediapipe install fails

```bash
pip install --upgrade pip
pip install mediapipe
```

## Architecture

```
app/
├── main.py                 # Entry point
├── gui/
│   ├── window.py           # PyQt5 main window + CameraThread
│   └── widgets.py          # Custom Qt widgets
├── vision/
│   ├── hand_tracker.py     # MediaPipe Tasks hand detection
│   ├── gesture_engine.py   # Gesture recognition (15+ gestures)
│   └── smoothing.py        # EMA + SMA cursor smoothing
├── control/
│   ├── mouse.py            # Cross-platform mouse control (pynput)
│   └── hotkeys.py          # Global keyboard shortcuts
├── config/
│   └── settings.json       # All tunable settings
└── utils/
    ├── fps.py              # FPS counter
    └── platform.py         # Cross-platform utilities
```

## Performance

| Hardware | Resolution | FPS | CPU Usage |
|---|---|---|---|
| Low-end (dual-core) | 640x480 | 25-30 | ~30% |
| Low-end (dual-core) | 1280x720 | 15-20 | ~50% |
| Mid-range (quad-core) | 1280x720 | 25-30 | ~35% |
| Desktop (6+ core) | 1280x720 | 30+ | ~20% |

### Optimization Tips

- Use `model_complexity: 0` for faster processing
- Use `model_complexity: 1` for better accuracy
- Increase `frame_skip` to reduce CPU load
- Good lighting dramatically improves detection accuracy

## Privacy

Airpoint is **fully offline** by design:

- **No cloud processing** — all ML inference runs locally on your device
- **No data logging** — no frames, coordinates, or gestures are saved
- **No network calls** — the application requires zero internet access
- **User control** — toggle camera off via GUI when not in use
- **No telemetry** — no analytics, no crash reports, no tracking

The hand tracking model is downloaded once from Google's servers on first run and cached locally.

## Development

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/airpoint.git
cd airpoint
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python app/main.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)

## Credits

- [MediaPipe](https://ai.google.dev/edge/mediapipe) — Hand tracking
- [OpenCV](https://opencv.org/) — Video processing
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) — GUI framework
- [pynput](https://pynput.readthedocs.io/) — Cross-platform input control
