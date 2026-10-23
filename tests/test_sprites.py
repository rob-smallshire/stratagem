"""The host's sprite drawing (sprite_draw and sprite_undo in asm/render.asm),
in py65: a sprite is drawn as sprites.drawn_byte says, behind the screen's
pixels in the sprite colour group (pieces in front, and sprites drawn
first), and removed again. Run with -s to see what drawing costs."""

import random

from mos6502 import Machine6502
from stratagem import sprites
from stratagem.build import read_disc_file
from stratagem.player import PLAYER_HEIGHT
from stratagem.screen import CELL_BYTES, ROW_BYTES, SCREEN_END, SCREEN_START, wrap


def renderer(game_build):
    machine = Machine6502()
    machine.load(*read_disc_file(game_build.disc_filepath, "RENDER"))
    return machine, game_build.labels["HOST"]


def addresses(top: int, height: int) -> list[int]:
    """The screen addresses of a sprite's bytes, line by line, with its top
    line at `top`."""
    cell = top & ~7
    return [wrap(cell + ((top & 7) + line >> 3) * ROW_BYTES + column * CELL_BYTES) + ((top & 7) + line & 7)
            for line in range(height) for column in range(sprites.SPRITE_COLUMNS)]


def draw(machine, labels, top: int, frame: int) -> int:
    """Draw frame `frame` at `top`; returns the cycles taken."""
    memory = machine.mpu.memory
    memory[labels["zp_sprite_address"]] = top & 0xFF
    memory[labels["zp_sprite_address"] + 1] = top >> 8
    memory[labels["zp_sprite_frame"]] = frame
    save = labels["sprite_save"]
    before = machine.mpu.processorCycles
    machine.call(labels["sprite_draw"], a=save & 0xFF, x=save >> 8)
    return machine.mpu.processorCycles - before


def test_sprites_are_drawn_behind_the_sprite_colour_group(game_build):
    machine, labels = renderer(game_build)
    memory = machine.mpu.memory
    frame = sprites.sprite_frames()[0]
    rng = random.Random(1)
    top = SCREEN_END - ROW_BYTES + 5            # across the screen's wrap
    under = addresses(top, PLAYER_HEIGHT)
    cycles = {}
    for name, choose in (("all tiles", lambda: rng.randrange(0xC0, 0x100)),
                         ("some in front", lambda: rng.randrange(0x100)),
                         ("all in front", lambda: rng.randrange(0x40))):
        before = {address: choose() for address in under}
        for address, byte in before.items():
            memory[address] = byte
        cycles[name] = draw(machine, labels, top, 0)
        for i, address in enumerate(under):
            expected = sprites.drawn_byte(before[address], frame[i], frame[sprites.SPRITE_BYTES + i])
            assert memory[address] == expected, (name, hex(address))
        machine.call(labels["render_restore"])
        assert all(memory[address] == byte for address, byte in before.items()), "not restored"
    assert all(SCREEN_START <= address < SCREEN_END for address in under)
    print("\ndrawing the miner's sprite on the host: " + ", ".join(f"{n} {c} cycles" for n, c in cycles.items()))


def test_drawn_byte_keeps_the_sprite_colour_group():
    for under in range(0x100):
        for mask, data in ((0, 0xFF), (0xAA, 0x55), (0x55, 0x2A)):
            drawn = sprites.drawn_byte(under, mask, data)
            for bits, colour_bit in ((sprites.LEFT_PIXEL_BITS, 0x80), (sprites.RIGHT_PIXEL_BITS, 0x40)):
                if under & colour_bit:
                    assert drawn & bits == (under & mask | data) & bits
                else:
                    assert drawn & bits == under & bits
