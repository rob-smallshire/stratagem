"""The loading screen (stratagem.loading_screen): MODE 1 screen bytes, the
palette and control values for flashing every line, and the dither."""

import numpy as np

from stratagem.loading_screen import (BLACK, BLUE, CYAN, FLASHING, FLASHING_SCHEMES, GREEN, HEIGHT, MAGENTA,
                                      PHYSICAL_LINEAR, RED, SCREEN_SIZE, SCREEN_START, WHITE, WIDTH, YELLOW,
                                      Scheme, address, control_values, decode_mode1, dither, encode_mode1,
                                      flashing, palette_writes, physical, render)


def test_mode1_bytes_hold_four_pixels_interleaved():
    logical = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    logical[0, 0:4] = [3, 0, 0, 0]
    logical[0, 4:8] = [1, 2, 3, 0]
    logical[9, 8:12] = [0, 0, 0, 1]
    screen = encode_mode1(logical)
    assert len(screen) == SCREEN_SIZE == 20 * 1024
    assert screen[0] == 0x88
    assert screen[8] == 0b0110_1010             # bits 7-4 colour bit 1, bits 3-0 colour bit 0
    assert screen[640 + 16 + 1] == 0x01         # row 1, column 2, line 1
    assert address(319, 255) == SCREEN_START + SCREEN_SIZE - 1


def test_screen_bytes_round_trip():
    logical = np.random.default_rng(1).integers(0, 4, (HEIGHT, WIDTH), dtype=np.uint8)
    screen = encode_mode1(logical)
    assert (decode_mode1(screen) == logical).all()
    assert encode_mode1(decode_mode1(screen)) == screen


def test_flashing_colours_show_their_complements_on_odd_lines():
    scheme = flashing(BLACK, CYAN, MAGENTA, YELLOW)
    assert scheme.palette(0) == (BLACK, CYAN, MAGENTA, YELLOW)
    assert scheme.palette(1) == (WHITE, RED, GREEN, BLUE)
    assert Scheme((BLACK, WHITE, FLASHING | CYAN, FLASHING | YELLOW)).name == "KWCY/KWRB"
    lines = scheme.line_palettes()
    assert (lines[0::2] == scheme.palette(0)).all() and (lines[1::2] == scheme.palette(1)).all()
    shown = {c for y in range(2) for c in scheme.palette(y)}
    assert shown == set(range(8))


def test_every_flashing_scheme_shows_all_eight_colours():
    assert len({s.entries for s in FLASHING_SCHEMES}) == 8
    for scheme in FLASHING_SCHEMES:
        assert set(scheme.palette(0)) | set(scheme.palette(1)) == set(range(8))


def test_palette_writes_set_each_logical_colours_four_indices():
    writes = palette_writes(flashing(BLACK, CYAN, MAGENTA, YELLOW))
    assert [w >> 4 for w in writes] == list(range(16))
    by_logical = {0: [0, 1, 4, 5], 1: [2, 3, 6, 7], 2: [8, 9, 12, 13], 3: [10, 11, 14, 15]}
    for logical, entry in enumerate((8 | BLACK, 8 | CYAN, 8 | MAGENTA, 8 | YELLOW)):
        for index in by_logical[logical]:
            assert writes[index] == index << 4 | entry ^ 7
    assert writes[0] == 0x0F and writes[2] == 0x29
    assert control_values() == (0xD8, 0xD9)


def test_render_shows_each_line_in_its_own_palette():
    scheme = flashing(BLACK, RED, GREEN, BLUE)
    logical = np.full((HEIGHT, WIDTH), 1, dtype=np.uint8)
    shown = render(encode_mode1(logical), scheme)
    assert (shown[0::2] == RED).all() and (shown[1::2] == CYAN).all()


def test_dither_makes_up_a_missing_colour_from_the_next_line():
    """Even lines can't show white and odd lines can't show black, nor any
    line grey: between them they average out to the grey asked for."""
    scheme = flashing(BLACK, CYAN, MAGENTA, YELLOW)
    lines = scheme.line_palettes(32)
    for level in (0.2, 0.5, 0.8):
        art = np.full((32, 64, 3), level)
        shown = PHYSICAL_LINEAR[physical(dither(art, lines), lines)]
        assert abs(shown.mean() - level) < 0.03
        assert np.abs(shown.mean(axis=(0, 1)) - level).max() < 0.05


def test_flashing_every_colour_loses_black_and_white():
    """Odd lines can't be darker than a primary, nor even lines lighter than
    a secondary: a sixth and five sixths of the way, at most."""
    lines = flashing(BLACK, CYAN, MAGENTA, YELLOW).line_palettes(32)
    for level, shows in ((0.0, 1 / 6), (1.0, 5 / 6)):
        shown = PHYSICAL_LINEAR[physical(dither(np.full((32, 64, 3), level), lines), lines)]
        assert abs(shown.mean() - shows) < 0.01


# LOADSCR, in Beebium. Beebium draws flashing colours in their first colour
# whatever the flash bit, so the screen is checked by when and what the
# handler writes to the control register, not by the picture.

LINES_PER_FRAME = 312
BLANKING_COLUMNS = range(84, 124)      # CRTC columns (of 128, 80 displayed) safe to switch in


def test_loadscr_shows_the_screen_and_switches_the_flash_bit_each_line(launch_bbc, machine, game_build):
    from conftest import boot_until_ready
    from stratagem.build import GENERATED_DIRPATH
    from stratagem.loading_screen import LOADING_SCHEME

    bbc = launch_bbc(machine)
    labels = boot_until_ready(bbc, game_build, "LOADSCR", command="*RUN LOADSCR")
    screen = (GENERATED_DIRPATH / "loading_screen.bin").read_bytes()
    assert bytes(bbc.memory.address.peek[SCREEN_START:SCREEN_START + SCREEN_SIZE]) == screen
    palette = bbc.video_ula.palette
    assert [palette[index] for index in range(16)] == [p & 15 ^ 7 for p in palette_writes(LOADING_SCHEME)]

    seen = set()
    for _ in range(LINES_PER_FRAME):
        bbc.debugger.run_to(labels["control_written"], skip_current=True)
        crtc, control = bbc.crtc.state, bbc.video_ula.state.control
        line = crtc.row * 8 + crtc.raster
        assert crtc.column in BLANKING_COLUMNS, f"line {line}: written at column {crtc.column}"
        assert control == 0xD8 | (line + 1) % LINES_PER_FRAME & 1, f"line {line}: {control:02X}"
        seen.add(line)
    assert len(seen) == LINES_PER_FRAME
