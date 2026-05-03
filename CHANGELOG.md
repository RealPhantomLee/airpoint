# Changelog

All notable changes to this project will be documented in this file.

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
