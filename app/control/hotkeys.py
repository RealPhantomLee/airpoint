"""Keyboard hotkey management for Airpoint."""

import threading
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
        """Handle key press events."""
        pass

    def _on_release(self, key):
        """Handle key release events."""
        pass

    def close(self):
        """Clean up resources."""
        self.stop()
