"""Base classes for gesture detection.

Design:
    - A `BaseGesture` is a single recognizer with a stable `name`, a `priority`
      (higher wins when two gestures fire on the same frame), and a set of
      `enabled_in_modes` that the ModeManager filters by.
    - `detect()` returns a bool — did the gesture fire on this frame? It is
      side-effect-free aside from the gesture's own internal state machine.
    - `fire()` returns an Action (or None) describing what should happen.
      The ActionDispatcher routes Actions to the mouse / media controllers.
    - Conflicts: if two gestures both detect on the same frame, the higher
      priority wins. The classifier also enforces a global cooldown after any
      gesture fires (`gesture_lock_ms`) and a per-gesture debounce.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionKind(str, Enum):
    """Every action the dispatcher knows how to perform."""

    MOVE = "move"
    CLICK = "click"
    DRAG_START = "drag_start"
    DRAG_END = "drag_end"
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    PAUSE = "pause"
    RESUME = "resume"

    SLIDE_NEXT = "slide_next"
    SLIDE_PREV = "slide_prev"

    MEDIA_PLAY_PAUSE = "media_play_pause"
    MEDIA_NEXT = "media_next"
    MEDIA_PREV = "media_prev"
    MEDIA_VOL_UP = "media_vol_up"
    MEDIA_VOL_DOWN = "media_vol_down"


@dataclass
class Action:
    """A request emitted by a gesture for the dispatcher to execute."""

    kind: ActionKind
    payload: dict = field(default_factory=dict)


@dataclass
class GestureContext:
    """Per-frame context passed into every gesture's `detect()`.

    The classifier builds this once per frame from the hand tracker output and
    the active mode profile, so individual gestures don't need to recompute
    common derived values.
    """

    # Active mode (e.g. "navigation", "presentation", "media", "accessibility").
    mode: str

    # Raw hand results from MediaPipe: list of dicts with landmarks/label/score.
    hand_results: list[dict]

    # Convenience: the primary hand (first detected) or None.
    hand: Optional[dict]

    # Mode-resolved threshold profile (pinch/scroll/swipe/dwell magnitudes).
    thresholds: dict

    # Wall-clock timestamp of this frame (seconds, time.monotonic()-style).
    now: float


class BaseGesture:
    """Subclass and override `detect()` and `fire()`.

    The classifier handles cooldown / debounce / mode filtering uniformly so
    subclasses stay focused on the recognition logic itself.
    """

    #: Stable id (lower-snake-case). Used as the dict key in toggles + logs.
    name: str = ""

    #: Higher-priority gestures win conflicts on the same frame.
    priority: int = 0

    #: Set of mode names this gesture is allowed to fire in.
    enabled_in_modes: set[str] = set()

    #: Per-gesture re-fire debounce (ms). 0 = no debounce.
    debounce_ms: int = 0

    #: How long after firing this gesture to suppress *any* lower-priority
    #: action gesture (ms). 0 = no global cooldown contribution.
    cooldown_ms: int = 0

    #: If True, this gesture is allowed to fire even while the dispatcher is
    #: paused. (Pause/Resume itself must set this to True.)
    allowed_when_paused: bool = False

    #: If True, the classifier should not enforce the global gesture-lock
    #: window for this gesture. Useful for continuous gestures like Move that
    #: must keep emitting actions every frame.
    bypasses_lock: bool = False

    def __init__(self) -> None:
        self._last_fire_ms: float = 0.0

    # ----- API the classifier uses -----

    def can_fire(self, ctx: GestureContext) -> bool:
        """True if mode-allowed and not in our own debounce window."""
        if ctx.mode not in self.enabled_in_modes:
            return False
        if self.debounce_ms <= 0:
            return True
        return (ctx.now * 1000.0) - self._last_fire_ms >= self.debounce_ms

    def mark_fired(self, ctx: GestureContext) -> None:
        self._last_fire_ms = ctx.now * 1000.0

    # ----- subclass hooks -----

    def detect(self, ctx: GestureContext) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError

    def fire(self, ctx: GestureContext) -> Optional[Action]:  # pragma: no cover - abstract
        raise NotImplementedError

    # ----- helpers shared by subclasses -----

    @staticmethod
    def distance(p1: tuple, p2: tuple) -> float:
        """2-D Euclidean distance on (x, y) ignoring z."""
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    @staticmethod
    def is_finger_extended(landmarks: list, tip_idx: int, pip_idx: int) -> bool:
        """A finger is 'extended' when its tip is above its PIP joint
        (smaller y in image coords means higher up).
        """
        return landmarks[tip_idx][1] < landmarks[pip_idx][1]


def now_seconds() -> float:
    """Single source of truth for time so tests can stub via time.monotonic patch."""
    return time.monotonic()
