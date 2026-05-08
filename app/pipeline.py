"""Top-level processing pipeline.

    Camera  →  FrameProcessor  →  HandTracker  →  GestureClassifier
                                                       │
                                                       ▼
                                           ModeManager → ActionDispatcher

Owns:
    - the camera capture loop
    - adaptive frame-skipping based on measured FPS
    - resilient camera reconnect with exponential backoff
    - thread management (pipeline runs on its own daemon thread)

The GUI subscribes to callbacks for `frame_ready`, `fps`, and `status` so the
preview window stays decoupled from the vision pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import cv2
import numpy as np

from app.config import Settings
from app.control.action_dispatcher import ActionDispatcher
from app.gesture_engine import GestureClassifier, ModeManager
from app.utils.fps import FPSCounter
from app.vision.hand_tracker import HandTracker

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates capture + tracking + gesture classification + dispatch.

    Designed to be run on a background thread. Callbacks are invoked from
    that same thread; the GUI is responsible for marshalling onto its own
    event loop (e.g. via Qt signals).
    """

    # Adaptive frame skipping: targets a steady processing FPS so we don't
    # backlog frames on slow hardware.
    _TARGET_FPS = 25
    _MIN_SKIP = 1
    _MAX_SKIP = 4

    # Reconnect backoff (seconds).
    _BACKOFF = (1.0, 2.0, 4.0, 8.0)

    def __init__(
        self,
        settings: Settings,
        hand_tracker: HandTracker,
        classifier: GestureClassifier,
        dispatcher: ActionDispatcher,
        mode_manager: ModeManager,
    ) -> None:
        self._settings = settings
        self._tracker = hand_tracker
        self._classifier = classifier
        self._dispatcher = dispatcher
        self._mode_manager = mode_manager

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        self._fps = FPSCounter()
        self._frame_skip = settings.get("camera.frame_skip", 2)
        self._frame_idx = 0

        # Callbacks (set by GUI).
        self.on_frame: Optional[Callable[[np.ndarray], None]] = None
        self.on_fps: Optional[Callable[[float], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_camera_state: Optional[Callable[[str], None]] = None

    # ----- lifecycle -----

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        if not self._open_camera():
            self._notify_status("Camera unavailable")
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="airpoint-pipeline", daemon=True)
        self._thread.start()
        self._notify_camera_state("running")
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._close_camera()
        self._notify_camera_state("stopped")

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ----- camera -----

    def _open_camera(self) -> bool:
        device = self._settings.get("camera.device_index", 0)
        cap = cv2.VideoCapture(device)
        if not cap.isOpened():
            cap.release()
            return False

        res = self._settings.get("camera.resolution", [1280, 720])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
        cap.set(cv2.CAP_PROP_FPS, self._settings.get("camera.fps", 30))
        self._cap = cap
        return True

    def _close_camera(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # pragma: no cover
                pass
            self._cap = None

    def _reconnect_camera(self) -> bool:
        """Try to reopen the camera with exponential backoff."""
        self._close_camera()
        for delay in self._BACKOFF:
            if self._stop.is_set():
                return False
            self._notify_status(f"Camera lost — reconnecting in {delay:.0f}s…")
            self._stop.wait(delay)
            if self._open_camera():
                self._notify_status("Camera reconnected")
                return True
        return False

    # ----- main loop -----

    def _run(self) -> None:
        consec_failures = 0
        try:
            while not self._stop.is_set():
                if self._cap is None:
                    if not self._reconnect_camera():
                        self._notify_status("Camera unavailable")
                        self._notify_camera_state("error")
                        return

                ok, frame = self._cap.read()
                if not ok:
                    consec_failures += 1
                    if consec_failures >= 30:
                        consec_failures = 0
                        if not self._reconnect_camera():
                            self._notify_status("Camera unavailable")
                            self._notify_camera_state("error")
                            return
                    continue

                consec_failures = 0
                fps = self._fps.tick()
                if self.on_fps:
                    self.on_fps(fps)

                # Adaptive frame-skip: bigger skip when we fall behind target.
                self._adapt_skip(fps)
                self._frame_idx = (self._frame_idx + 1) % max(1, self._frame_skip)
                run_detection = self._frame_idx == 0

                # Mirror so users move naturally (right hand = right side).
                frame = cv2.flip(frame, 1)

                if run_detection:
                    annotated, hand_results = self._tracker.process_frame(frame)
                    actions = self._classifier.process(hand_results)
                    if actions:
                        self._dispatcher.dispatch_many(actions)
                    if self.on_frame:
                        self.on_frame(annotated)
                else:
                    if self.on_frame:
                        self.on_frame(frame)
        except Exception as exc:  # pragma: no cover - belt-and-suspenders
            logger.exception("Pipeline crashed: %s", exc)
            self._notify_status(f"Pipeline error: {exc}")
            self._notify_camera_state("error")

    # ----- adaptive frame skipping -----

    def _adapt_skip(self, fps: float) -> None:
        if fps <= 0:
            return
        if fps < self._TARGET_FPS - 5 and self._frame_skip < self._MAX_SKIP:
            self._frame_skip += 1
        elif fps > self._TARGET_FPS + 5 and self._frame_skip > self._MIN_SKIP:
            self._frame_skip -= 1

    # ----- callback helpers -----

    def _notify_status(self, msg: str) -> None:
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def _notify_camera_state(self, state: str) -> None:
        if self.on_camera_state:
            try:
                self.on_camera_state(state)
            except Exception:
                pass
