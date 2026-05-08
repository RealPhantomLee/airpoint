"""Concrete gesture recognizers.

The full set is intentionally small: Move, Click, Drag, Scroll, Pause, plus
two mode-specific gestures (SwipeHorizontal, SwipeVertical) that drive
slide / track / volume control.

Every gesture registers itself with the global `registry` at import time.
"""

from __future__ import annotations

from typing import Optional

from app.gesture_engine.base_gesture import (
    Action,
    ActionKind,
    BaseGesture,
    GestureContext,
)
from app.gesture_engine.gesture_registry import registry

# MediaPipe hand-landmark indices (subset we actually use).
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_PIP = 14
PINKY_PIP = 18


# ---------- Move (continuous) ----------


class MoveGesture(BaseGesture):
    """Cursor follows the index fingertip. Continuous; bypasses gesture lock."""

    name = "move"
    priority = 10
    enabled_in_modes = {"navigation", "presentation", "accessibility"}
    bypasses_lock = True

    def detect(self, ctx: GestureContext) -> bool:
        return ctx.hand is not None

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        lm = ctx.hand["landmarks"]
        x, y, _ = lm[INDEX_TIP]
        return Action(ActionKind.MOVE, {"x": x, "y": y})


# ---------- Click + Drag (share pinch state) ----------


class ClickGesture(BaseGesture):
    """Thumb-index pinch fires a click. Hold-pinch is handled by DragGesture
    (which has higher priority)."""

    name = "click"
    priority = 50
    enabled_in_modes = {"navigation", "presentation", "accessibility"}
    debounce_ms = 200
    cooldown_ms = 500

    def __init__(self) -> None:
        super().__init__()
        self._was_pinching = False

    def detect(self, ctx: GestureContext) -> bool:
        if ctx.hand is None:
            self._was_pinching = False
            return False
        lm = ctx.hand["landmarks"]
        d = self.distance(lm[THUMB_TIP], lm[INDEX_TIP])
        is_pinching = d < ctx.thresholds["pinch_threshold"]
        # Edge: rising edge only — fire when transitioning into a pinch.
        fired = is_pinching and not self._was_pinching
        self._was_pinching = is_pinching
        return fired

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        if ctx.mode == "presentation":
            return Action(ActionKind.SLIDE_NEXT)
        return Action(ActionKind.CLICK)


class DragGesture(BaseGesture):
    """Pinch held longer than `drag_hold_ms` engages drag.

    Higher priority than Click so once we cross the hold threshold the click
    is suppressed. Releasing the pinch ends the drag.
    """

    name = "drag"
    priority = 60
    enabled_in_modes = {"navigation"}
    bypasses_lock = True   # drag must keep emitting until release

    def __init__(self) -> None:
        super().__init__()
        self._pinch_start_s: Optional[float] = None
        self._dragging = False

    def detect(self, ctx: GestureContext) -> bool:
        if ctx.hand is None:
            # Lost the hand mid-drag — release.
            if self._dragging:
                self._dragging = False
                self._pinch_start_s = None
                return True
            self._pinch_start_s = None
            return False

        lm = ctx.hand["landmarks"]
        is_pinching = self.distance(lm[THUMB_TIP], lm[INDEX_TIP]) < ctx.thresholds["pinch_threshold"]

        if is_pinching:
            if self._pinch_start_s is None:
                self._pinch_start_s = ctx.now
            held_ms = (ctx.now - self._pinch_start_s) * 1000.0
            if not self._dragging and held_ms >= ctx.thresholds["drag_hold_ms"]:
                self._dragging = True
                return True   # rising edge — fire DRAG_START
            return False
        else:
            if self._dragging:
                self._dragging = False
                self._pinch_start_s = None
                return True   # falling edge — fire DRAG_END
            self._pinch_start_s = None
            return False

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        return Action(ActionKind.DRAG_START if self._dragging else ActionKind.DRAG_END)


# ---------- Scroll ----------


class ScrollGesture(BaseGesture):
    """Index + middle fingers extended together; vertical motion scrolls."""

    name = "scroll"
    priority = 40
    enabled_in_modes = {"navigation", "accessibility"}

    def __init__(self) -> None:
        super().__init__()
        self._prev_y: Optional[float] = None
        self._last_scroll_ms: float = 0.0
        self._direction: Optional[str] = None

    def detect(self, ctx: GestureContext) -> bool:
        if ctx.hand is None:
            self._prev_y = None
            return False
        lm = ctx.hand["landmarks"]
        index_up = self.is_finger_extended(lm, INDEX_TIP, INDEX_PIP)
        middle_up = self.is_finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
        ring_down = not self.is_finger_extended(lm, MIDDLE_TIP + 4, RING_PIP)
        if not (index_up and middle_up and ring_down):
            self._prev_y = None
            return False

        # Use mid-point between index & middle as the scroll cursor.
        cur_y = (lm[INDEX_TIP][1] + lm[MIDDLE_TIP][1]) / 2.0
        if self._prev_y is None:
            self._prev_y = cur_y
            return False

        delta = cur_y - self._prev_y
        threshold = ctx.thresholds["scroll_delta"]
        cooldown = ctx.thresholds["scroll_cooldown_ms"]
        now_ms = ctx.now * 1000.0

        if abs(delta) < threshold:
            return False
        if now_ms - self._last_scroll_ms < cooldown:
            return False

        self._direction = "down" if delta > 0 else "up"
        self._prev_y = cur_y
        self._last_scroll_ms = now_ms
        return True

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        if self._direction == "up":
            return Action(ActionKind.SCROLL_UP)
        return Action(ActionKind.SCROLL_DOWN)


# ---------- Pause / Resume (open palm dwell) ----------


