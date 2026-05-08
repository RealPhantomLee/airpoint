# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] — 2026-05-08

Major refactor and repositioning. **Airpoint is now a gesture-based interaction
framework for accessibility, presentations, and media control** — not a
general-purpose mouse replacement. Existing config files are upgraded
automatically; default mode is `navigation`, which preserves prior behavior.

### Repositioned
- New pitch and use-case scope. README explicitly documents what Airpoint *is* and *is not* for. Long productivity sessions, gaming, and precision work are explicit non-goals.

### Added
- **Four interaction modes**: Navigation (default cursor), Presentation (laser-style + slide control), Media (cursor disabled, palm/swipes drive media keys), Accessibility (heavily smoothed, generous debounce, cursor + click + pause only). Each mode has its own threshold profile and cursor overrides applied automatically on switch.
- **`app/gesture_engine/` package** with a clean architecture: `BaseGesture` (priority, debounce, cooldown, mode filter), `GestureRegistry`, `ModeManager`, and a per-frame `GestureClassifier` that resolves conflicts via priority and global cooldown.
- **`ActionDispatcher`** as the only OS-touching layer. Gestures emit `Action` objects describing intent; the dispatcher routes them to the mouse/media controllers and honors pause.
- **`Pipeline`** class with adaptive frame skipping (targets 25 FPS) and exponential-backoff camera reconnect (1 → 2 → 4 → 8 s).
- **`AdvancedDialog`** for opt-in power-user settings (camera resolution, tracking confidence, edge boost, axis inversion). The 5-control main panel covers everything 90% of users will touch.
- **`MediaController.play_pause`, `slide_next`, `slide_prev`** for the new modes.

### Removed
- Eight gestures: double-click, right-click, middle-click, scroll-left, scroll-right, two-hand shortcut, fist-drag, thumb-wave-volume. They added cognitive load without commensurate value. Drag is now hold-pinch (consistent with click). Volume is a vertical swipe in Media mode.
- Four unimplemented gesture stubs (`next_track`, `prev_track`, `copy`, `paste`) declared in the old engine but never wired up.
- The 11-checkbox "Gestures" tab. Gesture availability is now mode-determined.
- The 4-tab settings panel (Gestures / Cursor / Camera / Settings). The five core controls live on the main panel; the rest move into Advanced.
- `app/control/hotkeys.py` (HotkeyManager was a dead skeleton; MediaController moved to `app/control/media.py`).
- `app/gui/widgets.py` (unused custom widgets).

### Changed
- **Default smoothing**: `cursor.smoothing_alpha` 0.30 → 0.22, `cursor.moving_average_window` 5 → 7. Smoother default cursor for new users; existing users keep their tuned values.
- **Default `max_num_hands`**: 2 → 1. Less ambiguity, fewer false positives.
- Drag trigger is now thumb-index pinch *held* ≥ 350 ms instead of a closed fist. One pose for click + drag.
- Settings file gained a `mode` key (default `navigation`).

### Notes for users on 1.x
- Your settings file is loaded as-is. The new `mode` key defaults to `navigation`; toggle modes from the dropdown.
- If you relied on right-click, middle-click, double-click, horizontal scroll, or two-hand shortcuts, those gestures are gone in 2.0. Use OS shortcuts or open Advanced to script your own (the gesture API is small enough to subclass — see `BaseGesture`).

## [1.1.0] — 2026-05-04

### Added
- **System tray** — closing the window now minimises to tray; double-click to restore; right-click menu for Show Window, Start/Stop Tracking, and Quit
- **Camera auto-recovery** — 30 consecutive read failures trigger a reconnect loop (3 attempts, 2 s apart) with live status messages; recovers from USB disconnects without restarting the app
- **MediaController** — volume up/down/mute, next/prev track, copy/paste via pynput keyboard media keys; volume gestures now change system volume on all platforms
- **Model download progress** — status bar shows "Downloading model (~170 MB)..." on first run instead of silently blocking
- **Settings validation** — all known settings clamped to safe ranges on every load; malformed or out-of-range values in `settings.json` no longer crash the app
- **SHA-256 integrity framework** — model download uses an explicit SSL context; set `MODEL_SHA256` in `hand_tracker.py` to enable checksum verification after download

