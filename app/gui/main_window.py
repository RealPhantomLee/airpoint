"""Minimal control panel for Airpoint.

Five controls only:

    1. Mode             dropdown   (Navigation / Presentation / Media / Accessibility)
    2. Sensitivity      slider     (0.5 – 3.0×)
    3. Smoothing        slider     (Light – Heavy)
    4. Camera           combo + status pill
    5. Tracking toggle  start/stop button

Plus a small live preview, an FPS / status line, and an "Advanced…" button
that opens `AdvancedDialog` for power users.

Threading: the vision pipeline runs on its own daemon thread (owned by
`Pipeline`). It calls plain Python callbacks; we re-emit those as Qt signals
via `_Bridge` so all GUI updates happen on the main thread.
"""

from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings
from app.control.action_dispatcher import ActionDispatcher
from app.control.media import MediaController
from app.control.mouse import MouseController
from app.gesture_engine import GestureClassifier, ModeManager
from app.gui.advanced_dialog import AdvancedDialog
from app.pipeline import Pipeline
from app.utils.platform import detect_cameras
from app.vision.hand_tracker import HandTracker


class _Bridge(QObject):
    """Routes pipeline callbacks (worker thread) onto Qt signals (main thread)."""

    frame = pyqtSignal(np.ndarray)
    fps = pyqtSignal(float)
    status = pyqtSignal(str)
    camera_state = pyqtSignal(str)


