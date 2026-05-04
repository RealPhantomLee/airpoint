"""Keyboard hotkey and media control for Airpoint."""

import sys
from pynput import keyboard


class HotkeyManager:
    """Manages global keyboard hotkeys."""

    def __init__(self):
        self._listener = None
        self._callbacks = {}
        self._running = False

    def register(self, key_combination: str, callback):
        """
        Register a hotkey callback.

        Args:
            key_combination: String like "ctrl+shift+p"
            callback: Function to call when hotkey pressed
        """
        self._callbacks[key_combination.lower()] = callback

    def start(self):
        """Start listening for hotkeys."""
        self._running = True
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self):
        """Stop listening for hotkeys."""
        self._running = False
        if self._listener:
            self._listener.stop()

    def _on_press(self, key):
        pass

    def _on_release(self, key):
        pass

    def close(self):
        self.stop()


class MediaController:
    """Controls media playback and volume via keyboard media keys (cross-platform)."""

    def __init__(self):
        self._kb = keyboard.Controller()

    def _tap(self, key):
        self._kb.press(key)
        self._kb.release(key)

    def volume_up(self):
        self._tap(keyboard.Key.media_volume_up)

    def volume_down(self):
        self._tap(keyboard.Key.media_volume_down)

    def mute(self):
        self._tap(keyboard.Key.media_volume_mute)

    def next_track(self):
        self._tap(keyboard.Key.media_next)

    def prev_track(self):
        self._tap(keyboard.Key.media_previous)

    def copy(self):
        modifier = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl
        with self._kb.pressed(modifier):
            self._tap(keyboard.KeyCode.from_char("c"))

    def paste(self):
        modifier = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl
        with self._kb.pressed(modifier):
            self._tap(keyboard.KeyCode.from_char("v"))
