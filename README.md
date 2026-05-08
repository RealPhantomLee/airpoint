# Airpoint

**A gesture-based interaction framework for accessibility, presentations, and media control.**

Airpoint turns a webcam into a hands-free input device for the moments when reaching for a mouse is awkward, slow, or impossible — running a slide deck, controlling music while cooking, navigating a kiosk, or working around a mobility limitation.

It is **not** a general-purpose mouse replacement. It is a focused tool for a small set of use cases where touchless interaction genuinely helps.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)](https://github.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What it's for

| Use case | Why touchless helps |
|----------|---------------------|
| **Presentations** | Advance slides without breaking eye contact or walking back to the laptop |
| **Accessibility** | A small set of forgiving gestures for users for whom a mouse or trackpad is hard or painful |
| **Media control** | Pause music, skip tracks, change volume from the kitchen, the gym, or across the room |
| **Kiosks / shared displays** | Touchless interaction in environments where shared touchscreens are a hygiene problem |

## What it's *not* for

Airpoint is the wrong tool if you need any of these:

- **Long productivity sessions** — gestures fatigue your arm; a mouse exists for a reason
- **Gaming** — latency, jitter, and gesture ambiguity make this a poor fit
- **Precision work** — CAD, design, photo retouching all need finer control than a webcam can provide
- **High-throughput typing or shortcuts** — a keyboard wins, every time

If your goal is "replace my mouse," look elsewhere. If your goal is "let me control this from across the room without touching anything," you're in the right place.

---

## The four modes

Airpoint exposes one mode at a time. Each mode enables a small, internally-consistent gesture set so you don't accidentally trigger the wrong thing.

### 🖱️ Navigation (default)
Cursor + click + drag + scroll + pause. Use this when you want webcam-driven cursor control — typically as an accessibility cursor, or to demo what the framework can do.

### 📽️ Presentation
Cursor moves like a laser pointer. Pinch advances the slide. Swipe left/right for previous/next slide. Scroll is disabled so you can't accidentally scroll while gesturing.

### 🎵 Media
Cursor disabled. Open palm = play/pause. Swipe up/down = volume. Swipe left/right = previous/next track. Designed for "control my music from across the room."

### ♿ Accessibility
The most forgiving mode. Move + click + pause only. Heavy smoothing, slower cursor, generous debounce, and longer dwell times so unintended triggers are rare.

---

## Six gestures, total

The whole framework is built on six recognizers. Some are mode-specific.

| Gesture | How | Active in |
|---------|-----|-----------|
| **Move** | Index finger raised, all others curled | Navigation, Presentation, Accessibility |
| **Click** | Thumb-to-index pinch (rising edge) | Navigation, Presentation, Accessibility |
| **Drag** | Pinch and hold ≥ 350 ms | Navigation only |
| **Scroll** | Index + middle extended; move hand up or down | Navigation, Accessibility |
| **Pause / Resume** | Open palm held ≥ 800 ms | All modes (also = play/pause in Media) |
| **Swipe** | Quick horizontal or vertical motion of the index finger | Presentation, Media |

There used to be 15+ gestures (right-click, middle-click, double-click, four scroll directions, two-hand shortcut, fist-drag, volume-wave, etc.). They were removed because they made the framework hard to learn and easy to trigger by accident. The current six are the smallest set that covers the four real use cases.

---

## Architecture

```
Camera  →  FrameProcessor  →  HandTracker  →  GestureClassifier
                                                    │
                                                    ▼
                                        ModeManager → ActionDispatcher
```

Each layer has a single responsibility and a stable interface:

| Module | Responsibility |
|--------|----------------|
| `app/pipeline.py` | Camera capture loop, adaptive frame skipping, resilient reconnect with exponential backoff |
| `app/vision/hand_tracker.py` | MediaPipe Tasks Vision API wrapper |
| `app/vision/frame_processor.py` | Low-light enhancement, optional barrel-distortion correction |
| `app/gesture_engine/base_gesture.py` | `BaseGesture` (priority, debounce, cooldown, mode filter), `GestureContext`, `Action` |
| `app/gesture_engine/gestures.py` | The six concrete gesture classes |
| `app/gesture_engine/gesture_registry.py` | Discovery + iteration |
| `app/gesture_engine/gesture_classifier.py` | Per-frame conflict resolution and dispatch |
| `app/gesture_engine/mode_manager.py` | Active mode, threshold profiles, cursor overrides per mode |
| `app/control/action_dispatcher.py` | Routes Action objects to the mouse / media controllers, honors pause |
| `app/control/mouse.py` | Cross-platform cursor control (pynput) |
| `app/control/media.py` | Cross-platform media + slide-navigation keys (pynput) |
| `app/gui/main_window.py` | 5-control panel: Mode / Sensitivity / Smoothing / Camera / Tracking toggle |
| `app/gui/advanced_dialog.py` | Opt-in advanced settings (camera, tracking confidence, edge boost, ...) |

### Why this structure

- **Gestures are pure recognizers.** A gesture's job is to look at landmarks and say "yes, fired." It doesn't move the mouse, dispatch keys, or know which mode is active. That makes them trivial to test in isolation (see the headless smoke test in CI).
- **The dispatcher is the only OS-touching layer.** Swap pynput for uinput, AppleScript, or a remote sender, and gestures don't change.
- **ModeManager is a swap, not a rebuild.** Switching from Navigation to Media doesn't tear down the pipeline — it just changes which gestures the classifier asks the registry for, and which threshold profile is active.

---

## Quick start

```bash
git clone https://github.com/RealPhantomLee/airpoint.git
cd airpoint

# Make scripts executable (Linux / macOS, one-time)
chmod +x scripts/install/linux.sh scripts/install/macos.sh run.sh

# Install (one-liner per OS)
./scripts/install/linux.sh        # Linux
./scripts/install/macos.sh        # macOS
# Windows:
powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1

# Run
./run.sh                          # Linux / macOS
.\run.ps1                         # Windows
```

The first run downloads MediaPipe's hand-landmarker model (~170 MB) into `~/.cache/airpoint/models/`. Every subsequent run is local.

---

## The 5-control main panel

Everything you'll use day-to-day fits in five controls:

1. **Mode** — Navigation / Presentation / Media / Accessibility
2. **Sensitivity** — how far the cursor moves for a given hand motion
3. **Smoothing** — how much the cursor lags to filter jitter
4. **Camera** — pick your input device, see live status (running / stopped / error)
5. **Tracking toggle** — start or stop the pipeline

Anything more obscure (resolution, frame skip, detection-confidence thresholds, axis inversion, edge boost) lives behind an **Advanced…** button. The default values work well for most users; touch them only if you have a specific reason.

---

## Reliability

Airpoint is designed to fail gracefully, not silently:

- **Adaptive frame skipping.** The pipeline targets 25 FPS. If it falls behind on a slow CPU, it skips more frames automatically. If it has headroom, it scales back.
- **Camera resilience.** A dropped camera triggers exponential-backoff reconnect (1 → 2 → 4 → 8 seconds) before reporting an error.
- **Per-gesture debounce + global gesture lock.** The classifier won't fire two action gestures within 500 ms of each other unless one is a continuous gesture (Move, Drag-while-held).
- **Gesture state resets when the hand leaves the frame.** A held drag releases. A dwell timer resets. No stuck state.

---

## Privacy

All processing happens on your device. Specifically:

- The hand-tracking model runs locally — no frames or coordinates leave the machine.
- No telemetry. No analytics. No crash reports.
- The MediaPipe model is downloaded **once** from Google's CDN, verified over HTTPS, and cached locally. After that, no network calls.
- Pause via open-palm dwell turns off all input — useful when stepping away.

---

## Migration from older versions

If you used Airpoint before this refactor:

- Your existing `app/config/settings.json` is upgraded automatically. The new `mode` key defaults to `navigation`, which preserves prior cursor-driven behavior.
- The 11 gesture toggle checkboxes are gone. Gestures are now mode-determined; pick the mode that matches what you're doing.
- The 4-tab settings panel is gone. The five controls you actually used are on the main panel; the rest moved into **Advanced…**.
- Drag was triggered by closing your fist; it's now triggered by holding a pinch ≥ 350 ms (consistent with click, no separate hand pose).
- Right-click, middle-click, double-click, horizontal scroll, two-hand shortcut, and the "wave to change volume" gesture were removed. Volume in Media mode is a vertical swipe.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Adding a new gesture is a self-contained change: subclass `BaseGesture`, set `name`, `priority`, and `enabled_in_modes`, implement `detect()` and `fire()`, then register it. The classifier handles cooldowns, debounce, and mode filtering for you.

---

## Related projects

Other work in my portfolio across cyber, cloud, web, and AI:

- [VaultKeeper](https://github.com/RealPhantomLee/VaultKeeper) — local-first encrypted knowledge platform
- [Local-AI-Web-Workspace](https://github.com/RealPhantomLee/Local-AI-Web-Workspace) — self-hosted Ollama + AnythingLLM stack
- [vulnerability-management-lab](https://github.com/RealPhantomLee/vulnerability-management-lab) — end-to-end VM lifecycle on VulnHub
- [azure-security-monitoring-lab](https://github.com/RealPhantomLee/azure-security-monitoring-lab) — Azure hardening + KQL detections
- [CyberSec-Web-Services](https://github.com/RealPhantomLee/CyberSec-Web-Services) — production self-hosted business site

Full portfolio: [github.com/RealPhantomLee](https://github.com/RealPhantomLee)

---

## License

[MIT](LICENSE)

## Credits

- [MediaPipe](https://ai.google.dev/edge/mediapipe) — hand tracking
- [OpenCV](https://opencv.org/) — video processing
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) — GUI framework
- [pynput](https://pynput.readthedocs.io/) — cross-platform input control
