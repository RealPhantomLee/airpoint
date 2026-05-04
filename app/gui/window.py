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
    QTabWidget,
    QScrollArea,
    QComboBox,
    QMessageBox,
    QSpinBox,
)


class CameraThread(QThread):
    """Background thread for camera capture and CV processing."""

    frame_ready = pyqtSignal(np.ndarray)
    gestures_ready = pyqtSignal(dict)
    fps_updated = pyqtSignal(float)
    status_message = pyqtSignal(str)

    _PREVIEW_W = 960
    _PREVIEW_H = 540

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
                self.frame_ready.emit(self._resize_for_preview(frame))
                fps_counter.tick()
                self.fps_updated.emit(fps_counter.fps)
                continue

            annotated, hand_results = self.tracker.process_frame(frame)
            fps_counter.tick()

            self.frame_ready.emit(self._resize_for_preview(annotated))

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

    def _resize_for_preview(self, frame: np.ndarray) -> np.ndarray:
        if frame.shape[1] > self._PREVIEW_W or frame.shape[0] > self._PREVIEW_H:
            return cv2.resize(frame, (self._PREVIEW_W, self._PREVIEW_H), interpolation=cv2.INTER_LINEAR)
        return frame


class MainWindow(QMainWindow):
    """Main application window — tabbed control center."""

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
        self.setMinimumSize(1200, 800)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ===== LEFT: Camera preview =====
        preview_group = QGroupBox("Camera Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(960, 540)
        self.preview_label.setStyleSheet("background-color: #2a2a2a;")
        preview_layout.addWidget(self.preview_label)

        status_bar = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
        status_bar.addWidget(self.fps_label)

        self.camera_status = QLabel("")
        self.camera_status.setStyleSheet("color: #888; font-size: 12px;")
        status_bar.addWidget(self.camera_status)

        self.gesture_label = QLabel("Gesture: --")
        self.gesture_label.setStyleSheet("color: #FFD700; font-size: 13px; font-weight: bold;")
        status_bar.addWidget(self.gesture_label)

        status_bar.addStretch()
        preview_layout.addLayout(status_bar)

        main_layout.addWidget(preview_group, stretch=3)

        # ===== RIGHT: Tabbed control panel =====
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)

        self._build_gestures_tab()
        self._build_cursor_tab()
        self._build_camera_tab()
        self._build_settings_tab()

        right_panel = QVBoxLayout()

        # Start/Stop button at top
        self.start_btn = QPushButton("Start Tracking")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; padding: 12px;
                font-size: 16px; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.start_btn.clicked.connect(self._toggle_tracking)
        right_panel.addWidget(self.start_btn)

        right_panel.addWidget(self.tab_widget)

        # Status at bottom
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_panel.addWidget(self.status_label)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        main_layout.addWidget(right_widget, stretch=1)

    def _build_gestures_tab(self):
        """Gestures tab — every gesture gets a toggle."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(4)

        # Movement
        self._add_section_label(layout, "MOVEMENT")
        self.g_move = QCheckBox("☝️  Point — Move cursor")
        self.g_move.setChecked(True)
        self.g_move.setToolTip("Raise index finger to control the mouse cursor")
        layout.addWidget(self.g_move)

        # Clicking
        self._add_section_label(layout, "CLICKING")
        self.g_click = QCheckBox("👌  Thumb+Index Pinch — Left click")
        self.g_click.setChecked(True)
        self.g_click.setToolTip("Touch thumb tip to index fingertip")
        layout.addWidget(self.g_click)

        self.g_double_click = QCheckBox("⚡  Double Pinch — Double click")
        self.g_double_click.setChecked(True)
        self.g_double_click.setToolTip("Pinch twice quickly (within 400ms)")
        layout.addWidget(self.g_double_click)

        self.g_right_click = QCheckBox("🤏  Thumb+Middle Pinch — Right click")
        self.g_right_click.setChecked(True)
        self.g_right_click.setToolTip("Touch thumb tip to middle fingertip")
        layout.addWidget(self.g_right_click)

        self.g_middle_click = QCheckBox("🤌  Thumb+Ring Pinch — Middle click")
        self.g_middle_click.setChecked(True)
        self.g_middle_click.setToolTip("Touch thumb tip to ring fingertip")
        layout.addWidget(self.g_middle_click)

        # Scrolling
        self._add_section_label(layout, "SCROLLING")
        self.g_scroll_vert = QCheckBox("✌️  Two-Finger Up/Down — Vertical scroll")
        self.g_scroll_vert.setChecked(True)
        self.g_scroll_vert.setToolTip("Index + middle finger up, move hand up or down")
        layout.addWidget(self.g_scroll_vert)

        self.g_scroll_horiz = QCheckBox("↔️  Two-Finger Spread — Horizontal scroll")
        self.g_scroll_horiz.setChecked(True)
        self.g_scroll_horiz.setToolTip("Spread index and middle fingers apart horizontally")
        layout.addWidget(self.g_scroll_horiz)

        # Dragging
        self._add_section_label(layout, "DRAGGING")
        self.g_drag = QCheckBox("✊  Closed Fist — Drag mode")
        self.g_drag.setChecked(True)
        self.g_drag.setToolTip("Close fist to hold left click, open to release")
        layout.addWidget(self.g_drag)

        # System
        self._add_section_label(layout, "SYSTEM")
        self.g_pause = QCheckBox("🖐️  Open Palm Hold — Pause tracking")
        self.g_pause.setChecked(True)
        self.g_pause.setToolTip("Hold all fingers extended for 1 second")
        layout.addWidget(self.g_pause)

        self.g_volume = QCheckBox("👍  Thumb Wave — Volume control")
        self.g_volume.setChecked(False)
        self.g_volume.setToolTip("Thumb + index up, wave right (up) or left (down)")
        layout.addWidget(self.g_volume)

        self.g_shortcut = QCheckBox("🙌  Two Hands — Shortcut mode")
        self.g_shortcut.setChecked(True)
        self.g_shortcut.setToolTip("Show both hands simultaneously")
        layout.addWidget(self.g_shortcut)

        layout.addStretch()
        scroll.setWidget(content)

        self.tab_widget.addTab(scroll, "Gestures")

    def _build_cursor_tab(self):
        """Cursor settings tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)

        self._add_section_label(layout, "SPEED")
        self._slider_row(layout, "Sensitivity:", 1, 30, 15, self._on_sensitivity_changed, display_div=10.0)

        self._slider_row(layout, "Smoothing:", 1, 9, 3, self._on_smoothing_changed, display_div=10.0)

        self._slider_row(layout, "Deadzone:", 1, 10, 2, self._on_deadzone_changed, display_div=100.0)

        self._add_section_label(layout, "EDGE REACH")
        self.edge_boost_checkbox = QCheckBox("Enable edge boost")
        self.edge_boost_checkbox.setChecked(self.settings.get("cursor.edge_boost", False))
        self.edge_boost_checkbox.stateChanged.connect(self._on_edge_boost_changed)
        layout.addWidget(self.edge_boost_checkbox)

        self.edge_boost_label = QLabel("Edge boost: 2.0x")
        layout.addWidget(self.edge_boost_label)
        self.edge_boost_slider = QSlider(Qt.Horizontal)
        self.edge_boost_slider.setMinimum(10)
        self.edge_boost_slider.setMaximum(50)
        self.edge_boost_slider.setValue(int(self.settings.get("cursor.edge_boost_factor", 2.0) * 10))
        self.edge_boost_slider.valueChanged.connect(self._on_edge_boost_slider)
        layout.addWidget(self.edge_boost_slider)

        self._add_section_label(layout, "AXIS INVERSION")
        self.invert_x_checkbox = QCheckBox("Invert X axis")
        self.invert_x_checkbox.setChecked(self.settings.get("cursor.invert_x", False))
        self.invert_x_checkbox.stateChanged.connect(self._on_invert_x_changed)
        layout.addWidget(self.invert_x_checkbox)

        self.invert_y_checkbox = QCheckBox("Invert Y axis")
        self.invert_y_checkbox.setChecked(self.settings.get("cursor.invert_y", False))
        self.invert_y_checkbox.stateChanged.connect(self._on_invert_y_changed)
        layout.addWidget(self.invert_y_checkbox)

        layout.addStretch()
        scroll.setWidget(content)

        self.tab_widget.addTab(scroll, "Cursor")

    def _build_camera_tab(self):
        """Camera settings tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)

        self._add_section_label(layout, "DEVICE")
        self._slider_row(layout, "Device Index:", 0, 4, 0, self._on_device_changed)

        res_combo = QHBoxLayout()
        res_combo.addWidget(QLabel("Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["480x360", "640x480", "1280x720", "1920x1080"])
        current_res = self.settings.get("camera.resolution", [1280, 720])
        res_str = f"{current_res[0]}x{current_res[1]}"
        idx = self.res_combo.findText(res_str)
        if idx >= 0:
            self.res_combo.setCurrentIndex(idx)
        self.res_combo.currentTextChanged.connect(self._on_resolution_changed)
        res_combo.addWidget(self.res_combo)
        layout.addLayout(res_combo)

        self._slider_row(layout, "Frame Skip:", 1, 6, 2, self._on_frame_skip_changed)

        self._add_section_label(layout, "LOW LIGHT")
        self.low_light_checkbox = QCheckBox("Low light mode (CLAHE enhancement)")
        self.low_light_checkbox.setChecked(self.settings.get("camera.low_light_mode", False))
        self.low_light_checkbox.stateChanged.connect(self._on_low_light_changed)
        layout.addWidget(self.low_light_checkbox)

        self._slider_row(layout, "Brightness Boost:", 0, 50, 15, self._on_brightness_changed)

        self._slider_row(layout, "Contrast Boost:", 10, 20, 12, self._on_contrast_changed, display_div=10.0)

        self._slider_row(layout, "CLAHE Clip Limit:", 10, 40, 20, self._on_clahe_changed, display_div=10.0)

        self.auto_exposure_checkbox = QCheckBox("Auto exposure compensation")
        self.auto_exposure_checkbox.setChecked(self.settings.get("camera.auto_exposure", True))
        self.auto_exposure_checkbox.stateChanged.connect(self._on_auto_exposure_changed)
        layout.addWidget(self.auto_exposure_checkbox)

        self._add_section_label(layout, "HAND TRACKING")
        self._slider_row(layout, "Detection Confidence:", 3, 9, 7, self._on_detect_conf_changed, display_div=10.0)

        self._slider_row(layout, "Tracking Confidence:", 3, 9, 6, self._on_track_conf_changed, display_div=10.0)

        model_combo = QHBoxLayout()
        model_combo.addWidget(QLabel("Model Complexity:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["0 (Fast)", "1 (Accurate)"])
        current_model = self.settings.get("hand_tracking.model_complexity", 1)
        self.model_combo.setCurrentIndex(current_model)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_combo.addWidget(self.model_combo)
        layout.addLayout(model_combo)

        self.wide_angle_checkbox = QCheckBox("GoPro wide-angle correction")
        self.wide_angle_checkbox.setChecked(self.settings.get("camera.wide_angle_correction", True))
        self.wide_angle_checkbox.stateChanged.connect(self._on_wide_angle_changed)
        layout.addWidget(self.wide_angle_checkbox)

        layout.addStretch()
        scroll.setWidget(content)

        self.tab_widget.addTab(scroll, "Camera")

    def _build_settings_tab(self):
        """General settings tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)

        self._add_section_label(layout, "GESTURE TIMING")
        self._slider_row(layout, "Click Debounce (ms):", 100, 500, 200, self._on_debounce_changed)

        self._slider_row(layout, "Double-Click Window (ms):", 200, 600, 400, self._on_double_click_delay_changed)

        self._slider_row(layout, "Gesture Lock (ms):", 100, 1000, 500, self._on_gesture_lock_changed)

        self._add_section_label(layout, "PRIVACY")
        self.camera_idle_checkbox = QCheckBox("Camera OFF when idle (5 min)")
        self.camera_idle_checkbox.setChecked(self.settings.get("gui.camera_off_idle", False))
        layout.addWidget(self.camera_idle_checkbox)

        self._add_section_label(layout, "ABOUT")
        about_text = QLabel(
            "Airpoint v1.0.0\n"
            "Touchless Cursor Control\n"
            "MediaPipe + OpenCV + PyQt5\n\n"
            "Privacy-first: no network calls,\n"
            "no data storage, local-only processing."
        )
        about_text.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(about_text)

        layout.addStretch()
        scroll.setWidget(content)

        self.tab_widget.addTab(scroll, "Settings")

    def _add_section_label(self, layout, text):
        """Add a bold section header."""
        label = QLabel(text)
        label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px; margin-top: 8px;")
        layout.addWidget(label)

    def _slider_row(self, layout, label, min_val, max_val, default, callback, display_div=None):
        """Add a labeled slider with value display."""
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.valueChanged.connect(callback)
        row.addWidget(slider)
        val_label = QLabel(str(default / display_div if display_div else default))
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
            QCheckBox { color: #ffffff; spacing: 6px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QTabWidget::pane { border: 1px solid #555; border-radius: 4px; background: #2a2a2a; }
            QTabBar::tab {
                background: #333; color: #ccc; padding: 8px 16px;
                border: 1px solid #555; border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: #4CAF50; color: white; }
            QTabBar::tab:hover { background: #555; }
            QSlider::groove:horizontal { border: 1px solid #555555; height: 4px; background: #555555; border-radius: 2px; }
            QSlider::handle:horizontal { background: #4CAF50; width: 16px; margin: -6px 0; border-radius: 8px; }
            QComboBox { background: #333; color: white; border: 1px solid #555; padding: 4px; border-radius: 3px; }
            QComboBox::drop-down { border: none; }
            QScrollArea { border: none; background: #2a2a2a; }
            QPushButton {
                background-color: #4CAF50; color: white; padding: 10px;
                font-size: 14px; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
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
            QPushButton {
                background-color: #f44336; color: white; padding: 12px;
                font-size: 16px; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        self.status_label.setText("Status: Running")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px;")
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
            QPushButton {
                background-color: #4CAF50; color: white; padding: 12px;
                font-size: 16px; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 13px;")
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
                Qt.FastTransformation,
            )
        )

    def _apply_gestures(self, gestures):
        self._last_activity = 300

        if gestures.get("move") and self.g_move.isChecked():
            self.mouse_controller.move_cursor(*gestures["move"])

        if gestures.get("click") and self.g_click.isChecked():
            self.mouse_controller.click()
            self.gesture_label.setText("Gesture: 👌 Left Click")

        if gestures.get("double_click") and self.g_double_click.isChecked():
            self.mouse_controller.double_click()
            self.gesture_label.setText("Gesture: ⚡ Double Click")

        if gestures.get("right_click") and self.g_right_click.isChecked():
            self.mouse_controller.right_click()
            self.gesture_label.setText("Gesture: 🤏 Right Click")

        if gestures.get("middle_click") and self.g_middle_click.isChecked():
            self.mouse_controller.middle_click()
            self.gesture_label.setText("Gesture: 🤌 Middle Click")

        if self.g_scroll_vert.isChecked():
            if gestures.get("scroll_up"):
                self.mouse_controller.scroll("up")
                self.gesture_label.setText("Gesture: ✌️ Scroll Up")
            elif gestures.get("scroll_down"):
                self.mouse_controller.scroll("down")
                self.gesture_label.setText("Gesture: ✌️ Scroll Down")

        if self.g_scroll_horiz.isChecked():
            if gestures.get("scroll_left"):
                self.mouse_controller.scroll("left")
                self.gesture_label.setText("Gesture: ↔️ Scroll Left")
            elif gestures.get("scroll_right"):
                self.mouse_controller.scroll("right")
                self.gesture_label.setText("Gesture: ↔️ Scroll Right")

        if gestures.get("drag") and self.g_drag.isChecked():
            if not self._was_dragging:
                self.mouse_controller.drag_start()
                self._was_dragging = True
                self.gesture_label.setText("Gesture: ✊ Drag")
        else:
            if self._was_dragging:
                self.mouse_controller.drag_end()
                self._was_dragging = False

        if gestures.get("pause") and self.g_pause.isChecked():
            self.gesture_label.setText("Gesture: 🖐️ PAUSED")

        if gestures.get("shortcut") and self.g_shortcut.isChecked():
            self.gesture_label.setText("Gesture: 🙌 Two-Hand Shortcut")

        if gestures.get("volume_up") and self.g_volume.isChecked():
            self.gesture_label.setText("Gesture: 👍 Volume Up")

        if gestures.get("volume_down") and self.g_volume.isChecked():
            self.gesture_label.setText("Gesture: 👈 Volume Down")

    def _update_fps(self, fps):
        self.fps_label.setText(f"FPS: {fps:.1f}")

    def _on_camera_status(self, message):
        self.camera_status.setText(message)

    # ===== Gesture callbacks — save to settings =====

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

    def _on_sensitivity_changed(self, value):
        sensitivity = value / 10.0
        self.mouse_controller.update_sensitivity(sensitivity)
        self.settings.set("cursor.sensitivity", sensitivity)

    def _on_smoothing_changed(self, value):
        alpha = value / 10.0
        self.mouse_controller.smoother.update_params(alpha=alpha)
        self.settings.set("cursor.smoothing_alpha", alpha)

    def _on_deadzone_changed(self, value):
        dz = value / 100.0
        self.mouse_controller.smoother.update_params()
        self.mouse_controller.smoother.deadzone = dz
        self.settings.set("cursor.deadzone", dz)

    def _on_edge_boost_changed(self, state):
        enabled = state == Qt.Checked
        self.settings.set("cursor.edge_boost", enabled)

    def _on_edge_boost_slider(self, value):
        factor = value / 10.0
        self.edge_boost_label.setText(f"Edge boost: {factor:.1f}x")
        self.settings.set("cursor.edge_boost_factor", factor)

    def _on_invert_x_changed(self, state):
        self.mouse_controller.invert_x = state == Qt.Checked
        self.settings.set("cursor.invert_x", state == Qt.Checked)

    def _on_invert_y_changed(self, state):
        self.mouse_controller.invert_y = state == Qt.Checked
        self.settings.set("cursor.invert_y", state == Qt.Checked)

    def _on_device_changed(self, value):
        self.settings.set("camera.device_index", value)

    def _on_resolution_changed(self, text):
        w, h = map(int, text.split("x"))
        self.settings.set("camera.resolution", [w, h])

    def _on_frame_skip_changed(self, value):
        self.settings.set("camera.frame_skip", value)

    def _on_low_light_changed(self, state):
        self.settings.set("camera.low_light_mode", state == Qt.Checked)

    def _on_brightness_changed(self, value):
        self.settings.set("camera.brightness_boost", value)

    def _on_contrast_changed(self, value):
        self.settings.set("camera.contrast_boost", value / 10.0)

    def _on_clahe_changed(self, value):
        self.settings.set("camera.clahe_clip_limit", value / 10.0)

    def _on_auto_exposure_changed(self, state):
        self.settings.set("camera.auto_exposure", state == Qt.Checked)

    def _on_detect_conf_changed(self, value):
        self.settings.set("hand_tracking.min_detection_confidence", value / 10.0)

    def _on_track_conf_changed(self, value):
        self.settings.set("hand_tracking.min_tracking_confidence", value / 10.0)

    def _on_model_changed(self, index):
        self.settings.set("hand_tracking.model_complexity", index)

    def _on_wide_angle_changed(self, state):
        self.settings.set("camera.wide_angle_correction", state == Qt.Checked)

    def _on_debounce_changed(self, value):
        self.settings.set("gestures.click_debounce_ms", value)

    def _on_double_click_delay_changed(self, value):
        self.settings.set("gestures.double_click_delay_ms", value)

    def _on_gesture_lock_changed(self, value):
        self.settings.set("gestures.gesture_lock_ms", value)
