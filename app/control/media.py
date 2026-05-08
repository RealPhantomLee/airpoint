"""Cross-platform media + presentation key control via pynput.

Replaces the old `app/control/hotkeys.py`. The dead `HotkeyManager` skeleton
is gone; the surviving `MediaController` lives here under its proper name.
The class also gained `play_pause`, `slide_next`, and `slide_prev` so it
covers the new Media + Presentation modes.
"""

from __future__ import annotations

import platform

from pynput import keyboard


class MediaController:
    """Simulates media keys + slide-navigation keys."""

    def __init__(self) -> None:
        self._kb = keyboard.Controller()
        self._is_macos = platform.system() == "Darwin"

    # ----- media keys -----

    def volume_up(self) -> None:
        self._kb.press(keyboard.Key.media_volume_up)
        self._kb.release(keyboard.Key.media_volume_up)

    def volume_down(self) -> None:
        self._kb.press(keyboard.Key.media_volume_down)
        self._kb.release(keyboard.Key.media_volume_down)

    def mute(self) -> None:
        self._kb.press(keyboard.Key.media_volume_mute)
        self._kb.release(keyboard.Key.media_volume_mute)

    def play_pause(self) -> None:
        self._kb.press(keyboard.Key.media_play_pause)
        self._kb.release(keyboard.Key.media_play_pause)

    def next_track(self) -> None:
        self._kb.press(keyboard.Key.media_next)
        self._kb.release(keyboard.Key.media_next)

    def prev_track(self) -> None:
        self._kb.press(keyboard.Key.media_previous)
        self._kb.release(keyboard.Key.media_previous)

    # ----- presentation: most slide tools accept arrow keys -----

    def slide_next(self) -> None:
        self._kb.press(keyboard.Key.right)
        self._kb.release(keyboard.Key.right)

    def slide_prev(self) -> None:
        self._kb.press(keyboard.Key.left)
        self._kb.release(keyboard.Key.left)

    # ----- editing (kept for parity with the old hotkeys module) -----

    def copy(self) -> None:
        mod = keyboard.Key.cmd if self._is_macos else keyboard.Key.ctrl
        with self._kb.pressed(mod):
            self._kb.press("c")
            self._kb.release("c")

    def paste(self) -> None:
        mod = keyboard.Key.cmd if self._is_macos else keyboard.Key.ctrl
        with self._kb.pressed(mod):
            self._kb.press("v")
            self._kb.release("v")
