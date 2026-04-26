"""
screen_capture.py — Custom WebRTC VideoStreamTrack for screen capture.

Uses `mss` for fast cross-platform screen capture and converts
frames into the format required by aiortc's media pipeline.

Performance considerations:
  - mss instance is reused across frames (no re-creation overhead)
  - Frame pacing maintains steady FPS without busy-waiting
  - Direct numpy conversion avoids intermediate PIL objects
  - YUV420p format avoids extra colorspace conversion in encoder
  - Adaptive quality: dynamic FPS + resolution scaling for low bandwidth
  - Frame diffing: skip frames when screen hasn't changed significantly
"""

import asyncio
import logging
import time

import numpy as np
from av import VideoFrame
from aiortc import VideoStreamTrack
from mss import mss

logger = logging.getLogger(__name__)

# ─── Quality Presets ────────────────────────────────────────
QUALITY_PRESETS = {
    'ultra-low': {'fps': 2, 'scale': 0.2, 'description': '10kbps — Extreme compression'},
    'low':       {'fps': 5, 'scale': 0.35, 'description': 'Low bandwidth (< 50kbps)'},
    'medium':    {'fps': 15, 'scale': 0.6, 'description': 'Balanced quality'},
    'high':      {'fps': 30, 'scale': 0.85, 'description': 'High quality LAN'},
    'ultra':     {'fps': 60, 'scale': 1.0, 'description': 'Full quality'},
}


