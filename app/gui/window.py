"""PyQt5 GUI window for Airpoint."""

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QCheckBox,
    QGroupBox,
)


class CameraThread(QThread):
    """Background thread for camera capture and CV processing."""

    frame_ready = pyqtSignal(np.ndarray)
    gestures_ready = pyqtSignal(dict)
    fps_updated = pyqtSignal(float)
    status_message = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.running = False
        self.cap = None
        self.tracker = None
        self.engine = None
        self._frame_skip_counter = 0

    def run(self):
        self.running = True

        from app.vision.hand_tracker import HandTracker
        from app.vision.gesture_engine import GestureEngine
        from app.utils.fps import FPSCounter

        device = self.settings.get("camera.device_index", 0)
        width, height = self.settings.get("camera.resolution", [1280, 720])
        fps = self.settings.get("camera.fps", 30)
        frame_skip = self.settings.get("camera.frame_skip", 2)

        self.cap = cv2.VideoCapture(device)
        if not self.cap.isOpened():
            self.status_message.emit("Camera not found. Check device index.")
            self.frame_ready.emit(np.zeros((height, width, 3), dtype=np.uint8))
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.status_message.emit(f"Camera ready ({actual_w}x{actual_h})")

        self.tracker = HandTracker(self.settings)
        self.engine = GestureEngine(self.settings)
        fps_counter = FPSCounter()

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            self._frame_skip_counter += 1
            if self._frame_skip_counter % frame_skip != 0:
                self.frame_ready.emit(frame)
                fps_counter.tick()
                self.fps_updated.emit(fps_counter.fps)
                continue

            annotated, hand_results = self.tracker.process_frame(frame)
            fps_counter.tick()

            self.frame_ready.emit(annotated)

            if self.engine:
                gestures = self.engine.detect_gestures(hand_results)
                self.gestures_ready.emit(gestures)

            self.fps_updated.emit(fps_counter.fps)

        if self.cap:
            self.cap.release()
        if self.tracker:
            self.tracker.close()

    def stop(self):
        self.running = False
        self.wait()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, settings, mouse_controller):
        super().__init__()
        self.settings = settings
        self.mouse_controller = mouse_controller
        self.camera_thread = None
        self._is_running = False
        self._was_dragging = False

        self._setup_ui()
        self._setup_timer()
        self._apply_theme()

        title = self.settings.get("gui.window_title", "Airpoint")
        self.setWindowTitle(title)
        self.setMinimumSize(960, 700)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left: Camera preview
        preview_group = QGroupBox("Camera Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(960, 540)
        self.preview_label.setStyleSheet("background-color: #2a2a2a;")
        preview_layout.addWidget(self.preview_label)

        # Status bar
        status_bar = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_bar.addWidget(self.fps_label)

        self.camera_status = QLabel("")
        self.camera_status.setStyleSheet("color: #888; font-size: 12px;")
        status_bar.addWidget(self.camera_status)

        self.gesture_label = QLabel("Gesture: --")
        self.gesture_label.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")
        status_bar.addWidget(self.gesture_label)

        status_bar.addStretch()
        preview_layout.addLayout(status_bar)

        main_layout.addWidget(preview_group, stretch=3)

        # Right: Controls
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout(control_group)

        # Start/Stop
        self.start_btn = QPushButton("Start Tracking")
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 14px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.start_btn.clicked.connect(self._toggle_tracking)
        control_layout.addWidget(self.start_btn)

        # Sensitivity
        self._add_slider(control_layout, "Sensitivity:", 1, 30, 15, self._on_sensitivity_changed)

        # Smoothing
        self._add_slider(control_layout, "Smoothing:", 1, 9, 3, self._on_smoothing_changed)

        # Gestures
        gestures_group = QGroupBox("Gestures")
        gestures_layout = QVBoxLayout(gestures_group)

        self.click_checkbox = QCheckBox("Pinch to Click")
        self.click_checkbox.setChecked(True)
        gestures_layout.addWidget(self.click_checkbox)

        self.right_click_checkbox = QCheckBox("Thumb+Middle = Right Click")
        self.right_click_checkbox.setChecked(True)
        gestures_layout.addWidget(self.right_click_checkbox)

        self.scroll_checkbox = QCheckBox("Two-Finger Scroll")
        self.scroll_checkbox.setChecked(True)
        gestures_layout.addWidget(self.scroll_checkbox)

        self.drag_checkbox = QCheckBox("Fist to Drag")
        self.drag_checkbox.setChecked(True)
        gestures_layout.addWidget(self.drag_checkbox)

        control_layout.addWidget(gestures_group)

        # Privacy
        privacy_group = QGroupBox("Privacy")
        privacy_layout = QVBoxLayout(privacy_group)

        self.camera_idle_checkbox = QCheckBox("Camera OFF when idle")
        self.camera_idle_checkbox.setChecked(self.settings.get("gui.camera_off_idle", False))
        privacy_layout.addWidget(self.camera_idle_checkbox)

        control_layout.addWidget(privacy_group)

        # Status
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        control_layout.addWidget(self.status_label)

        control_layout.addStretch()
        main_layout.addWidget(control_group, stretch=1)

    def _add_slider(self, layout, label, min_val, max_val, default, callback):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.valueChanged.connect(callback)
        row.addWidget(slider)
        val_label = QLabel(str(default))
        row.addWidget(val_label)
        layout.addLayout(row)
        return slider, val_label

    def _setup_timer(self):
        self.idle_timer = QTimer()
        self.idle_timer.setInterval(1000)
        self.idle_timer.timeout.connect(self._check_idle)
        self._last_activity = 0

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #ffffff; }
            QGroupBox { font-weight: bold; border: 1px solid #555555; border-radius: 4px; margin-top: 6px; padding-top: 10px; color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QLabel { color: #ffffff; }
            QCheckBox { color: #ffffff; }
            QSlider::groove:horizontal { border: 1px solid #555555; height: 4px; background: #555555; border-radius: 2px; }
            QSlider::handle:horizontal { background: #4CAF50; width: 16px; margin: -6px 0; border-radius: 8px; }
        """)

    def _toggle_tracking(self):
        if not self._is_running:
            self._start_tracking()
        else:
            self._stop_tracking()

    def _start_tracking(self):
        self.camera_thread = CameraThread(self.settings)
        self.camera_thread.frame_ready.connect(self._update_preview)
        self.camera_thread.gestures_ready.connect(self._apply_gestures)
        self.camera_thread.fps_updated.connect(self._update_fps)
        self.camera_thread.status_message.connect(self._on_camera_status)
        self.camera_thread.start()

        self._is_running = True
        self.start_btn.setText("Stop Tracking")
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #f44336; color: white; padding: 10px; font-size: 14px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #da190b; }
        """)
        self.status_label.setText("Status: Running")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.mouse_controller.set_paused(False)
        self.idle_timer.start()

    def _stop_tracking(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None

        self._is_running = False
        self._was_dragging = False
        self.mouse_controller.drag_end()

        self.start_btn.setText("Start Tracking")
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 14px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.fps_label.setText("FPS: --")
        self.mouse_controller.set_paused(True)
        self.idle_timer.stop()

    def _update_preview(self, frame):
        if frame is None or frame.size == 0:
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        qt_image = QImage(rgb.tobytes(), w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)

        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def _apply_gestures(self, gestures):
        self._last_activity = 300

        if gestures.get("move"):
            self.mouse_controller.move_cursor(*gestures["move"])

        if gestures.get("click") and self.click_checkbox.isChecked():
            self.mouse_controller.click()
            self.gesture_label.setText("Gesture: Click")

        if gestures.get("double_click"):
            self.mouse_controller.double_click()
            self.gesture_label.setText("Gesture: Double Click")

        if gestures.get("right_click") and self.right_click_checkbox.isChecked():
            self.mouse_controller.right_click()
            self.gesture_label.setText("Gesture: Right Click")

        if gestures.get("middle_click"):
            self.mouse_controller.middle_click()
            self.gesture_label.setText("Gesture: Middle Click")

        if self.scroll_checkbox.isChecked():
            if gestures.get("scroll_up"):
                self.mouse_controller.scroll("up")
                self.gesture_label.setText("Gesture: Scroll Up")
            elif gestures.get("scroll_down"):
                self.mouse_controller.scroll("down")
                self.gesture_label.setText("Gesture: Scroll Down")
            if gestures.get("scroll_left"):
                self.mouse_controller.scroll("left")
                self.gesture_label.setText("Gesture: Scroll Left")
            elif gestures.get("scroll_right"):
                self.mouse_controller.scroll("right")
                self.gesture_label.setText("Gesture: Scroll Right")

        if gestures.get("drag") and self.drag_checkbox.isChecked():
            if not self._was_dragging:
                self.mouse_controller.drag_start()
                self._was_dragging = True
                self.gesture_label.setText("Gesture: Drag")
        else:
            if self._was_dragging:
                self.mouse_controller.drag_end()
                self._was_dragging = False

        if gestures.get("pause"):
            self.gesture_label.setText("Gesture: PAUSED")

        if gestures.get("shortcut"):
            self.gesture_label.setText("Gesture: Two-Hand Shortcut")

    def _update_fps(self, fps):
        self.fps_label.setText(f"FPS: {fps:.1f}")

    def _on_camera_status(self, message):
        self.camera_status.setText(message)

    def _on_sensitivity_changed(self, value):
        sensitivity = value / 10.0
        self.mouse_controller.update_sensitivity(sensitivity)
        self.settings.set("cursor.sensitivity", sensitivity)

    def _on_smoothing_changed(self, value):
        alpha = value / 10.0
        self.mouse_controller.smoother.update_params(alpha=alpha)
        self.settings.set("cursor.smoothing_alpha", alpha)

    def _check_idle(self):
        if not self._is_running:
            return
        if self.camera_idle_checkbox.isChecked():
            self._last_activity -= 1
            if self._last_activity <= 0:
                self._stop_tracking()

    def closeEvent(self, event):
        if self._is_running:
            self._stop_tracking()
        self.mouse_controller.set_paused(True)
        event.accept()
