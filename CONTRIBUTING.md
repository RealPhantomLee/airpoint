# Contributing to Airpoint

Thanks for your interest! Here's how to get started.

## Quick Start

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Test locally
5. Commit with a clear message (`git commit -m "feat: add gesture X"`)
6. Push and open a PR

## Code Style

- Follow PEP 8
- Use type hints on all public methods
- Keep functions focused (single responsibility)
- No hardcoded paths — use `pathlib`
- No secrets or personal paths in commits

## Adding New Gestures

1. Define the gesture in `app/vision/gesture_engine.py`
2. Add the action mapping in `app/control/mouse.py` or `app/control/hotkeys.py`
3. Add a toggle checkbox in `app/gui/window.py`
4. Document in `README.md` gesture table
5. Test on multiple platforms if possible

## Platform Testing

Before submitting a PR, test on your platform:

```bash
# Linux
./scripts/install/linux.sh

# macOS
./scripts/install/macos.sh

# Windows
powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1
```

## Pull Request Checklist

- [ ] Code compiles (`python -m py_compile app/main.py`)
- [ ] No personal paths or secrets
- [ ] README updated (new features, gestures, config)
- [ ] Works on your platform
- [ ] Follows existing code style

## Reporting Issues

Include:
- OS and version
- Python version
- Webcam model
- Error output (if any)
- Steps to reproduce
