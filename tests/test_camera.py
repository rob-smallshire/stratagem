"""The 6502 focus and camera planning match the Python model, frame by frame."""

import random
from dataclasses import replace

import pytest

from conftest import parasite_machine
from stratagem import camera
from stratagem.camera import Camera


@pytest.fixture(scope="module")
def main_machine(game_build):
    return parasite_machine(game_build)[0]


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def _put16(memory, address: int, value: int) -> None:
    memory[address] = value & 0xFF
    memory[address + 1] = value >> 8


def _get16(memory, address: int) -> int:
    return memory[address] | memory[address + 1] << 8


def write_state(memory, labels, state: Camera, direction: int) -> None:
    memory[labels["zp_direction"]] = direction & 0xFF
    _put16(memory, labels["zp_focus_x"], state.focus_x)
    _put16(memory, labels["zp_focus_y"], state.focus_y)
    memory[labels["zp_lead"]] = state.lead & 0xFF
    _put16(memory, labels["zp_camera_x"], state.camera_x)
    _put16(memory, labels["zp_camera_y"], state.camera_y)


def read_state(memory, labels) -> Camera:
    return Camera(
        focus_x=_get16(memory, labels["zp_focus_x"]),
        focus_y=_get16(memory, labels["zp_focus_y"]),
        lead=_signed(memory[labels["zp_lead"]]),
        camera_x=_get16(memory, labels["zp_camera_x"]),
        camera_y=_get16(memory, labels["zp_camera_y"]),
        dx=_signed(memory[labels["zp_plan_dx"]]),
        dy=_signed(memory[labels["zp_plan_dy"]]),
        redraw=memory[labels["zp_redraw"]] != 0,
    )


FOCUS_X_MAX = camera.WORLD_COLUMNS * 2 - 1
FOCUS_Y_MAX = camera.WORLD_ROWS * 8 - 1


def _random_state(rng: random.Random) -> Camera:
    focus_x = rng.choice([0, 1, 2, FOCUS_X_MAX, rng.randrange(FOCUS_X_MAX + 1)])
    focus_y = rng.choice([0, 3, FOCUS_Y_MAX, rng.randrange(FOCUS_Y_MAX + 1)])
    if rng.random() < 0.8:
        # Near the focus, as in play; otherwise anywhere, forcing a redraw.
        camera_x = (focus_x >> 1) - rng.randrange(camera.VIEW_COLUMNS)
        camera_y = (focus_y >> 3) - rng.randrange(camera.VIEW_ROWS)
    else:
        camera_x = rng.randrange(camera.CAMERA_X_MAX + 1)
        camera_y = rng.randrange(camera.CAMERA_Y_MAX + 1)
    return Camera(
        focus_x=focus_x,
        focus_y=focus_y,
        lead=rng.randint(-camera.LEAD_MAX, camera.LEAD_MAX),
        camera_x=max(0, min(camera.CAMERA_X_MAX, camera_x)),
        camera_y=max(0, min(camera.CAMERA_Y_MAX, camera_y)),
    )


def test_camera_matches_model(main_machine, game_build):
    labels = game_build.labels["PARASITE"]
    memory = main_machine.mpu.memory
    rng = random.Random(1988)
    frames = 0
    for _ in range(300):
        state = _random_state(rng)
        direction = 0
        for _ in range(60):
            if rng.random() < 0.15:
                direction = rng.choice([-1, 0, 1])     # held for several frames
            # The focus wanders as a player does: up to 2 pixels and 6 lines a frame.
            focus_x = max(0, min(FOCUS_X_MAX, state.focus_x + direction * rng.randint(0, 2)))
            focus_y = max(0, min(FOCUS_Y_MAX, state.focus_y + rng.randint(-6, 6)))
            state = replace(state, focus_x=focus_x, focus_y=focus_y)
            write_state(memory, labels, state, direction)
            main_machine.call(labels["plan_camera"])
            actual = read_state(memory, labels)
            expected = camera.plan_camera(state, direction)
            assert actual == expected, f"from {state} with direction {direction}"
            state = expected
            frames += 1
    assert frames == 18_000
