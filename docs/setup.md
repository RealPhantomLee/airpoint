# Setup Guide

## Quick Install

```bash
# Linux
./scripts/install/linux.sh

# macOS
./scripts/install/macos.sh

# Windows
powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1
```

## System Requirements

### Minimum
| Component | Spec |
|---|---|
| CPU | Dual-core 2.0 GHz |
| RAM | 4 GB |
| Webcam | 720p |
| Python | 3.12 |
| Disk | ~200 MB (includes model) |

### Recommended
| Component | Spec |
|---|---|
| CPU | Quad-core 2.5 GHz+ |
| RAM | 8 GB |
| Webcam | 1080p |
| Python | 3.12 |

## Platform Setup

### Arch Linux

```bash
sudo pacman -S python python-pip git v4l-utils mesa libgl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git v4l-utils libgl1-mesa-glx
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

### Fedora

```bash
sudo dnf install python3 python3-pip git v4l-utils mesa-libGL
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

### macOS

```bash
brew install python git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

> macOS will prompt for camera access. Click **Allow**.

### Windows

```powershell
# Install Python 3.12 from winget or python.org
winget install Python.Python.3.12

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app\main.py
```

## Webcam Setup

### Test Your Camera

```bash
# Linux
v4l2-ctl --list-devices
ffplay /dev/video0

# macOS
# No CLI tool needed — macOS apps handle camera natively

# Windows
# Camera app in Start menu, or test via Python
python -c "import cv2; cap=cv2.VideoCapture(0); print(cap.read()[0]); cap.release()"
```

### Permission Issues (Linux)

```bash
# Add user to video group
sudo usermod -aG video $USER

# Log out and back in for changes to take effect
```

### Multiple Cameras

If you have multiple webcams, find the right device index:

```bash
# Linux
ls /dev/video*
# /dev/video0, /dev/video1, etc.

# Set in app/config/settings.json
# "camera": { "device_index": 1 }
```

## Performance Tuning

### For Low-End Hardware

```json
{
  "camera": {
    "resolution": [480, 360],
    "frame_skip": 3
  },
  "hand_tracking": {
    "model_complexity": 0,
    "min_detection_confidence": 0.5
  }
}
```

### For Best Accuracy

```json
{
  "camera": {
    "resolution": [1280, 720],
    "frame_skip": 1
  },
  "hand_tracking": {
    "model_complexity": 1,
    "min_detection_confidence": 0.7
  }
}
```

## Webcam Placement Tips

1. Position camera **slightly above eye level**
2. Keep background **uncluttered** and **solid-colored** if possible
3. Ensure **even lighting** on your hand
4. Avoid **strong backlighting** (don't sit facing a window)
5. Keep hand **6-18 inches** from camera
6. Good lighting matters more than camera quality

## Troubleshooting

| Problem | Solution |
|---|---|
| Camera not found | Check `device_index` in settings.json |
| Low FPS | Increase `frame_skip`, lower resolution |
| Cursor jittery | Increase smoothing, improve lighting |
| Gestures not detected | Improve hand visibility, raise `min_detection_confidence` |
| `libGL.so.1` missing | Install `libgl` (Arch) or `libgl1-mesa-glx` (Ubuntu) |
| PyQt5 blank window | Set `QT_QPA_PLATFORM=xcb` (Linux) |
| Model download fails | Check internet connection, model caches to `~/.cache/airpoint/` |
