"""Interaction modes.

Each mode bundles:
    - a name string
    - a threshold profile (pinch/scroll/swipe magnitudes, dwell times)
    - smoothing/sensitivity defaults that the dispatcher can apply on switch
    - a human-readable description (used in the UI dropdown)

Modes are deliberately limited so users can predict behavior:

    Navigation     — cursor + click + drag + scroll + pause (default)
    Presentation   — laser-style cursor + click-to-advance + swipe prev/next
    Media          — palm = play/pause, swipes = volume + track; cursor off
    Accessibility  — cursor + click + pause only, with extra-generous smoothing
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mode:
    name: str
    label: str
    description: str
    thresholds: dict = field(default_factory=dict)
    cursor_overrides: dict = field(default_factory=dict)


# Default threshold profile — concrete modes override only what they need.
_BASE_THRESHOLDS = {
    "pinch_threshold": 0.05,        # thumb-index distance to register a pinch
    "drag_hold_ms": 350,            # how long pinch must hold to escalate to drag
    "scroll_delta": 0.025,          # vertical motion to trigger a scroll tick
    "scroll_cooldown_ms": 220,      # min gap between scroll ticks
    "swipe_delta": 0.15,            # horizontal motion to register a swipe
    "swipe_window_ms": 600,         # window the swipe must complete in
    "palm_dwell_ms": 800,           # open-palm hold before pause toggles
    "click_debounce_ms": 200,       # min gap between clicks
    "gesture_lock_ms": 500,         # global mutual-exclusion window
}


NAVIGATION = Mode(
    name="navigation",
    label="Navigation",
    description=(
        "Default cursor mode. Move with your index finger, pinch to click, "
        "hold pinch to drag, two fingers to scroll, open palm to pause."
    ),
    thresholds={**_BASE_THRESHOLDS},
)


PRESENTATION = Mode(
    name="presentation",
    label="Presentation",
    description=(
        "Laser-pointer style cursor for slides. Pinch advances. Swipe left/right "
        "for previous/next slide. Scroll disabled."
    ),
    thresholds={
        **_BASE_THRESHOLDS,
        "swipe_delta": 0.18,
        "click_debounce_ms": 350,   # slower so accidental advance is rare
    },
    cursor_overrides={
        "sensitivity": 1.2,
        "smoothing_alpha": 0.18,    # heavier smoothing — laser pointer should glide
    },
)


MEDIA = Mode(
    name="media",
    label="Media",
    description=(
        "Hands-off media control. Open palm = play/pause, swipe up/down = "
        "volume, swipe left/right = previous/next track. Cursor disabled."
    ),
    thresholds={
        **_BASE_THRESHOLDS,
        "swipe_delta": 0.16,
        "palm_dwell_ms": 600,
    },
)


ACCESSIBILITY = Mode(
    name="accessibility",
    label="Accessibility",
    description=(
        "Forgiving mode for users who need slower, calmer interaction. "
        "Move + click + pause only, with heavy smoothing and slow cursor."
    ),
    thresholds={
        **_BASE_THRESHOLDS,
        "pinch_threshold": 0.07,        # easier to trigger
        "click_debounce_ms": 450,
        "palm_dwell_ms": 1000,
        "gesture_lock_ms": 700,
    },
    cursor_overrides={
        "sensitivity": 0.9,
        "smoothing_alpha": 0.12,
    },
)


_MODES: dict[str, Mode] = {
    NAVIGATION.name: NAVIGATION,
    PRESENTATION.name: PRESENTATION,
    MEDIA.name: MEDIA,
    ACCESSIBILITY.name: ACCESSIBILITY,
}


class ModeManager:
    """Holds the active mode and notifies a listener on change.

    The pipeline owns one ModeManager. The GUI calls `set_active(name)` when
    the user picks a mode from the dropdown; the classifier reads the
    threshold profile via `thresholds()`.
    """

    def __init__(self, initial: str = NAVIGATION.name) -> None:
        if initial not in _MODES:
            initial = NAVIGATION.name
        self._active = _MODES[initial]
        self._listeners: list = []

    @property
    def active(self) -> Mode:
        return self._active

    def set_active(self, name: str) -> bool:
        """Switch mode by name. Returns True if the mode actually changed."""
        if name not in _MODES:
            return False
        if name == self._active.name:
            return False
        self._active = _MODES[name]
        for cb in self._listeners:
            try:
                cb(self._active)
            except Exception:  # pragma: no cover - listener errors must not crash pipeline
                pass
        return True

    def thresholds(self) -> dict:
        return self._active.thresholds

    def on_change(self, callback) -> None:
        """Register a listener invoked with the new Mode after each change."""
        self._listeners.append(callback)

    @staticmethod
    def all_modes() -> list[Mode]:
        return list(_MODES.values())

    @staticmethod
    def get(name: str) -> Mode:
        return _MODES.get(name, NAVIGATION)