### Fixed
- **Click debounce never fired** — `_last_click_time` was stored in seconds but compared in milliseconds, making the debounce difference always ~1.7 trillion; every pinch registered a click regardless of speed. Now stored in milliseconds
- **Scroll cooldown double-decremented** — cooldown counted down twice per active scroll frame (once inside the detection block, once in the outer tick), halving the effective cooldown. Removed the redundant inner decrement
- **Spurious no-op in scroll detection** — a dead expression `gestures["scroll_up"] if delta > 0 else gestures["scroll_down"]` with no assignment sat above the real assignment line; removed
- **Left-hand thumb detection** — `_is_finger_extended` for thumb hardcoded the right-hand x-axis direction; now accepts a `handedness` parameter and checks the correct direction per hand
- **`is_wayland()` always returned False** — checked `"wayland" in platform.system().lower()` which is always `"linux"`; now correctly checks `WAYLAND_DISPLAY` and `XDG_SESSION_TYPE` environment variables
- **Sensitivity slider had no effect** — `move_cursor` stored `self.sensitivity` but never applied it; cursor position is now scaled around the screen centre by the sensitivity factor
- **`run.sh` looked for venv in parent directory** — `PROJECT_DIR` was set to `dirname($SCRIPT_DIR)` instead of `$SCRIPT_DIR`, causing "No virtual environment found" on every run

### Performance
- `frame_processor`: brightness computed once per frame (was computed twice by `_auto_exposure` and `_is_low_light` independently); brightness/contrast LUTs precomputed at init and on settings change instead of rebuilt per frame; removed unconditional `frame.copy()`; LUT construction now uses vectorised numpy instead of Python list comprehensions
- `hand_tracker`: `_CONNECTIONS` list moved to class constant (was re-allocated every frame); timestamps now use wall-clock time so MediaPipe VIDEO mode gets accurate inter-frame timing at variable FPS
- `gesture_engine`: `_count_extended` called once per detection cycle (was called 3×); `two_fingers_up` precomputed once and reused for both scroll checks
- `window`: frames pre-resized to 960×540 in `CameraThread` before emitting, removing the per-frame smooth-scale from the GUI thread; `Qt.SmoothTransformation` → `Qt.FastTransformation`
- `mouse`: sensitivity applied via centre-scaled position mapping

### Changed
- Settings writes debounced to 0.5 s — rapid slider drags no longer write to disk on every tick
- `wide_angle_correction` defaults to `False` — saves 21 per-landmark math ops per frame for users without a GoPro
- Python requirement locked to 3.12 across all installers and documentation

### Removed
- `pyautogui` dependency — was listed in `requirements.txt` but never imported anywhere
- `app/config/settings.py` — empty zero-byte placeholder file
- `_correct_barrel_distortion` stub in `frame_processor.py` — dead method that returned the frame unchanged

### Documentation
- Replaced placeholder clone URLs with the real repository URL
- Added `chmod +x` step to Linux/macOS install instructions
- Added Windows `run.ps1` quick-start to README
- Added `frame_processor.py` to architecture diagram
- Added "Camera disconnects while running" troubleshooting section
- Updated Privacy section to note HTTPS model download and local cache path

## [1.0.0] — 2026-05-03

### Initial Release

#### Features
- Real-time hand tracking via MediaPipe Tasks API
- 15+ touchless gestures (click, scroll, drag, volume, etc.)
- Full PyQt5 GUI with live camera preview
- Low-end hardware optimization (frame skipping, model complexity toggle)
- Privacy-first: no network calls, no data storage, local-only processing
- Cross-platform support (Linux, macOS, Windows)
- Camera idle timeout toggle
- Sensitivity and smoothing sliders
- Live gesture indicator

#### Gestures
- Index finger → cursor movement
- Thumb+index pinch → left click
- Double pinch → double click
- Thumb+middle pinch → right click
- Thumb+ring pinch → middle click
- Two fingers up → vertical scroll
- Two finger spread → horizontal scroll
- Closed fist → drag mode
- Open palm hold → pause system
- Thumb wave → volume control
- Two hands → shortcut mode

#### Technical
- MediaPipe v0.10+ Tasks API (not legacy solutions API)
- EMA + SMA cursor smoothing
- Background camera thread for responsive GUI
- Configurable via `settings.json`
