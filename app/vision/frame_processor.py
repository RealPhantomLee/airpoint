"""Frame preprocessing pipeline for low-light and GoPro optimization."""

import cv2
import numpy as np


class FrameProcessor:
    """
    Pre-processes camera frames before hand detection.
    Handles low-light enhancement and GoPro wide-angle correction.
    """

    def __init__(self, settings):
        self.low_light_mode = settings.get("camera.low_light_mode", False)
        self.clahe_clip = settings.get("camera.clahe_clip_limit", 2.0)
        self.brightness_boost = settings.get("camera.brightness_boost", 15)
        self.contrast_boost = settings.get("camera.contrast_boost", 1.2)
        self.auto_exposure = settings.get("camera.auto_exposure", True)
        self.wide_angle_correction = settings.get("camera.wide_angle_correction", False)

        self.clahe = cv2.createCLAHE(clipLimit=self.clahe_clip, tileGridSize=(8, 8))

        # GoPro wide-angle lens distortion parameters
        # These approximate a GoPro's barrel distortion for a ~120° FOV lens
        self._distortion_k1 = -0.2
        self._distortion_k2 = 0.05

        self._brightness_lut = self._build_lut_add(self.brightness_boost)
        self._contrast_lut = self._build_lut_contrast(self.contrast_boost)

    @staticmethod
    def _build_lut_add(value: float) -> np.ndarray:
        return np.clip(np.arange(256, dtype=np.float32) + value, 0, 255).astype(np.uint8)

    @staticmethod
    def _build_lut_contrast(factor: float) -> np.ndarray:
        return np.clip(128.0 + factor * (np.arange(256, dtype=np.float32) - 128), 0, 255).astype(np.uint8)

    def process(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply the full preprocessing pipeline.

        Args:
            frame: Raw BGR frame from camera

        Returns:
            Enhanced frame ready for MediaPipe detection
        """
        # Compute brightness once — used by both auto-exposure and low-light checks
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))

        result = frame

        if self.auto_exposure:
            result = self._auto_exposure(result, mean_brightness)

        if self.low_light_mode or mean_brightness < 80:
            result = self._enhance_low_light(result)

        return result

    def _auto_exposure(self, frame: np.ndarray, mean_brightness: float) -> np.ndarray:
        """Auto-adjust exposure based on pre-computed frame brightness."""
        target = 128.0
        if mean_brightness < 80:
            boost = (target - mean_brightness) * 0.3
            return cv2.LUT(frame, self._build_lut_add(boost))
        if mean_brightness > 180:
            reduction = (mean_brightness - target) * 0.2
            return cv2.LUT(frame, self._build_lut_add(-reduction))
        return frame

    def _enhance_low_light(self, frame: np.ndarray) -> np.ndarray:
        """
        Enhance low-light frame using CLAHE + brightness/contrast boost.
        Operates on the L channel in LAB color space for better results.
        Uses pre-built LUTs — no per-frame table allocation.
        """
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        enhanced_l = self.clahe.apply(l_channel)
        enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
        result = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        result = cv2.LUT(result, self._brightness_lut)
        return cv2.LUT(result, self._contrast_lut)

    def undistort_landmark(self, x: float, y: float) -> tuple[float, float]:
        """
        Correct a single landmark's (x, y) for GoPro barrel distortion.

        Args:
            x: Normalized x (0.0-1.0)
            y: Normalized y (0.0-1.0)

        Returns:
            Corrected (x, y)
        """
        if not self.wide_angle_correction:
            return (x, y)

        cx = (x - 0.5) * 2
        cy = (y - 0.5) * 2
        r2 = cx * cx + cy * cy
        factor = 1 + self._distortion_k1 * r2 + self._distortion_k2 * (r2 ** 2)
        x_out = max(0.0, min(1.0, (cx * factor / 2) + 0.5))
        y_out = max(0.0, min(1.0, (cy * factor / 2) + 0.5))
        return (x_out, y_out)

    def update_settings(self, settings):
        """Update processor settings at runtime."""
        self.low_light_mode = settings.get("camera.low_light_mode", False)
        self.clahe_clip = settings.get("camera.clahe_clip_limit", 2.0)
        self.brightness_boost = settings.get("camera.brightness_boost", 15)
        self.contrast_boost = settings.get("camera.contrast_boost", 1.2)
        self.auto_exposure = settings.get("camera.auto_exposure", True)
        self.wide_angle_correction = settings.get("camera.wide_angle_correction", False)
        self.clahe = cv2.createCLAHE(clipLimit=self.clahe_clip, tileGridSize=(8, 8))
        self._brightness_lut = self._build_lut_add(self.brightness_boost)
        self._contrast_lut = self._build_lut_contrast(self.contrast_boost)
