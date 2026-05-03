"""Gesture recognition engine for Airpoint."""

import time
import numpy as np

from app.config import Settings


class GestureEngine:
    """Recognizes hand gestures from pre-processed MediaPipe landmarks."""

    FINGERTIPS = {
        "thumb": 4,
        "index": 8,
        "middle": 12,
        "ring": 16,
        "pinky": 20,
    }

    FINGER_MCPS = {
        "thumb": 2,
        "index": 5,
        "middle": 9,
        "ring": 13,
        "pinky": 17,
    }

    FINGER_PIPS = {
        "index": 6,
        "middle": 10,
        "ring": 14,
        "pinky": 18,
    }

    def __init__(self, settings: Settings):
        self.settings = settings

        self._last_click_time = 0
        self._last_pinch_time = 0
        self._palm_hold_start = None
        self._prev_scroll_y = None
        self._prev_scroll_x = None
        self._scroll_cooldown = 0
        self._gesture_locked_until = 0
        self._last_thumb_x = None
        self._thumb_wave_start = None

        self.pinch_threshold = settings.get("gestures.pinch_threshold", 0.04)
        self.scroll_threshold = settings.get("gestures.scroll_threshold", 0.015)
        self.debounce_ms = settings.get("gestures.click_debounce_ms", 200)
        self.double_click_delay_ms = settings.get("gestures.double_click_delay_ms", 400)
        self.gesture_lock_ms = settings.get("gestures.gesture_lock_ms", 500)

    def detect_gestures(self, hand_results: list[dict]) -> dict:
        gestures = {
            "move": None,
            "click": False,
            "double_click": False,
            "right_click": False,
            "middle_click": False,
            "scroll_up": False,
            "scroll_down": False,
            "scroll_left": False,
            "scroll_right": False,
            "drag": False,
            "pause": False,
            "shortcut": False,
            "volume_up": False,
            "volume_down": False,
            "prev_track": False,
            "next_track": False,
            "copy": False,
            "paste": False,
        }

        if not hand_results:
            self._palm_hold_start = None
            self._last_thumb_x = None
            self._prev_scroll_y = None
            return gestures

        # Two hands = shortcut mode
        if len(hand_results) >= 2:
            gestures["shortcut"] = True
            return gestures

        hand = hand_results[0]
        landmarks = hand["landmarks"]

        now = time.time() * 1000

        # Movement is always allowed
        index_tip = self._get_landmark_2d(landmarks, 8)
        if index_tip != (0.0, 0.0):
            gestures["move"] = index_tip

        # === PAUSE: Open palm hold ===
        if self._is_open_palm(landmarks):
            if self._palm_hold_start is None:
                self._palm_hold_start = time.time()
            elif (time.time() - self._palm_hold_start) > 1.0:
                gestures["pause"] = True
                self._lock_gesture()
        else:
            self._palm_hold_start = None

        # Skip action gestures if locked
        if now < self._gesture_locked_until:
            if self._scroll_cooldown > 0:
                self._scroll_cooldown -= 1
            return gestures

        # === LEFT CLICK: Thumb + index pinch ===
        thumb_tip = self._get_landmark_3d(landmarks, 4)
        index_tip_3d = self._get_landmark_3d(landmarks, 8)
        if thumb_tip != (0.0, 0.0, 0.0) and index_tip_3d != (0.0, 0.0, 0.0):
            dist = self._distance(thumb_tip[:2], index_tip_3d[:2])
            if dist < self.pinch_threshold and self._can_click():
                gestures["click"] = True
                self._last_click_time = time.time()
                if (now - self._last_pinch_time) < self.double_click_delay_ms:
                    gestures["double_click"] = True
                self._last_pinch_time = now
                self._lock_gesture()

        # === RIGHT CLICK: Thumb + middle pinch ===
        middle_tip = self._get_landmark_3d(landmarks, 12)
        if thumb_tip != (0.0, 0.0, 0.0) and middle_tip != (0.0, 0.0, 0.0):
            dist = self._distance(thumb_tip[:2], middle_tip[:2])
            if dist < self.pinch_threshold and self._can_click():
                gestures["right_click"] = True
                self._lock_gesture()

        # === MIDDLE CLICK: Thumb + ring pinch ===
        ring_tip = self._get_landmark_3d(landmarks, 16)
        if thumb_tip != (0.0, 0.0, 0.0) and ring_tip != (0.0, 0.0, 0.0):
            dist = self._distance(thumb_tip[:2], ring_tip[:2])
            if dist < self.pinch_threshold and self._can_click():
                gestures["middle_click"] = True
                self._lock_gesture()

        # === DRAG: Closed fist ===
        if self._is_closed_fist(landmarks):
            gestures["drag"] = True

        # === VERTICAL SCROLL: Two fingers (index + middle) up/down ===
        if self._is_two_fingers_up(landmarks):
            index_y = landmarks[8][1]
            if self._prev_scroll_y is not None:
                delta = self._prev_scroll_y - index_y
                if abs(delta) > self.scroll_threshold:
                    if self._scroll_cooldown <= 0:
                        gestures["scroll_up"] if delta > 0 else gestures["scroll_down"]
                        gestures["scroll_up" if delta > 0 else "scroll_down"] = True
                        self._scroll_cooldown = 8
                    self._scroll_cooldown -= 1
            self._prev_scroll_y = index_y
        else:
            self._prev_scroll_y = None

        # === HORIZONTAL SCROLL: Two fingers spread ===
        if self._is_two_fingers_up(landmarks):
            spread = landmarks[8][0] - landmarks[12][0]
            if self._prev_scroll_x is not None:
                delta = spread - self._prev_scroll_x
                if abs(delta) > self.scroll_threshold and self._scroll_cooldown <= 0:
                    gestures["scroll_right" if delta > 0 else "scroll_left"] = True
                    self._lock_gesture()
            self._prev_scroll_x = spread
        else:
            self._prev_scroll_x = None

        if self._scroll_cooldown > 0:
            self._scroll_cooldown -= 1

        # === VOLUME: Thumb wave right/left (thumb + index up) ===
        if self._is_thumb_and_index_up(landmarks):
            thumb_x = landmarks[4][0]
            if self._thumb_wave_start is None:
                self._thumb_wave_start = {"x": thumb_x, "t": time.time()}
            else:
                elapsed = time.time() - self._thumb_wave_start["t"]
                if 0.3 < elapsed < 1.5:
                    dx = thumb_x - self._thumb_wave_start["x"]
                    if dx > 0.08:
                        gestures["volume_up"] = True
                        self._lock_gesture()
                    elif dx < -0.08:
                        gestures["volume_down"] = True
                        self._lock_gesture()
        else:
            self._thumb_wave_start = None

        return gestures

    def _lock_gesture(self):
        now = time.time() * 1000
        self._gesture_locked_until = now + self.gesture_lock_ms

    def _can_click(self) -> bool:
        now = time.time() * 1000
        return (now - self._last_click_time) >= self.debounce_ms

    def _get_landmark_2d(self, landmarks, idx):
        if idx < len(landmarks):
            return (landmarks[idx][0], landmarks[idx][1])
        return (0.0, 0.0)

    def _get_landmark_3d(self, landmarks, idx):
        if idx < len(landmarks):
            return landmarks[idx]
        return (0.0, 0.0, 0.0)

    def _distance(self, p1, p2):
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))

    def _is_finger_extended(self, landmarks, finger):
        tip_idx = self.FINGERTIPS[finger]
        if finger == "thumb":
            tip = landmarks[tip_idx]
            ip = landmarks[3]
            return tip[0] < ip[0]
        pip_idx = self.FINGER_PIPS[finger]
        return landmarks[tip_idx][1] < landmarks[pip_idx][1]

    def _count_extended(self, landmarks):
        return sum(1 for f in ["index", "middle", "ring", "pinky"] if self._is_finger_extended(landmarks, f))

    def _is_open_palm(self, landmarks):
        return self._count_extended(landmarks) >= 4

    def _is_closed_fist(self, landmarks):
        return self._count_extended(landmarks) == 0

    def _is_two_fingers_up(self, landmarks):
        return self._count_extended(landmarks) == 2 and \
               self._is_finger_extended(landmarks, "index") and \
               self._is_finger_extended(landmarks, "middle")

    def _is_thumb_and_index_up(self, landmarks):
        return self._is_finger_extended(landmarks, "index") and \
               not self._is_finger_extended(landmarks, "middle") and \
               not self._is_finger_extended(landmarks, "ring")
