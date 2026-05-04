"""Configuration loader for Airpoint."""

import json
import threading
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent / "settings.json"


class Settings:
    """Manages application settings with deferred saves and input validation."""

    def __init__(self, config_path: str | None = None):
        self._path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config = {}
        self._save_timer: threading.Timer | None = None
        self.load()

    def load(self) -> dict:
        """Load settings from JSON file and validate values."""
        try:
            with open(self._path, "r") as f:
                self._config = json.load(f)
            self._validate()
            return self._config
        except FileNotFoundError:
            self._config = self._create_default()
            return self._config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid settings.json: {e}")

    def save(self):
        """Flush any pending deferred save and write to disk immediately."""
        if self._save_timer:
            self._save_timer.cancel()
            self._save_timer = None
        with open(self._path, "w") as f:
            json.dump(self._config, f, indent=2)

    def save_deferred(self, delay: float = 0.5):
        """Schedule a save after delay seconds, cancelling any pending save."""
        if self._save_timer:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(delay, self.save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def get(self, key: str, default=None):
        """Get a setting using dot notation (e.g., 'camera.fps')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set_quiet(self, key: str, value):
        """Update a setting in memory without triggering a save."""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def set(self, key: str, value):
        """Update a setting in memory and schedule a deferred disk write."""
        self.set_quiet(key, value)
        self.save_deferred()

    def as_dict(self) -> dict:
        """Return full config as dict."""
        return self._config.copy()

    def _validate(self):
        """Clamp all known settings to safe ranges after loading."""
        def clamp(key, default, lo, hi, cast=float):
            v = self.get(key, default)
            try:
                self.set_quiet(key, max(lo, min(cast(v), hi)))
            except (TypeError, ValueError):
                self.set_quiet(key, default)

        clamp("camera.device_index", 0, 0, 9, int)
        clamp("camera.fps", 30, 1, 120, int)
        clamp("camera.frame_skip", 2, 1, 10, int)
        clamp("hand_tracking.max_num_hands", 2, 1, 2, int)
        clamp("hand_tracking.min_detection_confidence", 0.6, 0.1, 1.0)
        clamp("hand_tracking.min_tracking_confidence", 0.5, 0.1, 1.0)
        clamp("cursor.sensitivity", 1.5, 0.1, 5.0)
        clamp("cursor.smoothing_alpha", 0.3, 0.05, 0.99)
        clamp("cursor.deadzone", 0.02, 0.0, 0.5)
        clamp("gestures.pinch_threshold", 0.04, 0.01, 0.2)
        clamp("gestures.scroll_threshold", 0.015, 0.005, 0.1)
        clamp("gestures.click_debounce_ms", 200, 50, 1000, int)

        res = self.get("camera.resolution", [1280, 720])
        if not isinstance(res, list) or len(res) != 2:
            self.set_quiet("camera.resolution", [1280, 720])
        else:
            try:
                self.set_quiet("camera.resolution", [
                    max(160, min(int(res[0]), 3840)),
                    max(120, min(int(res[1]), 2160)),
                ])
            except (TypeError, ValueError):
                self.set_quiet("camera.resolution", [1280, 720])

    def _create_default(self) -> dict:
        """Create default config if file missing."""
        default = {
            "camera": {"device_index": 0, "resolution": [640, 480], "fps": 30},
            "hand_tracking": {
                "max_num_hands": 2,
                "model_complexity": 0,
                "min_detection_confidence": 0.6,
                "min_tracking_confidence": 0.5,
            },
            "cursor": {
                "sensitivity": 1.5,
                "smoothing_alpha": 0.3,
                "moving_average_window": 5,
            },
            "gestures": {
                "pinch_threshold": 0.05,
                "scroll_threshold": 0.02,
                "click_debounce_ms": 200,
            },
            "gui": {
                "window_title": "Airpoint - Touchless Cursor Control",
                "preview_width": 640,
                "preview_height": 480,
            },
            "privacy": {"no_data_storage": True, "no_network_calls": True},
        }
        self._config = default
        self.save()
        return default
