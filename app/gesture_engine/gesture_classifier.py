"""Per-frame gesture orchestration.

Responsibilities:
    1. Build a `GestureContext` from raw MediaPipe output + active mode.
    2. Iterate gestures relevant to the active mode in priority order.
    3. Apply per-gesture debounce + global cooldown ("gesture lock").
    4. Collect zero or more `Action`s for the dispatcher.
    5. Continuous gestures (Move, Drag-while-held) bypass the lock so they
       keep emitting actions every frame.
"""

from __future__ import annotations

from typing import Optional

from app.gesture_engine.base_gesture import (
    Action,
    ActionKind,
    BaseGesture,
    GestureContext,
    now_seconds,
)
from app.gesture_engine.gesture_registry import registry
from app.gesture_engine.mode_manager import ModeManager


class GestureClassifier:
    def __init__(self, mode_manager: ModeManager) -> None:
        self._mode_manager = mode_manager
        self._lock_until_ms: float = 0.0

    def process(self, hand_results: list[dict]) -> list[Action]:
        """Run all gestures for the active mode against this frame and return
        the actions that fired, in priority order."""
        mode = self._mode_manager.active
        ctx = GestureContext(
            mode=mode.name,
            hand_results=hand_results,
            hand=hand_results[0] if hand_results else None,
            thresholds=mode.thresholds,
            now=now_seconds(),
        )

        gestures = registry.for_mode(mode.name)
        actions: list[Action] = []

        now_ms = ctx.now * 1000.0
        locked = now_ms < self._lock_until_ms

        for gesture in gestures:
            if not gesture.can_fire(ctx):
                continue
            if locked and not gesture.bypasses_lock:
                continue

            try:
                fired = gesture.detect(ctx)
            except Exception:  # pragma: no cover — gesture bugs must not crash pipeline
                continue

            if not fired:
                continue

            action = self._resolve_action(gesture, ctx)
            if action is None:
                continue

            actions.append(action)
            gesture.mark_fired(ctx)
            if gesture.cooldown_ms > 0:
                self._lock_until_ms = max(self._lock_until_ms, now_ms + gesture.cooldown_ms)

        return actions

    @staticmethod
    def _resolve_action(gesture: BaseGesture, ctx: GestureContext) -> Optional[Action]:
        """Allow gestures to override their default fire() per mode."""
        override = getattr(gesture, "mode_override_action", None)
        if callable(override):
            forced = override(ctx)
            if forced is not None:
                return forced
        return gesture.fire(ctx)

    # Used by tests / hot-reload.
    def reset_lock(self) -> None:
        self._lock_until_ms = 0.0
