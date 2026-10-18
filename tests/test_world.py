"""The 6502 world generator matches its Python model, tile for tile."""

import pytest

from mos6502 import Machine6502
from stratagem.build import read_disc_file
from stratagem.world import WORLD_SIZE, tile_at


@pytest.fixture(scope="module")
def world_machine(game_build):
    load_address, data = read_disc_file(game_build.disc_filepath, "WORLD")
    machine = Machine6502()
    machine.load(load_address, data)
    return machine


def test_tile_at_matches_model_everywhere(world_machine, game_build):
    tile_at_address = game_build.labels["STRATAGEM"]["tile_at"]
    mismatches = []
    for y in range(WORLD_SIZE):
        for x in range(WORLD_SIZE):
            mpu = world_machine.call(tile_at_address, x=x, y=y).mpu
            if (mpu.a, mpu.x, mpu.y) != (tile_at(x, y), x, y):
                mismatches.append(((x, y), (mpu.a, mpu.x, mpu.y), tile_at(x, y)))
    assert mismatches[:10] == []
