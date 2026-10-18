"""A model of the camera in asm/main.asm: a focus point moved by the keys,
and a camera that follows it, exactly as the 6502 does it.

The focus is in pixels (x, 0-2047) and lines (y, 0-4095). The camera is the
world cell at the top left of the view: x in columns (two pixels), y in
character rows (eight lines).

The camera keeps the focus inside a window around the centre of the view
(a dead zone), so small movements don't scroll. Horizontally the window
shifts against the direction of travel by a lead that eases towards
LEAD_MAX, to show more of what lies ahead, as Exile's scrolling velocity
does. The camera moves up to MAX_STEP_X columns a frame, more the further
the focus is outside the window, and one row a frame vertically (the hidden
row can take only one new row a frame). If the focus leaves the view
altogether, as when teleporting, the view is redrawn centred on it.

The focus marker is MARKER_COLUMNS wide and MARKER_LINES high, with its top
left at the focus.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from stratagem.screen import VIEW_COLUMNS, VIEW_ROWS

WORLD_COLUMNS = 1024
WORLD_ROWS = 512
CAMERA_X_MAX = WORLD_COLUMNS - VIEW_COLUMNS          # 960
CAMERA_Y_MAX = WORLD_ROWS - VIEW_ROWS                # 481

MARKER_COLUMNS = 2
MARKER_LINES = 16
FOCUS_X_MAX = WORLD_COLUMNS * 2 - MARKER_COLUMNS * 2  # 2044
FOCUS_Y_MAX = WORLD_ROWS * 8 - MARKER_LINES           # 4080
FOCUS_SPEED_X = 2    # pixels a frame
FOCUS_SPEED_Y = 4    # lines a frame

WINDOW_LEFT = 24     # columns: the window is WINDOW_LEFT <= x < WINDOW_RIGHT
WINDOW_RIGHT = 40
WINDOW_TOP = 11      # rows: WINDOW_TOP <= y < WINDOW_BOTTOM
WINDOW_BOTTOM = 20
LEAD_MAX = 12        # columns
MAX_STEP_X = 2       # columns a frame
CENTRE_X = 32        # where a redraw puts the focus
CENTRE_Y = 15

INPUT_LEFT, INPUT_RIGHT, INPUT_UP, INPUT_DOWN = 1, 2, 4, 8


@dataclass(frozen=True)
class Camera:
    focus_x: int
    focus_y: int
    lead: int = 0
    camera_x: int = 0
    camera_y: int = 0
    dx: int = 0          # the last step's movement, applied at the next flip
    dy: int = 0
    redraw: bool = False


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _direction(inputs: int, negative: int, positive: int) -> int:
    return (1 if inputs & positive else 0) - (1 if inputs & negative else 0)


def update_focus(state: Camera, inputs: int) -> Camera:
    vx = _direction(inputs, INPUT_LEFT, INPUT_RIGHT)
    vy = _direction(inputs, INPUT_UP, INPUT_DOWN)
    focus_x = _clamp(state.focus_x + FOCUS_SPEED_X * vx, 0, FOCUS_X_MAX)
    focus_y = _clamp(state.focus_y + FOCUS_SPEED_Y * vy, 0, FOCUS_Y_MAX)
    lead = state.lead
    target = vx * LEAD_MAX
    if lead < target:
        lead += 1
    elif lead > target:
        lead -= 1
    return replace(state, focus_x=focus_x, focus_y=focus_y, lead=lead)


def plan_camera(state: Camera) -> Camera:
    column = state.focus_x >> 1
    row = state.focus_y >> 3
    x = column - state.camera_x
    y = row - state.camera_y
    if not (0 <= x < VIEW_COLUMNS and 0 <= y < VIEW_ROWS):
        return replace(
            state,
            camera_x=_clamp(column - CENTRE_X, 0, CAMERA_X_MAX),
            camera_y=_clamp(row - CENTRE_Y, 0, CAMERA_Y_MAX),
            dx=0, dy=0, redraw=True,
        )
    left = WINDOW_LEFT - state.lead
    right = WINDOW_RIGHT - state.lead
    if x < left:
        dx = -min(MAX_STEP_X, (left - x + 3) >> 2)
    elif x >= right:
        dx = min(MAX_STEP_X, (x - right + 4) >> 2)
    else:
        dx = 0
    if y < WINDOW_TOP:
        dy = -1
    elif y >= WINDOW_BOTTOM:
        dy = 1
    else:
        dy = 0
    camera_x = _clamp(state.camera_x + dx, 0, CAMERA_X_MAX)
    camera_y = _clamp(state.camera_y + dy, 0, CAMERA_Y_MAX)
    return replace(state, camera_x=camera_x, camera_y=camera_y,
                   dx=camera_x - state.camera_x, dy=camera_y - state.camera_y, redraw=False)


def step(state: Camera, inputs: int) -> Camera:
    """One frame: move the focus by the inputs, then plan the camera."""
    return plan_camera(update_focus(state, inputs))


def marker_screen_position(state: Camera) -> tuple[int, int]:
    """The marker's view column and line."""
    return (state.focus_x >> 1) - state.camera_x, state.focus_y - state.camera_y * 8
