"""Hand tracking using MediaPipe Tasks Vision API (v0.10+)."""

import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Optional
from pathlib import Path

from app.config import Settings
from app.vision.frame_processor import FrameProcessor

MODEL_NAME = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


class HandTracker:
    """Real-time hand landmark detection using MediaPipe Tasks API."""

    _CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17),
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model_path = self._get_or_download_model()
        self.frame_processor = FrameProcessor(settings)

        base_options = python.BaseOptions(model_asset_path=str(self._model_path))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=settings.get("hand_tracking.max_num_hands", 2),
            min_hand_detection_confidence=settings.get(
                "hand_tracking.min_detection_confidence", 0.6
            ),
            min_hand_presence_confidence=settings.get(
                "hand_tracking.min_tracking_confidence", 0.5
            ),
            min_tracking_confidence=settings.get(
                "hand_tracking.min_tracking_confidence", 0.5
            ),
        )

        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self._start_ms = int(time.time() * 1000)

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list]:
        """
        Process a single frame for hand detection.

        Args:
            frame: BGR image from webcam

        Returns:
            Tuple of (annotated_frame, list_of_hand_results)
        """
        # Pre-process frame (low-light enhancement, GoPro correction)
        processed = self.frame_processor.process(frame)

        rgb_frame = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int(time.time() * 1000) - self._start_ms
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        hand_results = []

        if result.hand_landmarks:
            for landmarks, handedness in zip(
                result.hand_landmarks, result.handedness
            ):
                self._draw_landmarks(frame, landmarks)

                landmarks_list = []
                for lm in landmarks:
                    # Correct for GoPro wide-angle distortion
                    cx, cy = self.frame_processor.undistort_landmark(lm.x, lm.y)
                    landmarks_list.append((cx, cy, lm.z))

                hand_results.append({
                    "landmarks": landmarks_list,
                    "label": handedness[0].category_name,
                    "score": handedness[0].score,
                })

        return frame, hand_results

    def _draw_landmarks(self, frame: np.ndarray, landmarks):
        """Draw hand landmarks on frame."""
        h, w, _ = frame.shape

        for start, end in self._CONNECTIONS:
            if start < len(landmarks) and end < len(landmarks):
                pt1 = (int(landmarks[start].x * w), int(landmarks[start].y * h))
                pt2 = (int(landmarks[end].x * w), int(landmarks[end].y * h))
                cv2.line(frame, pt1, pt2, (0, 255, 0), 1)

        for lm in landmarks:
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 2, (0, 0, 255), -1)

    def get_finger_tip(self, hand_result: dict, finger_index: int) -> tuple[float, float]:
        if not hand_result.get("landmarks"):
            return (0.0, 0.0)
        landmarks = hand_result["landmarks"]
        if finger_index < len(landmarks):
            return (landmarks[finger_index][0], landmarks[finger_index][1])
        return (0.0, 0.0)

    def get_landmark(self, hand_result: dict, landmark_index: int) -> tuple[float, float, float]:
        if hand_result.get("landmarks") and landmark_index < len(hand_result["landmarks"]):
            return hand_result["landmarks"][landmark_index]
        return (0.0, 0.0, 0.0)

    def calculate_distance(self, point1: tuple, point2: tuple) -> float:
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(point1, point2)))

    def close(self):
        self.landmarker.close()

    def _get_or_download_model(self) -> Path:
        cache_dir = Path.home() / ".cache" / "airpoint" / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        model_path = cache_dir / MODEL_NAME

        if not model_path.exists():
            print(f"Downloading hand tracking model to {model_path}...")
            import urllib.request
            urllib.request.urlretrieve(MODEL_URL, str(model_path))
            print("Model downloaded successfully.")

        return model_path
