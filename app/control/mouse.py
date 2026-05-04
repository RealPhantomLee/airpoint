"""Mouse control via pynput (cross-platform)."""

from pynput import mouse

from app.config import Settings
from app.vision.smoothing import CursorSmoother
from app.utils.platform import get_screen_size


class MouseController:
    """Controls OS mouse cursor from hand tracking data."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.smoother = CursorSmoother(
            alpha=settings.get("cursor.smoothing_alpha", 0.3),
            window_size=settings.get("cursor.moving_average_window", 5),
            deadzone=settings.get("cursor.deadzone", 0.02),
        )

        self.sensitivity = settings.get("cursor.sensitivity", 1.5)
        self.invert_x = settings.get("cursor.invert_x", False)
        self.invert_y = settings.get("cursor.invert_y", False)
        self.edge_boost = settings.get("cursor.edge_boost", False)
        self.edge_boost_factor = settings.get("cursor.edge_boost_factor", 2.0)

        self._mouse = mouse.Controller()
        self._screen_width, self._screen_height = get_screen_size()

        self._prev_pos = None
        self._is_paused = False

    def move_cursor(self, norm_x, norm_y):
        if self._is_paused:
            return

        smooth_x, smooth_y = self.smoother.smooth(norm_x, norm_y)

        if self.invert_x:
            smooth_x = 1.0 - smooth_x
        if self.invert_y:
            smooth_y = 1.0 - smooth_y

        # Edge boost: amplify movement near screen edges so cursor can reach corners
        if self.edge_boost:
            smooth_x = self._apply_edge_boost(smooth_x)
            smooth_y = self._apply_edge_boost(smooth_y)

        cx = 0.5 + (smooth_x - 0.5) * self.sensitivity
        cy = 0.5 + (smooth_y - 0.5) * self.sensitivity

        screen_x = int(cx * self._screen_width)
        screen_y = int(cy * self._screen_height)

        screen_x = max(0, min(screen_x, self._screen_width - 1))
        screen_y = max(0, min(screen_y, self._screen_height - 1))

        self._mouse.position = (screen_x, screen_y)
        self._prev_pos = (smooth_x, smooth_y)

    def _apply_edge_boost(self, value):
        if not self.edge_boost:
            return value

        factor = self.edge_boost_factor

        if value < 0.5:
            # Lower half: push toward 0
            normalized = value / 0.5
            boosted = normalized ** factor
            return boosted * 0.5
        else:
            # Upper half: push toward 1
            distance_from_edge = 1.0 - value
            normalized = distance_from_edge / 0.5
            boosted = normalized ** factor
            new_distance = boosted * 0.5
            return 1.0 - new_distance

    def click(self):
        if not self._is_paused:
            self._mouse.click(mouse.Button.left)

    def double_click(self):
        if not self._is_paused:
            self._mouse.click(mouse.Button.left, 2)

    def right_click(self):
        if not self._is_paused:
            self._mouse.click(mouse.Button.right)

    def middle_click(self):
        if not self._is_paused:
            self._mouse.click(mouse.Button.middle)

    def scroll(self, direction):
        if self._is_paused:
            return
        amounts = {"up": 10, "down": -10, "left": -5, "right": 5}
        if direction in amounts:
            if direction in ("left", "right"):
                self._mouse.scroll(amounts[direction], 0)
            else:
                self._mouse.scroll(0, amounts[direction])

    def drag_start(self):
        if not self._is_paused:
            self._mouse.press(mouse.Button.left)

    def drag_end(self):
        if not self._is_paused:
            self._mouse.release(mouse.Button.left)

    def set_paused(self, paused):
        self._is_paused = paused

    @property
    def is_paused(self):
        return self._is_paused

    def update_sensitivity(self, sensitivity):
        self.sensitivity = max(0.1, min(sensitivity, 5.0))
