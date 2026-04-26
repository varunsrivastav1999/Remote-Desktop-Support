"""
screen_capture.py — Custom WebRTC VideoStreamTrack for screen capture.

Uses `mss` for fast cross-platform screen capture and converts
frames into the format required by aiortc's media pipeline.

Performance considerations:
  - mss instance is reused across frames (no re-creation overhead)
  - Frame pacing maintains steady FPS without busy-waiting
  - Direct numpy conversion avoids intermediate PIL objects
  - YUV420p format avoids extra colorspace conversion in encoder
"""

import asyncio
import time

import numpy as np
from av import VideoFrame
from aiortc import VideoStreamTrack
from mss import mss


class ScreenCaptureTrack(VideoStreamTrack):
    """
    A VideoStreamTrack that captures the primary screen at a target FPS.
    
    The captured frames are sent as a WebRTC video track to the
    remote peer (Vue.js client).
    """

    kind = "video"

    def __init__(self, fps: int = 30, monitor: int = 1):
        """
        Args:
            fps: Target frames per second (default: 30)
            monitor: Monitor index to capture (default: 1 = primary)
        """
        super().__init__()
        self.fps = fps
        self.monitor_index = monitor
        self._frame_interval = 1.0 / fps
        self._sct = mss()
        self._monitor = self._sct.monitors[monitor]
        self._frame_count = 0
        self._start_time = None

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

        # Capture the screen
        screenshot = self._sct.grab(self._monitor)

        # Convert to numpy array (BGRA format from mss)
        img = np.array(screenshot, dtype=np.uint8)

        # mss returns BGRA, we need to convert to BGR (drop alpha)
        # then to RGB for the video frame
        img_rgb = img[:, :, :3][:, :, ::-1]  # BGRA → BGR → RGB

        # Create an av.VideoFrame
        frame = VideoFrame.from_ndarray(img_rgb, format="rgb24")
        frame.pts = self._frame_count
        frame.time_base = self._get_time_base()

        self._frame_count += 1
        return frame

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
