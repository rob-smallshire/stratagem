"""Tube prototype 3 (asm/tube_draw.asm): the host draws cells as the parasite
lists them, read straight from the Tube, and what each cell costs the host.

Run with -s to see the costs, in host cycles (2 MHz)."""

from conftest import RUN_TIMEOUT_EMULATED_SECONDS, collect_marks, run_on_tube
from stratagem import lighting

MARKS = 5
LIST_CELLS = 64         # asm/tube_draw.asm
DRAW_SCREEN = 0x3000


def test_tube_draw(tube_bbc, game_build):
    bbc = tube_bbc
    labels = game_build.labels["TUBE_DRAW"]
    host = bbc.memory.address.peek
    para = bbc.connect_coprocessor().memory.address.peek
    run_on_tube(bbc, game_build, "TDRAWH", "TDRAWP")
    cycles = collect_marks(bbc, labels["draw_mark_hit"], labels["draw_mark_id"], MARKS)
    ran = bbc.run_until_or_timeout(lambda: para[labels["dp_done"]] == 0xFF, RUN_TIMEOUT_EMULATED_SECONDS)
    assert ran, "the parasite did not finish"

    graphics = bytes(host[labels["draw_graphics"]:labels["draw_graphics"] + 256])
    masks = lighting.light_masks()
    for n in range(LIST_CELLS):
        cell = graphics[8 * (n & 31):8 * (n & 31) + 8]
        for name, base, mask in (("dim", DRAW_SCREEN + 8 * n, (n % 15) * 16 + 8 * (n & 1)),
                                 ("full", DRAW_SCREEN + 8 * (LIST_CELLS + n), 15 * 16 + 8 * (n & 1))):
            expected = bytes(b & masks[mask + line] for line, b in enumerate(cell))
            assert bytes(host[base:base + 8]) == expected, f"{name} cell {n}"

    mark = cycles[5] - cycles[4]
    one = cycles[2] - cycles[1] - mark
    dim = (cycles[3] - cycles[2] - mark - one) / (LIST_CELLS - 1)
    full = (cycles[4] - cycles[3] - mark - one) / (LIST_CELLS - 1)
    print(f"\n  a list of one cell {one}; each further cell: dim {dim:.1f}, full {full:.1f}")
