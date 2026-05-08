"""Gesture engine: mode-aware, priority-resolved gesture recognition.

Public surface:
    - BaseGesture, GestureContext, Action  (base_gesture)
    - ModeManager, Mode                    (mode_manager)
    - GestureClassifier                    (gesture_classifier)
    - registry                             (gesture_registry)
    - All concrete gestures                (gestures)
"""

from app.gesture_engine.base_gesture import Action, ActionKind, BaseGesture, GestureContext
from app.gesture_engine.gesture_classifier import GestureClassifier
from app.gesture_engine.gesture_registry import registry
from app.gesture_engine.mode_manager import Mode, ModeManager

# Imported for its registration side-effect (every gesture in this module
# calls registry.register() at import time). Do not remove.
from app.gesture_engine import gestures as _gestures  # noqa: F401

__all__ = [
    "Action",
    "ActionKind",
    "BaseGesture",
    "GestureClassifier",
    "GestureContext",
    "Mode",
    "ModeManager",
    "registry",
]
