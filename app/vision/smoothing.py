"""Movement smoothing engine for cursor control."""

import numpy as np
from collections import deque


class CursorSmoother:
    """
    Applies multiple smoothing techniques to cursor movement:
    - Exponential Moving Average (EMA)
    - Simple Moving Average (SMA)
    - Deadzone filtering
    """

    def __init__(
        self,
        alpha: float = 0.3,
        window_size: int = 5,
        deadzone: float = 0.02,
    ):
        """
        Args:
            alpha: EMA smoothing factor (0-1, lower = smoother)
            window_size: SMA window size
            deadzone: Minimum movement threshold (normalized)
        """
        self.alpha = alpha
        self.window_size = window_size
        self.deadzone = deadzone

        self._ema_pos = None
        self._sma_buffer = deque(maxlen=window_size)
        self._initialized = False

    def smooth(self, x: float, y: float) -> tuple[float, float]:
        """
        Apply smoothing to raw cursor coordinates.

        Args:
            x: Normalized x coordinate (0.0-1.0)
            y: Normalized y coordinate (0.0-1.0)

        Returns:
            Smoothed (x, y) tuple
        """
        pos = np.array([x, y])

        # Initialize on first call
        if not self._initialized:
            self._ema_pos = pos.copy()
            self._sma_buffer.append(pos.copy())
            self._initialized = True
            return (x, y)

        # Deadzone: ignore tiny movements
        delta = pos - self._ema_pos
        if np.linalg.norm(delta) < self.deadzone:
            return (self._ema_pos[0], self._ema_pos[1])

        # Apply EMA
        self._ema_pos = self.alpha * pos + (1 - self.alpha) * self._ema_pos

        # Update SMA buffer
        self._sma_buffer.append(self._ema_pos.copy())

        # Return SMA of EMA values for extra smoothness
        if len(self._sma_buffer) >= self.window_size:
            smoothed = np.mean(list(self._sma_buffer), axis=0)
        else:
            smoothed = self._ema_pos

        return (float(smoothed[0]), float(smoothed[1]))

    def reset(self):
        """Reset smoothing state."""
        self._ema_pos = None
        self._sma_buffer.clear()
        self._initialized = False

    def update_params(self, alpha: float | None = None, window_size: int | None = None):
        """Update smoothing parameters at runtime."""
        if alpha is not None:
            self.alpha = alpha
        if window_size is not None:
            self.window_size = window_size
            self._sma_buffer = deque(maxlen=window_size)
