"""Routes Action objects from the gesture classifier to the OS controllers.

Owns:
    - the MouseController (cursor + click + scroll + drag)
    - the MediaController (volume + play/pause + tracks)
    - the global pause flag (toggled by PauseGesture)

This is the only module that knows how an Action becomes a real OS event.
That keeps gestures pure (they only describe intent) and lets us swap input
backends (pynput → uinput → AppleScript) without touching gesture code.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import Settings
from app.control.media import MediaController
from app.control.mouse import MouseController
from app.gesture_engine import Action, ActionKind, Mode, ModeManager

logger = logging.getLogger(__name__)


class ActionDispatcher:
    def __init__(
        self,
        settings: Settings,
        mouse_controller: MouseController,
        media_controller: MediaController,
        mode_manager: ModeManager,
    ) -> None:
        self._settings = settings
        self._mouse = mouse_controller
        self._media = media_controller
        self._mode_manager = mode_manager

        # Independent of mouse_controller's own pause: this lets the dispatcher
        # ignore an ENTIRE class of actions (e.g. cursor) without touching the
        # underlying controller.
        self._paused = False

        # Apply mode profile on startup AND on every mode change.
        self._apply_mode_profile(mode_manager.active)
        mode_manager.on_change(self._apply_mode_profile)

    # ----- public surface -----

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._mouse.set_paused(paused)

    def dispatch(self, action: Action) -> None:
        """Execute one action. Pause is honored except for PAUSE/RESUME themselves."""
        kind = action.kind
        mode = self._mode_manager.active.name

        if self._paused and kind not in (ActionKind.PAUSE, ActionKind.RESUME):
            return

        # ----- pause -----
        if kind is ActionKind.PAUSE:
            self.set_paused(True)
            return
        if kind is ActionKind.RESUME:
            self.set_paused(False)
            return

        # ----- cursor (only in cursor modes) -----
        if mode == "media":
            # Media mode disables cursor entirely; ignore any leaked cursor
            # actions defensively.
            if kind in (
                ActionKind.MOVE,
                ActionKind.CLICK,
                ActionKind.DRAG_START,
                ActionKind.DRAG_END,
                ActionKind.SCROLL_UP,
                ActionKind.SCROLL_DOWN,
            ):
                return

        if kind is ActionKind.MOVE:
            self._mouse.move_cursor(action.payload["x"], action.payload["y"])
            return
        if kind is ActionKind.CLICK:
            self._mouse.click()
            return
        if kind is ActionKind.DRAG_START:
            self._mouse.drag_start()
            return
        if kind is ActionKind.DRAG_END:
            self._mouse.drag_end()
            return
        if kind is ActionKind.SCROLL_UP:
            self._mouse.scroll("up")
            return
        if kind is ActionKind.SCROLL_DOWN:
            self._mouse.scroll("down")
            return

        # ----- presentation -----
        if kind is ActionKind.SLIDE_NEXT:
            self._media.slide_next()
            return
        if kind is ActionKind.SLIDE_PREV:
            self._media.slide_prev()
            return

        # ----- media -----
        if kind is ActionKind.MEDIA_PLAY_PAUSE:
            self._media.play_pause()
            return
        if kind is ActionKind.MEDIA_NEXT:
            self._media.next_track()
            return
        if kind is ActionKind.MEDIA_PREV:
            self._media.prev_track()
            return
        if kind is ActionKind.MEDIA_VOL_UP:
            self._media.volume_up()
            return
        if kind is ActionKind.MEDIA_VOL_DOWN:
            self._media.volume_down()
            return

        logger.warning("Unhandled action kind: %s", kind)

    def dispatch_many(self, actions: list[Action]) -> None:
        for a in actions:
            self.dispatch(a)

    # ----- mode profile application -----

    def _apply_mode_profile(self, mode: Mode) -> None:
        """When a mode is activated, push its cursor overrides onto the mouse
        controller so smoothing and sensitivity feel right immediately."""
        overrides = mode.cursor_overrides
        if "sensitivity" in overrides:
            self._mouse.update_sensitivity(overrides["sensitivity"])
        if "smoothing_alpha" in overrides:
            try:
                self._mouse.smoother.update_params(alpha=overrides["smoothing_alpha"])
            except AttributeError:
                pass
