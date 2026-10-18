"""The 6502 focus and camera planning match the Python model, frame by frame."""

import random

import pytest

from mos6502 import Machine6502
from stratagem import camera
from stratagem.build import read_disc_file
from stratagem.camera import Camera


@pytest.fixture(scope="module")
def main_machine(game_build):
    load_address, data = read_disc_file(game_build.disc_filepath, "MAIN")
    machine = Machine6502()
    machine.load(load_address, data)
    return machine


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def _put16(memory, address: int, value: int) -> None:
    memory[address] = value & 0xFF
    memory[address + 1] = value >> 8


def _get16(memory, address: int) -> int:
    return memory[address] | memory[address + 1] << 8


def write_state(memory, labels, state: Camera, inputs: int) -> None:
    memory[labels["zp_input"]] = inputs
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


def _random_state(rng: random.Random) -> Camera:
    focus_x = rng.choice([0, 1, 2, camera.FOCUS_X_MAX, rng.randrange(camera.FOCUS_X_MAX + 1)])
    focus_y = rng.choice([0, 3, camera.FOCUS_Y_MAX, rng.randrange(camera.FOCUS_Y_MAX + 1)])
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
    labels = game_build.labels["STRATAGEM"]
    memory = main_machine.mpu.memory
    rng = random.Random(1988)
    frames = 0
    for _ in range(300):
        state = _random_state(rng)
        inputs = 0
        for _ in range(60):
            if rng.random() < 0.15:
                inputs = rng.randrange(16)     # held for several frames, as keys are
            write_state(memory, labels, state, inputs)
            main_machine.call(labels["update_focus"])
            main_machine.call(labels["plan_camera"])
            actual = read_state(memory, labels)
            expected = camera.step(state, inputs)
            assert actual == expected, f"from {state} with inputs {inputs}"
            state = expected
            frames += 1
    assert frames == 18_000
