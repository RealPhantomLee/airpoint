"""Central registry of all known gestures.

Gestures register themselves at import time. The classifier asks the registry
for the list of gestures relevant to the active mode, sorted by priority.
"""

from __future__ import annotations

from app.gesture_engine.base_gesture import BaseGesture


class _Registry:
    def __init__(self) -> None:
        self._gestures: list[BaseGesture] = []

    def register(self, gesture: BaseGesture) -> BaseGesture:
        if any(g.name == gesture.name for g in self._gestures):
            return gesture
        self._gestures.append(gesture)
        return gesture

    def all(self) -> list[BaseGesture]:
        return list(self._gestures)

    def for_mode(self, mode: str) -> list[BaseGesture]:
        """Return gestures enabled in `mode`, highest-priority first."""
        return sorted(
            [g for g in self._gestures if mode in g.enabled_in_modes],
            key=lambda g: -g.priority,
        )

    def clear(self) -> None:
        """For tests."""
        self._gestures.clear()


registry = _Registry()