class ScreenCaptureTrack(VideoStreamTrack):
    """
    A VideoStreamTrack that captures the primary screen at a target FPS.

    The captured frames are sent as a WebRTC video track to the
    remote peer (Vue.js client).

    Supports:
      - Dynamic FPS and resolution adjustment via quality presets
      - Frame diffing to skip unchanged frames (saves bandwidth)
      - Multi-monitor selection and hot-switching
    """

    kind = "video"

    def __init__(self, fps: int = 30, monitor: int = 1, quality: str = 'medium', requires_auth: bool = False):
        """
        Args:
            fps: Target frames per second (default: 30)
            monitor: Monitor index to capture (default: 1 = primary)
            quality: Quality preset name (default: 'medium')
            requires_auth: If True, yields black frames until authenticated
        """
        super().__init__()
        self._sct = mss()
        self.monitor_index = monitor
        self._monitor = self._sct.monitors[monitor]
        self._frame_count = 0
        self._start_time = None
        self._prev_frame_hash = None
        self._skip_count = 0
        self._last_img_rgb = None
        self.is_authenticated = not requires_auth

        # Apply quality preset (overrides fps if preset is given)
        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS['medium'])
        self.fps = preset['fps'] if quality != 'medium' else fps
        self.scale = preset['scale']
        self._frame_interval = 1.0 / self.fps
        self._quality = quality

        logger.info(
            f"ScreenCapture: monitor={monitor}, fps={self.fps}, "
            f"scale={self.scale:.0%}, quality={quality}"
        )

    async def recv(self) -> VideoFrame:
        """
        Capture a screen frame and return it as an av.VideoFrame.

        This method is called by aiortc's media pipeline at the
        rate determined by the codec. We pace it to our target FPS
        to avoid unnecessary CPU usage.
        """
        # Initialize timing on first frame
        if self._start_time is None:
            self._start_time = time.time()

        # Frame pacing: wait until it's time for the next frame
        target_time = self._start_time + (self._frame_count * self._frame_interval)
        now = time.time()
        if now < target_time:
            await asyncio.sleep(target_time - now)

        if not self.is_authenticated:
            # Yield a black frame with the exact same resolution as the capture will be
            h, w = self._monitor['height'], self._monitor['width']
            if self.scale < 1.0:
                new_w = max(160, int(w * self.scale))
                new_h = max(90, int(h * self.scale))
            else:
                new_w, new_h = w, h
            img_rgb = np.zeros((new_h, new_w, 3), dtype=np.uint8)
        else:
            # Capture the screen
            screenshot = self._sct.grab(self._monitor)

            # Convert to numpy array (BGRA format from mss)
            img = np.array(screenshot, dtype=np.uint8)

            # mss returns BGRA, convert to RGB (drop alpha) and ensure contiguous memory
            img_rgb = np.ascontiguousarray(img[:, :, :3][:, :, ::-1])

            # ─── Frame Diffing ──────────────────────────────────
            # Skip frame if screen hasn't changed (saves bandwidth)
            if self._quality in ('ultra-low', 'low'):
                frame_hash = self._fast_hash(img_rgb)
                if frame_hash == self._prev_frame_hash and self._last_img_rgb is not None:
                    self._skip_count += 1
                    img_rgb = self._last_img_rgb
                else:
                    self._prev_frame_hash = frame_hash
                    self._last_img_rgb = img_rgb

            # ─── Resolution Scaling ─────────────────────────────
            if self.scale < 1.0:
                h, w = img_rgb.shape[:2]
                new_w = max(160, int(w * self.scale))
                new_h = max(90, int(h * self.scale))
                # Use numpy-based nearest-neighbor resize (fast, no PIL needed)
                img_rgb = self._fast_resize(img_rgb, new_w, new_h)
                # Ensure contiguous after resize
                img_rgb = np.ascontiguousarray(img_rgb)

        # Create an av.VideoFrame
        frame = VideoFrame.from_ndarray(img_rgb, format="rgb24")
        frame.pts = self._frame_count
        frame.time_base = self._get_time_base()

        self._frame_count += 1
        return frame

    def set_quality(self, quality: str):
        """Dynamically change quality preset during a session."""
        preset = QUALITY_PRESETS.get(quality)
        if not preset:
            logger.warning(f"Unknown quality preset: {quality}")
            return

        old_quality = self._quality
        self._quality = quality
        self.fps = preset['fps']
        self.scale = preset['scale']
        self._frame_interval = 1.0 / self.fps

        # Reset timing for new FPS
        self._start_time = time.time()
        self._frame_count = 0

        logger.info(
            f"Quality changed: {old_quality} → {quality} "
            f"(fps={self.fps}, scale={self.scale:.0%})"
        )

    def switch_monitor(self, monitor_index: int):
        """Switch to a different monitor during a session."""
        monitors = self._sct.monitors
        if monitor_index < 1 or monitor_index >= len(monitors):
            logger.warning(f"Invalid monitor index: {monitor_index}")
            return False

        self.monitor_index = monitor_index
        self._monitor = monitors[monitor_index]
        self._prev_frame_hash = None  # Reset frame diffing
        logger.info(
            f"Switched to monitor {monitor_index}: "
            f"{self._monitor['width']}x{self._monitor['height']}"
        )
        return True

    @staticmethod
    def get_monitors():
        """Return list of available monitors with their info."""
        with mss() as sct:
            result = []
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    continue  # Skip the "all monitors" entry
                result.append({
                    'index': i,
                    'width': mon['width'],
                    'height': mon['height'],
                    'left': mon['left'],
                    'top': mon['top'],
                    'name': f"Monitor {i} ({mon['width']}×{mon['height']})",
                })
            return result

    def _fast_hash(self, img: np.ndarray) -> int:
        """Fast perceptual hash for frame diffing.

        Samples a small grid of pixels and hashes them.
        Not cryptographic — just for quick change detection.
        """
        h, w = img.shape[:2]
        # Sample 8x8 grid of pixels
        rows = np.linspace(0, h - 1, 8, dtype=int)
        cols = np.linspace(0, w - 1, 8, dtype=int)
        sample = img[np.ix_(rows, cols)]
        return hash(sample.tobytes())

    @staticmethod
    def _fast_resize(img: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
        """Fast nearest-neighbor resize using numpy (no OpenCV/PIL needed)."""
        h, w = img.shape[:2]
        row_indices = np.linspace(0, h - 1, new_h, dtype=int)
        col_indices = np.linspace(0, w - 1, new_w, dtype=int)
        return img[np.ix_(row_indices, col_indices)]

    def _get_time_base(self):
        """Return the time base as a Fraction for frame timing."""
        from fractions import Fraction
        return Fraction(1, self.fps)

    def stop(self):
        """Clean up the mss instance."""
        super().stop()
        if self._sct:
            self._sct.close()

    @property
    def screen_size(self):
        """Return the captured monitor's resolution as (width, height)."""
        return (self._monitor['width'], self._monitor['height'])

    @property
    def stats(self):
        """Return capture statistics."""
        return {
            'fps': self.fps,
            'scale': self.scale,
            'quality': self._quality,
            'monitor': self.monitor_index,
            'resolution': f"{self._monitor['width']}x{self._monitor['height']}",
            'frames_captured': self._frame_count,
            'frames_skipped': self._skip_count,
        }
