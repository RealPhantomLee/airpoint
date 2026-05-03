"""Configuration loader for Airpoint."""

import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent / "settings.json"


class Settings:
    """Manages application settings with hot-reload support."""

    def __init__(self, config_path: str | None = None):
        self._path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config = {}
        self.load()

    def load(self) -> dict:
        """Load settings from JSON file."""
        try:
            with open(self._path, "r") as f:
                self._config = json.load(f)
            return self._config
        except FileNotFoundError:
            self._config = self._create_default()
            return self._config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid settings.json: {e}")

    def save(self):
        """Save current settings to JSON file."""
        with open(self._path, "w") as f:
            json.dump(self._config, f, indent=2)

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

    def set(self, key: str, value):
        """Set a setting using dot notation."""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self.save()

    def as_dict(self) -> dict:
        """Return full config as dict."""
        return self._config.copy()

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
