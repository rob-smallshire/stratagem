"""The lighting model's rules."""

import numpy as np

from stratagem import lighting
from stratagem.lighting import FULL


def grid(art: str) -> np.ndarray:
    """Transparency from art: '.' open, '#' opaque."""
    return np.array([[c == "." for c in line] for line in art.split()])


def test_daylight_falls_to_the_first_opaque_tile():
    clear = grid("""
        ...
        #..
        ..#
        ...
    """)
    assert lighting.sky_light(clear).tolist() == [[FULL, FULL, FULL], [0, FULL, FULL], [0, FULL, 0], [0, FULL, 0]]


def test_light_spreads_round_corners_but_not_through_walls():
    clear = grid("""
        .....
        ####.
        .....
    """)
    light = np.zeros(clear.shape, dtype=int)
    light[0, 0] = FULL
    lit = lighting.spread(light, clear, 2)
    assert lit[0].tolist() == [15, 13, 11, 9, 7]
    assert lit[1].tolist() == [0, 0, 0, 0, 5]
    assert lit[2].tolist() == [0, 0, 0, 1, 3]


def test_walls_take_light_at_their_faces_and_soak_it_up():
    clear = grid("""
        .####.
    """)
    light = np.zeros(clear.shape, dtype=int)
    light[0, 0] = 12
    soaked = lighting.spread(light, clear, 2, wall_step=4)
    assert soaked[0].tolist() == [12, 12, 8, 4, 0, 0]     # and never out the other side
    faces = lighting.light_surfaces(light, clear)
    assert faces[0].tolist() == [12, 12, 0, 0, 0, 0]


def test_diagonal_light_doesnt_leak_between_corners():
    clear = grid("""
        .#
        #.
    """)
    light = np.zeros(clear.shape, dtype=int)
    light[0, 0] = FULL
    assert lighting.spread(light, clear, 2, 3)[1, 1] == 0


def test_dither_coverage_counts_pixels():
    pixels = np.full((4, 4), 7)
    for level in range(FULL + 1):
        kept = np.count_nonzero(lighting.lit_pixels(pixels, np.full((4, 4), level)))
        assert kept == lighting.coverage(level)
    assert lighting.coverage(FULL) == 16 and lighting.coverage(0) == 0