class MainWindow(QMainWindow):
    PREVIEW_W = 480
    PREVIEW_H = 360

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

        self.setWindowTitle(settings.get("gui.window_title", "Airpoint"))
        self.resize(820, 460)

        # ----- core objects (created on Start, see _start_tracking) -----
        self._mode_manager = ModeManager(settings.get("mode", "navigation"))
        self._mouse = MouseController(settings)
        self._mouse.set_paused(True)
        self._media = MediaController()
        self._dispatcher = ActionDispatcher(
            settings, self._mouse, self._media, self._mode_manager
        )
        self._classifier = GestureClassifier(self._mode_manager)
        self._tracker: HandTracker | None = None
        self._pipeline: Pipeline | None = None

        # ----- bridge worker → main-thread signals -----
        self._bridge = _Bridge()
        self._bridge.frame.connect(self._on_frame)
        self._bridge.fps.connect(self._on_fps)
        self._bridge.status.connect(self._on_status)
        self._bridge.camera_state.connect(self._on_camera_state)

        # ----- build UI -----
        self._build_ui()
        self._build_tray()
        self._apply_dark_theme()

        # Populate cameras lazily after first paint.
        QTimer.singleShot(150, self._refresh_cameras)

    # ----- UI -----

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ----- left: preview -----
        left = QVBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(self.PREVIEW_W, self.PREVIEW_H)
        self.preview.setStyleSheet("background:#0b0f17; border-radius:8px;")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setText("Camera preview\n(off)")
        left.addWidget(self.preview)

        info_row = QHBoxLayout()
        self.fps_label = QLabel("FPS: —")
        self.fps_label.setStyleSheet("color:#8b95a8; font-size:11px;")
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color:#34d399; font-size:11px;")
        info_row.addWidget(self.fps_label)
        info_row.addStretch(1)
        info_row.addWidget(self.status_label)
        left.addLayout(info_row)
        layout.addLayout(left)

        # ----- right: 5 controls -----
        right = QVBoxLayout()
        right.setSpacing(12)

        title = QLabel("Airpoint")
        title.setStyleSheet("color:#e6edf3; font-size:20px; font-weight:bold;")
        right.addWidget(title)

        subtitle = QLabel("Touchless interaction framework")
        subtitle.setStyleSheet("color:#8b95a8; font-size:11px;")
        right.addWidget(subtitle)

        right.addWidget(self._separator())

        # 1. Mode
        right.addWidget(self._label("Mode"))
        self.mode_combo = QComboBox()
        for m in ModeManager.all_modes():
            self.mode_combo.addItem(m.label, m.name)
        active_idx = self.mode_combo.findData(self._mode_manager.active.name)
        if active_idx >= 0:
            self.mode_combo.setCurrentIndex(active_idx)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        right.addWidget(self.mode_combo)

        self.mode_help = QLabel(self._mode_manager.active.description)
        self.mode_help.setWordWrap(True)
        self.mode_help.setStyleSheet("color:#8b95a8; font-size:10px;")
        right.addWidget(self.mode_help)

        # 2. Sensitivity
        sens = float(self.settings.get("cursor.sensitivity", 1.3))
        right.addWidget(self._label(f"Sensitivity"))
        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(5, 30)              # 0.5×–3.0×
        self.sens_slider.setValue(int(sens * 10))
        self.sens_slider.valueChanged.connect(self._on_sens_change)
        right.addWidget(self.sens_slider)

        # 3. Smoothing  (Heavy ←→ Light, mapped to alpha 0.10–0.55)
        alpha = float(self.settings.get("cursor.smoothing_alpha", 0.22))
        right.addWidget(self._label("Smoothing"))
        self.smooth_slider = QSlider(Qt.Horizontal)
        self.smooth_slider.setRange(10, 55)           # alpha 0.10–0.55
        self.smooth_slider.setValue(int(alpha * 100))
        self.smooth_slider.valueChanged.connect(self._on_smooth_change)
        right.addWidget(self.smooth_slider)

        right.addWidget(self._separator())

        # 4. Camera
        cam_row = QHBoxLayout()
        cam_row.addWidget(self._label("Camera"), 0)
        self.cam_combo = QComboBox()
        self.cam_combo.addItem("Detecting…", -1)
        self.cam_combo.currentIndexChanged.connect(self._on_camera_change)
        cam_row.addWidget(self.cam_combo, 1)
        right.addLayout(cam_row)

        cam_status_row = QHBoxLayout()
        self.cam_dot = QLabel("●")
        self.cam_dot.setStyleSheet("color:#6b7280; font-size:14px;")
        self.cam_status_text = QLabel("Stopped")
        self.cam_status_text.setStyleSheet("color:#8b95a8; font-size:11px;")
        cam_status_row.addWidget(self.cam_dot)
        cam_status_row.addWidget(self.cam_status_text)
        cam_status_row.addStretch(1)
        right.addLayout(cam_status_row)

        # 5. Tracking toggle
        self.tracking_btn = QPushButton("Start tracking")
        self.tracking_btn.setMinimumHeight(38)
        self.tracking_btn.clicked.connect(self._toggle_tracking)
        right.addWidget(self.tracking_btn)

        # Advanced (opt-in)
        self.advanced_btn = QPushButton("Advanced…")
        self.advanced_btn.clicked.connect(self._open_advanced)
        right.addWidget(self.advanced_btn)

        right.addStretch(1)
        layout.addLayout(right, 1)

    def _build_tray(self) -> None:
        # Programmatically painted green dot icon.
        pix = QPixmap(16, 16)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#34d399"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 12, 12)
        p.end()

        self.tray = QSystemTrayIcon(QIcon(pix), self)
        menu = QMenu()
        a_show = QAction("Show window", self)
        a_show.triggered.connect(self.showNormal)
        a_show.triggered.connect(self.activateWindow)
        a_quit = QAction("Quit Airpoint", self)
        a_quit.triggered.connect(self._quit)
        menu.addAction(a_show)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background:#0b0f17; color:#e6edf3; }
            QPushButton {
                background:#1f2937; color:#e6edf3; border:1px solid #374151;
                border-radius:6px; padding:8px 12px;
            }
            QPushButton:hover { background:#374151; }
            QPushButton:pressed { background:#111827; }
            QComboBox {
                background:#1f2937; color:#e6edf3; border:1px solid #374151;
                border-radius:6px; padding:6px 8px;
            }
            QSlider::groove:horizontal {
                background:#1f2937; height:6px; border-radius:3px;
            }
            QSlider::handle:horizontal {
                background:#34d399; width:16px; margin:-6px 0; border-radius:8px;
            }
            QSlider::sub-page:horizontal { background:#34d399; border-radius:3px; }
            """
        )

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#cbd5e1; font-size:11px; font-weight:bold;")
        return lbl

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#1f2937;")
        return sep

    # ----- callbacks: pipeline → bridge → here -----

    def _on_frame(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.PREVIEW_W, self.PREVIEW_H, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview.setPixmap(pix)

    def _on_fps(self, fps: float) -> None:
        self.fps_label.setText(f"FPS: {fps:.0f}")

    def _on_status(self, msg: str) -> None:
        self.status_label.setText(msg)

    def _on_camera_state(self, state: str) -> None:
        colors = {"running": "#34d399", "stopped": "#6b7280", "error": "#ef4444"}
        text = {"running": "Running", "stopped": "Stopped", "error": "Camera error"}
        self.cam_dot.setStyleSheet(f"color:{colors.get(state, '#6b7280')}; font-size:14px;")
        self.cam_status_text.setText(text.get(state, state))
        self.tracking_btn.setText("Stop tracking" if state == "running" else "Start tracking")

    # ----- control handlers -----

    def _on_mode_change(self, _idx: int) -> None:
        name = self.mode_combo.currentData()
        if not name:
            return
        if self._mode_manager.set_active(name):
            self.settings.set("mode", name)
            self.mode_help.setText(self._mode_manager.active.description)
            self.status_label.setText(f"Mode: {self._mode_manager.active.label}")

    def _on_sens_change(self, value: int) -> None:
        s = value / 10.0
        self._mouse.update_sensitivity(s)
        self.settings.set("cursor.sensitivity", s)

    def _on_smooth_change(self, value: int) -> None:
        alpha = value / 100.0
        self._mouse.smoother.update_params(alpha=alpha)
        self.settings.set("cursor.smoothing_alpha", alpha)

    def _on_camera_change(self, _idx: int) -> None:
        device = self.cam_combo.currentData()
        if device is None or device < 0:
            return
        self.settings.set("camera.device_index", int(device))
        # Restart pipeline if it's running so the new device is picked up.
        if self._pipeline and self._pipeline.is_running:
            self._stop_tracking()
            self._start_tracking()

    def _refresh_cameras(self) -> None:
        cams = detect_cameras(max_index=4) or [{"index": 0, "name": "Camera 0"}]
        self.cam_combo.blockSignals(True)
        self.cam_combo.clear()
        active = int(self.settings.get("camera.device_index", 0))
        for cam in cams:
            self.cam_combo.addItem(cam["name"], cam["index"])
        idx = self.cam_combo.findData(active)
        if idx >= 0:
            self.cam_combo.setCurrentIndex(idx)
        self.cam_combo.blockSignals(False)

    def _toggle_tracking(self) -> None:
        if self._pipeline and self._pipeline.is_running:
            self._stop_tracking()
        else:
            self._start_tracking()

    def _start_tracking(self) -> None:
        if self._tracker is None:
            self.status_label.setText("Loading hand model…")
            self._tracker = HandTracker(self.settings)
        self._pipeline = Pipeline(
            self.settings, self._tracker, self._classifier, self._dispatcher, self._mode_manager
        )
        self._pipeline.on_frame = self._bridge.frame.emit
        self._pipeline.on_fps = self._bridge.fps.emit
        self._pipeline.on_status = self._bridge.status.emit
        self._pipeline.on_camera_state = self._bridge.camera_state.emit
        if not self._pipeline.start():
            self.status_label.setText("Camera unavailable")
            return
        self._mouse.set_paused(False)
        self.tracking_btn.setText("Stop tracking")

    def _stop_tracking(self) -> None:
        if self._pipeline:
            self._pipeline.stop()
            self._pipeline = None
        self._mouse.set_paused(True)
        self.preview.clear()
        self.preview.setText("Camera preview\n(off)")
        self.fps_label.setText("FPS: —")
        self.tracking_btn.setText("Start tracking")

    # ----- advanced -----

    def _open_advanced(self) -> None:
        dlg = AdvancedDialog(self.settings, self)
        dlg.exec_()

    # ----- system tray + close -----

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event) -> None:
        # Minimize to tray rather than quit; user uses tray menu to actually quit.
        if self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self._quit()

    def _quit(self) -> None:
        self._stop_tracking()
        self.settings.save()
        self.tray.hide()
        from PyQt5.QtWidgets import QApplication

        QApplication.instance().quit()
