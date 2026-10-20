"""Unit test for the companion agent's mouse event mapping.

pynput is replaced with a recorder (never injects real input). The recorder mirrors
pynput's macOS controller: press() increments `_click` and stamps it as
kCGMouseEventClickState, release() stamps the current value, None means unstamped.
"""
import importlib.util
import os
import sys
import types

AGENT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "agent_script.py"))


class Button:
    left = "left"
    middle = "middle"
    right = "right"


class RecorderMouse:
    def __init__(self):
        self.events = []
        self._click = None
        self._position = (0, 0)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self.events.append(("move", value))

    def press(self, button):
        if self._click is not None:
            self._click += 1
        self.events.append(("press", button, self._click))

    def release(self, button):
        self.events.append(("release", button, self._click))

    def click(self, button, count=1):
        self.events.append(("click", button, count))

    def scroll(self, dx, dy):
        self.events.append(("scroll", dx, dy))


def load_agent():
    pynput = types.ModuleType("pynput")
    pmouse = types.ModuleType("pynput.mouse")
    pkeyboard = types.ModuleType("pynput.keyboard")
    pmouse.Controller = RecorderMouse
    pmouse.Button = Button
    pkeyboard.Controller = lambda: object()
    pkeyboard.Key = types.SimpleNamespace(**{name: name for name in (
        "enter backspace tab esc space up down left right shift ctrl alt cmd delete home end "
        "page_up page_down caps_lock insert f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12"
    ).split()})
    saved = {name: sys.modules.get(name) for name in ("pynput", "pynput.mouse", "pynput.keyboard", "AppKit")}
    sys.modules.update({"pynput": pynput, "pynput.mouse": pmouse, "pynput.keyboard": pkeyboard})
    sys.modules["AppKit"] = None  # skip real screen detection
    try:
        spec = importlib.util.spec_from_file_location("agent_under_test", AGENT_PATH)
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    assert agent.HAS_PYNPUT and isinstance(agent.mouse, RecorderMouse)
    return agent


def run(agent, platform, events):
    agent.mouse = RecorderMouse()
    real_platform = sys.platform
    sys.platform = platform
    try:
        for event in events:
            assert agent.execute_mouse(event)["status"] == "ok", event
    finally:
        sys.platform = real_platform
    return [e for e in agent.mouse.events if e[0] != "move"]


# What RemoteScreen.vue sends for a double-click (detail 1 then 2), plus the browser's
# synthesized dblclick that older clients also forwarded.
DOUBLE_CLICK = [
    {"type": "mousedown", "x": 0.5, "y": 0.5, "button": 0, "clicks": 1},
    {"type": "mouseup", "x": 0.5, "y": 0.5, "button": 0, "clicks": 1},
    {"type": "mousedown", "x": 0.5, "y": 0.5, "button": 0, "clicks": 2},
    {"type": "mouseup", "x": 0.5, "y": 0.5, "button": 0, "clicks": 2},
    {"type": "dblclick", "x": 0.5, "y": 0.5, "button": 0},
]
RIGHT_CLICK = [
    {"type": "mousedown", "x": 0.3, "y": 0.3, "button": 2, "clicks": 1},
    {"type": "contextmenu", "x": 0.3, "y": 0.3, "button": 2},
    {"type": "mouseup", "x": 0.3, "y": 0.3, "button": 2, "clicks": 1},
]
DRAG = [
    {"type": "mousedown", "x": 0.1, "y": 0.1, "button": 0, "clicks": 1},
    {"type": "mousemove", "x": 0.2, "y": 0.2},
    {"type": "mousemove", "x": 0.3, "y": 0.3},
    {"type": "mouseup", "x": 0.3, "y": 0.3, "button": 0, "clicks": 1},
]


def test_double_click_macos_stamps_click_state():
    agent = load_agent()
    assert run(agent, "darwin", DOUBLE_CLICK) == [
        ("press", "left", 1), ("release", "left", 1),
        ("press", "left", 2), ("release", "left", 2),
    ]
    assert agent.mouse._click is None


def test_double_click_windows_linux_raw_pairs_only():
    agent = load_agent()
    for platform in ("win32", "linux"):
        assert run(agent, platform, DOUBLE_CLICK) == [
            ("press", "left", None), ("release", "left", None),
            ("press", "left", None), ("release", "left", None),
        ]


def test_right_click_is_single_press_release():
    agent = load_agent()
    assert run(agent, "darwin", RIGHT_CLICK) == [("press", "right", 1), ("release", "right", 1)]
    assert run(agent, "win32", RIGHT_CLICK) == [("press", "right", None), ("release", "right", None)]


def test_drag_holds_button_across_moves():
    agent = load_agent()
    agent.mouse = RecorderMouse()
    real_platform = sys.platform
    sys.platform = "darwin"
    try:
        for event in DRAG:
            agent.execute_mouse(event)
    finally:
        sys.platform = real_platform
    kinds = [e[0] for e in agent.mouse.events]
    assert kinds == ["move", "press", "move", "move", "move", "release"]
    assert agent.mouse.events[-1] == ("release", "left", 1)


def test_bad_click_count_falls_back_to_one():
    agent = load_agent()
    events = [{"type": "mousedown", "button": 0, "clicks": "x"}, {"type": "mouseup", "button": 0, "clicks": 99}]
    assert run(agent, "darwin", events) == [("press", "left", 1), ("release", "left", 3)]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✓ {name}")
