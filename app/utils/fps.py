"""FPS counter utility for performance monitoring."""

import time
from collections import deque


class FPSCounter:
    """Thread-safe FPS calculator with moving average."""

    def __init__(self, window_size: int = 30):
        self._timestamps = deque(maxlen=window_size)
        self._current_fps = 0.0

    def tick(self) -> float:
        """Record a frame tick and return current FPS."""
        now = time.perf_counter()
        self._timestamps.append(now)
        self._update_fps()
        return self._current_fps

    @property
    def fps(self) -> float:
        """Get current FPS."""
        return self._current_fps

    @property
    def frame_time_ms(self) -> float:
        """Get average frame processing time in milliseconds."""
        if self._current_fps > 0:
            return 1000.0 / self._current_fps
        return 0.0

    def _update_fps(self):
        """Calculate FPS from timestamp window."""
        if len(self._timestamps) < 2:
            self._current_fps = 0.0
            return

        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed > 0:
            self._current_fps = (len(self._timestamps) - 1) / elapsed
        else:
            self._current_fps = 0.0

    def reset(self):
        """Reset the counter."""
        self._timestamps.clear()
        self._current_fps = 0.0