class PauseGesture(BaseGesture):
    """Open palm held for `palm_dwell_ms` toggles pause.

    Active in every mode and allowed while paused so the user can always
    resume without restarting the app.
    """

    name = "pause"
    priority = 90
    enabled_in_modes = {"navigation", "presentation", "media", "accessibility"}
    cooldown_ms = 700
    allowed_when_paused = True

    def __init__(self) -> None:
        super().__init__()
        self._open_since_s: Optional[float] = None
        self._is_paused = False

    def detect(self, ctx: GestureContext) -> bool:
        if ctx.hand is None:
            self._open_since_s = None
            return False

        lm = ctx.hand["landmarks"]
        # All four finger tips above their PIPs = open palm.
        extended = sum(
            1
            for tip, pip in (
                (INDEX_TIP, INDEX_PIP),
                (MIDDLE_TIP, MIDDLE_PIP),
                (16, RING_PIP),
                (20, PINKY_PIP),
            )
            if self.is_finger_extended(lm, tip, pip)
        )

        if extended >= 4:
            if self._open_since_s is None:
                self._open_since_s = ctx.now
                return False
            held_ms = (ctx.now - self._open_since_s) * 1000.0
            if held_ms >= ctx.thresholds["palm_dwell_ms"]:
                self._open_since_s = None
                self._is_paused = not self._is_paused
                return True
            return False

        self._open_since_s = None
        return False

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        return Action(ActionKind.PAUSE if self._is_paused else ActionKind.RESUME)

    # Mode-specific override: in Media mode, open-palm dwell sends play/pause
    # rather than the global pause toggle.
    def mode_override_action(self, ctx: GestureContext) -> Optional[Action]:
        if ctx.mode == "media":
            return Action(ActionKind.MEDIA_PLAY_PAUSE)
        return None


# ---------- Swipes (mode-specific media / presentation gestures) ----------


class SwipeHorizontalGesture(BaseGesture):
    """Quick horizontal motion of the index fingertip.

    Drives slide prev/next in Presentation mode and track prev/next in Media
    mode. Disabled in Navigation and Accessibility.
    """

    name = "swipe_horizontal"
    priority = 70
    enabled_in_modes = {"presentation", "media"}
    cooldown_ms = 600

    def __init__(self) -> None:
        super().__init__()
        self._anchor_x: Optional[float] = None
        self._anchor_t: float = 0.0
        self._direction: Optional[str] = None

    def detect(self, ctx: GestureContext) -> bool:
        if ctx.hand is None:
            self._anchor_x = None
            return False
        lm = ctx.hand["landmarks"]
        index_up = self.is_finger_extended(lm, INDEX_TIP, INDEX_PIP)
        middle_up = self.is_finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
        # Single index extended (not the scroll pose).
        if not (index_up and not middle_up):
            self._anchor_x = None
            return False

        x = lm[INDEX_TIP][0]
        if self._anchor_x is None:
            self._anchor_x = x
            self._anchor_t = ctx.now
            return False

        if (ctx.now - self._anchor_t) * 1000.0 > ctx.thresholds["swipe_window_ms"]:
            self._anchor_x = x
            self._anchor_t = ctx.now
            return False

        dx = x - self._anchor_x
        if abs(dx) >= ctx.thresholds["swipe_delta"]:
            self._direction = "right" if dx > 0 else "left"
            self._anchor_x = None
            return True
        return False

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        if ctx.mode == "presentation":
            return Action(
                ActionKind.SLIDE_NEXT if self._direction == "right" else ActionKind.SLIDE_PREV
            )
        if ctx.mode == "media":
            return Action(
                ActionKind.MEDIA_NEXT if self._direction == "right" else ActionKind.MEDIA_PREV
            )
        return None


class SwipeVerticalGesture(BaseGesture):
    """Vertical swipe of the index fingertip — used only in Media mode for
    volume up/down. (Navigation uses ScrollGesture instead.)"""

    name = "swipe_vertical"
    priority = 70
    enabled_in_modes = {"media"}
    cooldown_ms = 350

    def __init__(self) -> None:
        super().__init__()
        self._anchor_y: Optional[float] = None
        self._anchor_t: float = 0.0
        self._direction: Optional[str] = None

    def detect(self, ctx: GestureContext) -> bool:
        if ctx.hand is None:
            self._anchor_y = None
            return False
        lm = ctx.hand["landmarks"]
        index_up = self.is_finger_extended(lm, INDEX_TIP, INDEX_PIP)
        middle_up = self.is_finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
        if not (index_up and not middle_up):
            self._anchor_y = None
            return False

        y = lm[INDEX_TIP][1]
        if self._anchor_y is None:
            self._anchor_y = y
            self._anchor_t = ctx.now
            return False

        if (ctx.now - self._anchor_t) * 1000.0 > ctx.thresholds["swipe_window_ms"]:
            self._anchor_y = y
            self._anchor_t = ctx.now
            return False

        dy = y - self._anchor_y
        if abs(dy) >= ctx.thresholds["swipe_delta"]:
            self._direction = "down" if dy > 0 else "up"
            self._anchor_y = None
            return True
        return False

    def fire(self, ctx: GestureContext) -> Optional[Action]:
        if self._direction == "up":
            return Action(ActionKind.MEDIA_VOL_UP)
        return Action(ActionKind.MEDIA_VOL_DOWN)


# ---------- Registration ----------


def register_default_gestures() -> None:
    """Idempotent — safe to call multiple times. Imported at package init."""
    for cls in (
        MoveGesture,
        ScrollGesture,
        ClickGesture,
        DragGesture,
        SwipeHorizontalGesture,
        SwipeVerticalGesture,
        PauseGesture,
    ):
        registry.register(cls())


register_default_gestures()
