"""
input_handler.py — Translates remote control events into OS-level input.

Receives mouse/keyboard event data from the WebRTC Data Channel
and executes them on the host machine using pynput.

Events arrive as JSON with relative coordinates (0.0 to 1.0),
which are mapped to absolute screen pixel positions.
"""

import json
import logging
from typing import Tuple

from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

logger = logging.getLogger(__name__)

# Mapping of web key names to pynput Key constants
SPECIAL_KEYS = {
    'Enter': Key.enter,
    'Backspace': Key.backspace,
    'Tab': Key.tab,
    'Escape': Key.esc,
    'Delete': Key.delete,
    'ArrowUp': Key.up,
    'ArrowDown': Key.down,
    'ArrowLeft': Key.left,
    'ArrowRight': Key.right,
    'Home': Key.home,
    'End': Key.end,
    'PageUp': Key.page_up,
    'PageDown': Key.page_down,
    'F1': Key.f1, 'F2': Key.f2, 'F3': Key.f3, 'F4': Key.f4,
    'F5': Key.f5, 'F6': Key.f6, 'F7': Key.f7, 'F8': Key.f8,
    'F9': Key.f9, 'F10': Key.f10, 'F11': Key.f11, 'F12': Key.f12,
    'Control': Key.ctrl_l,
    'Shift': Key.shift_l,
    'Alt': Key.alt_l,
    'Meta': Key.cmd,  # Windows/Command key
    'CapsLock': Key.caps_lock,
    ' ': Key.space,
}

# Mapping of mouse button numbers to pynput Button
MOUSE_BUTTONS = {
    0: Button.left,
    1: Button.middle,
    2: Button.right,
}


class InputHandler:
    """
    Handles remote input events by executing them on the host machine.
    
    All coordinates received are relative (0.0 to 1.0) and are
    converted to absolute screen positions based on screen_size.
    """

    def __init__(self, screen_size: Tuple[int, int]):
        """
        Args:
            screen_size: (width, height) of the captured screen in pixels.
        """
        self.screen_width, self.screen_height = screen_size
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        logger.info(f"InputHandler initialized for screen {self.screen_width}x{self.screen_height}")

    def handle_event(self, raw_data: str):
        """
        Parse and dispatch a control event.
        
        Args:
            raw_data: JSON string from the WebRTC Data Channel.
        """
        try:
            event = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {raw_data[:100]}")
            return

        event_type = event.get('type')

        if event_type in ('mousemove', 'mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu'):
            self._handle_mouse(event)
        elif event_type == 'scroll':
            self._handle_scroll(event)
        elif event_type in ('keydown', 'keyup'):
            self._handle_keyboard(event)
        else:
            logger.debug(f"Unknown event type: {event_type}")

    def _to_absolute(self, x: float, y: float) -> Tuple[int, int]:
        """Convert relative coordinates (0.0-1.0) to absolute screen pixels."""
        abs_x = int(x * self.screen_width)
        abs_y = int(y * self.screen_height)
        # Clamp to screen bounds
        abs_x = max(0, min(self.screen_width - 1, abs_x))
        abs_y = max(0, min(self.screen_height - 1, abs_y))
        return abs_x, abs_y

    def _handle_mouse(self, event: dict):
        """Handle mouse events: move, click, double-click, right-click."""
        x, y = self._to_absolute(event.get('x', 0), event.get('y', 0))
        event_type = event['type']
        button_num = event.get('button', 0)
        button = MOUSE_BUTTONS.get(button_num, Button.left)

        if event_type == 'mousemove':
            self.mouse.position = (x, y)

        elif event_type == 'mousedown':
            self.mouse.position = (x, y)
            self.mouse.press(button)

        elif event_type == 'mouseup':
            self.mouse.position = (x, y)
            self.mouse.release(button)

        elif event_type == 'click':
            self.mouse.position = (x, y)
            self.mouse.click(button, 1)

        elif event_type == 'dblclick':
            self.mouse.position = (x, y)
            self.mouse.click(button, 2)

        elif event_type == 'contextmenu':
            self.mouse.position = (x, y)
            self.mouse.click(Button.right, 1)

    def _handle_scroll(self, event: dict):
        """Handle scroll/wheel events."""
        x, y = self._to_absolute(event.get('x', 0), event.get('y', 0))
        self.mouse.position = (x, y)

        delta_x = event.get('deltaX', 0)
        delta_y = event.get('deltaY', 0)

        # Normalize scroll delta (browsers report varying magnitudes)
        scroll_x = -1 if delta_x > 0 else (1 if delta_x < 0 else 0)
        scroll_y = -1 if delta_y > 0 else (1 if delta_y < 0 else 0)

        if scroll_y != 0:
            self.mouse.scroll(0, scroll_y)
        if scroll_x != 0:
            self.mouse.scroll(scroll_x, 0)

    def _handle_keyboard(self, event: dict):
        """Handle keyboard events: key press and release."""
        key_name = event.get('key', '')
        event_type = event['type']

        # Check for special keys first
        key = SPECIAL_KEYS.get(key_name)

        if key is None:
            if len(key_name) == 1:
                # Regular character key
                key = key_name
            else:
                logger.debug(f"Unmapped key: {key_name}")
                return

        try:
            if event_type == 'keydown':
                self.keyboard.press(key)
            elif event_type == 'keyup':
                self.keyboard.release(key)
        except Exception as e:
            logger.warning(f"Failed to execute key event: {e}")
