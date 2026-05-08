"""Advanced settings dialog — opt-in for power users.

Holds the noisy knobs that don't belong in the 5-control main panel:
    - camera resolution + frame skip (manual override of adaptive logic)
    - low-light enhancement (CLAHE clip, brightness, contrast)
    - hand-tracking confidence thresholds + model complexity
    - cursor edge-boost + axis inversion
    - reset-to-defaults

The main panel is what 90% of users will ever see. Anything here should
require a deliberate "I know what I'm doing" click.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings


class AdvancedDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Airpoint — Advanced settings")
        self.resize(520, 480)

        layout = QVBoxLayout(self)

        warning = QLabel(
            "These settings let you fine-tune Airpoint for unusual hardware or "
            "edge cases. Defaults are tuned for most users — change with care."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#fbbf24; font-size:11px;")
        layout.addWidget(warning)

        tabs = QTabWidget()
        tabs.addTab(self._camera_tab(), "Camera")
        tabs.addTab(self._tracking_tab(), "Hand tracking")
        tabs.addTab(self._cursor_tab(), "Cursor")
        layout.addWidget(tabs)

        bottom = QHBoxLayout()
        reset_btn = QPushButton("Reset to defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        bottom.addWidget(reset_btn)
        bottom.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept)
        bottom.addWidget(bb)
        layout.addLayout(bottom)

    # ----- tabs -----

    def _camera_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)

        # Resolution
        self.res_combo = QComboBox()
        for label, w_h in (
            ("480 × 360", (480, 360)),
            ("640 × 480", (640, 480)),
            ("1280 × 720", (1280, 720)),
            ("1920 × 1080", (1920, 1080)),
        ):
            self.res_combo.addItem(label, w_h)
        cur_res = tuple(self.settings.get("camera.resolution", [1280, 720]))
        for i in range(self.res_combo.count()):
            if self.res_combo.itemData(i) == cur_res:
                self.res_combo.setCurrentIndex(i)
                break
        self.res_combo.currentIndexChanged.connect(self._on_res_change)
        f.addRow("Resolution", self.res_combo)

        # Frame skip
        self.skip = self._slider(
            "camera.frame_skip", 1, 6, default=2,
            tip="Higher skip = lower CPU. Adaptive frame skipping will adjust this automatically.",
        )
        f.addRow("Frame skip", self.skip)

        # Auto exposure / low light / wide angle
        self.auto_exp = QCheckBox()
        self.auto_exp.setChecked(bool(self.settings.get("camera.auto_exposure", True)))
        self.auto_exp.toggled.connect(lambda v: self.settings.set("camera.auto_exposure", bool(v)))
        f.addRow("Auto exposure", self.auto_exp)

        self.low_light = QCheckBox()
        self.low_light.setChecked(bool(self.settings.get("camera.low_light_mode", True)))
        self.low_light.toggled.connect(
            lambda v: self.settings.set("camera.low_light_mode", bool(v))
        )
        f.addRow("Low-light enhancement", self.low_light)

        self.wide_angle = QCheckBox()
        self.wide_angle.setChecked(
            bool(self.settings.get("camera.wide_angle_correction", False))
        )
        self.wide_angle.toggled.connect(
            lambda v: self.settings.set("camera.wide_angle_correction", bool(v))
        )
        f.addRow("Wide-angle (GoPro) correction", self.wide_angle)

        return w

    def _tracking_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)

        self.det_conf = self._slider(
            "hand_tracking.min_detection_confidence", 30, 90, default=60, scale=100,
            tip="Higher = fewer false positives but more dropouts.",
        )
        f.addRow("Detection confidence", self.det_conf)

        self.trk_conf = self._slider(
            "hand_tracking.min_tracking_confidence", 30, 90, default=60, scale=100,
            tip="Higher = smoother but more dropouts.",
        )
        f.addRow("Tracking confidence", self.trk_conf)

        self.model = QComboBox()
        self.model.addItem("Fast (low CPU)", 0)
        self.model.addItem("Accurate (more CPU)", 1)
        active = int(self.settings.get("hand_tracking.model_complexity", 0))
        self.model.setCurrentIndex(0 if active == 0 else 1)
        self.model.currentIndexChanged.connect(
            lambda _i: self.settings.set("hand_tracking.model_complexity", self.model.currentData())
        )
        f.addRow("Model complexity", self.model)

        self.max_hands = QComboBox()
        self.max_hands.addItem("1 (recommended)", 1)
        self.max_hands.addItem("2", 2)
        active = int(self.settings.get("hand_tracking.max_num_hands", 1))
        self.max_hands.setCurrentIndex(0 if active == 1 else 1)
        self.max_hands.currentIndexChanged.connect(
            lambda _i: self.settings.set("hand_tracking.max_num_hands", self.max_hands.currentData())
        )
        f.addRow("Max hands tracked", self.max_hands)

        return w

    def _cursor_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)

        self.deadzone = self._slider(
            "cursor.deadzone", 0, 10, default=2, scale=100,
            tip="Cursor ignores movements smaller than this.",
        )
        f.addRow("Deadzone", self.deadzone)

        self.invert_x = QCheckBox()
        self.invert_x.setChecked(bool(self.settings.get("cursor.invert_x", False)))
        self.invert_x.toggled.connect(lambda v: self.settings.set("cursor.invert_x", bool(v)))
        f.addRow("Invert X axis", self.invert_x)

        self.invert_y = QCheckBox()
        self.invert_y.setChecked(bool(self.settings.get("cursor.invert_y", True)))
        self.invert_y.toggled.connect(lambda v: self.settings.set("cursor.invert_y", bool(v)))
        f.addRow("Invert Y axis", self.invert_y)

        self.edge_boost = QCheckBox()
        self.edge_boost.setChecked(bool(self.settings.get("cursor.edge_boost", True)))
        self.edge_boost.toggled.connect(
            lambda v: self.settings.set("cursor.edge_boost", bool(v))
        )
        f.addRow("Edge boost (reach corners)", self.edge_boost)

        self.edge_factor = self._slider(
            "cursor.edge_boost_factor", 10, 50, default=20, scale=10,
            tip="How aggressively to amplify edge motion. 2.0× is a good default.",
        )
        f.addRow("Edge boost factor", self.edge_factor)

        return w

    # ----- helpers -----

    def _slider(self, key: str, lo: int, hi: int, default: int, scale: int = 1, tip: str = "") -> QSlider:
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        cur = self.settings.get(key, default / scale if scale > 1 else default)
        try:
            s.setValue(int(round(float(cur) * scale)) if scale > 1 else int(cur))
        except (TypeError, ValueError):
            s.setValue(default)
        if tip:
            s.setToolTip(tip)

        def _on_change(v: int) -> None:
            value = v / scale if scale > 1 else v
            self.settings.set(key, value)

        s.valueChanged.connect(_on_change)
        return s

    def _on_res_change(self, _i: int) -> None:
        wh = self.res_combo.currentData()
        if wh:
            self.settings.set("camera.resolution", list(wh))

    def _reset_defaults(self) -> None:
        # Erase the file and let Settings recreate it from scratch on next load.
        from pathlib import Path

        path = Path(self.settings._path)  # noqa: SLF001 - intentional reset
        if path.exists():
            path.unlink()
        self.settings.load()
        self.accept()  # close — user reopens to see refreshed values
