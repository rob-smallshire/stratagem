"""A model of crafting (asm/crafting.asm on the parasite), exactly as the
6502 does it: the grid, the recipes and the recipe book
(docs/inventory-and-crafting.md, Making).

The grid is GRID_MAX cells square, by rows; each cell holds a kind or
EMPTY. A station gives the grid's size: in the hand, 2 x 2, its top left
cells (T Y / G H). Putting a kind in a cell takes one from its count, and
taking it out gives it back, so the grid's contents are always the
ingredients of what's made.

A recipe is a shape: rows of cells, a kind or EMPTY each. The grid
matches a recipe if, trimmed to its rows and columns with anything in
them, it is the recipe's shape, cell for cell (not mirrored), and the
recipe can be made at the station. Making gives the recipe's count of what
it makes, and lays the shape out again from the counts, cell by cell, as
far as they go. The recipe book remembers each recipe made (a bit each),
and COPY lays out the next one in it.
"""

from __future__ import annotations

from dataclasses import dataclass

from stratagem.inventory import (KIND_BENCH, KIND_COUNT, KIND_GEM, KIND_ORE, KIND_PLANKS, KIND_SOIL, KIND_STONE,
                                 KIND_TORCH, KIND_WOOD, gain, spend)

GRID_MAX = 3
GRID_CELLS = GRID_MAX * GRID_MAX
EMPTY = 0xFF
EMPTY_GRID = (EMPTY,) * GRID_CELLS
assert KIND_COUNT < EMPTY

STATION_HAND = 0
GRID_SIZES = {STATION_HAND: 2}

LETTERS = {"W": KIND_WOOD, "D": KIND_SOIL, "S": KIND_STONE, "O": KIND_ORE, "G": KIND_GEM, "P": KIND_PLANKS,
           ".": EMPTY}


@dataclass(frozen=True)
class Recipe:
    shape: str              # rows of LETTERS, "/" between rows
    makes: int
    count: int
    station: int = STATION_HAND

    @property
    def rows(self) -> list[list[int]]:
        return [[LETTERS[c] for c in row] for row in self.shape.split("/")]


RECIPES = [
    Recipe("W", KIND_PLANKS, 4),
    Recipe("O/W", KIND_TORCH, 2),
    Recipe("PP/PP", KIND_BENCH, 1),
]
assert len(RECIPES) <= 8                # the book is a byte of bits
for _recipe in RECIPES:
    _rows = _recipe.rows
    assert all(len(row) == len(_rows[0]) for row in _rows) and len(_rows) <= GRID_MAX and len(_rows[0]) <= GRID_MAX
    assert any(c != EMPTY for c in _rows[0]) and any(c != EMPTY for c in _rows[-1])       # trimmed
    assert any(row[0] != EMPTY for row in _rows) and any(row[-1] != EMPTY for row in _rows)
    assert len(_rows) <= GRID_SIZES[_recipe.station] and len(_rows[0]) <= GRID_SIZES[_recipe.station]


def in_grid(cell: int, station: int) -> bool:
    """Whether the cell is in the station's grid."""
    size = GRID_SIZES[station]
    return cell % GRID_MAX < size and cell // GRID_MAX < size


def trimmed(grid: tuple[int, ...]) -> list[list[int]]:
    """The grid's rows and columns with anything in them."""
    used = [cell for cell in range(GRID_CELLS) if grid[cell] != EMPTY]
    if not used:
        return []
    top, bottom = min(c // GRID_MAX for c in used), max(c // GRID_MAX for c in used)
    left, right = min(c % GRID_MAX for c in used), max(c % GRID_MAX for c in used)
    return [[grid[row * GRID_MAX + column] for column in range(left, right + 1)] for row in range(top, bottom + 1)]


def match(grid: tuple[int, ...], station: int) -> int | None:
    """The recipe the grid lays out, if any can be made at the station."""
    shape = trimmed(grid)
    for index, recipe in enumerate(RECIPES):
        if recipe.station <= station and recipe.rows == shape:
            return index
    return None


def put(counts: tuple[int, ...], grid: tuple[int, ...], cell: int, brush: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """A cell's key: the brush's kind into the cell, from its count; the
    same kind back out of it; or another kind back out and the brush's in,
    if there is one to put."""
    held = grid[cell]
    if held != EMPTY:
        counts = gain(counts, held)
        grid = grid[:cell] + (EMPTY,) + grid[cell + 1:]
        if held == brush:
            return counts, grid
    if counts[brush]:
        counts = spend(counts, brush)
        grid = grid[:cell] + (brush,) + grid[cell + 1:]
    return counts, grid


def clear(counts: tuple[int, ...], grid: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """DELETE: everything in the grid back to the counts."""
    for kind in grid:
        if kind != EMPTY:
            counts = gain(counts, kind)
    return counts, EMPTY_GRID


def lay_out(counts: tuple[int, ...], rows: list[list[int]]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """An empty grid laid out with a shape from its top left, each cell from
    the counts, left empty if its kind has run out."""
    grid = list(EMPTY_GRID)
    for row, kinds in enumerate(rows):
        for column, kind in enumerate(kinds):
            if kind != EMPTY and counts[kind]:
                counts = spend(counts, kind)
                grid[row * GRID_MAX + column] = kind
    return counts, tuple(grid)


def make(counts: tuple[int, ...], grid: tuple[int, ...], book: int, station: int
         ) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    """RETURN: if the grid matches a recipe, make it, put it in the book,
    and lay its shape out again from the counts. Returns the counts, the
    grid and the book."""
    index = match(grid, station)
    if index is None:
        return counts, grid, book
    recipe = RECIPES[index]
    for _ in range(recipe.count):
        counts = gain(counts, recipe.makes)
    counts, grid = lay_out(counts, recipe.rows)
    return counts, grid, book | 1 << index


def copy(counts: tuple[int, ...], grid: tuple[int, ...], book: int, last: int, station: int
         ) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    """COPY: the grid emptied, and the next recipe in the book after the one
    last copied (round again) that the station makes laid out from the
    counts. Returns the counts, the grid and the recipe copied (`last` if
    there's none)."""
    for step in range(1, len(RECIPES) + 1):
        index = (last + step) % len(RECIPES)
        if book & 1 << index and RECIPES[index].station <= station:
            counts, grid = clear(counts, grid)
            counts, grid = lay_out(counts, RECIPES[index].rows)
            return counts, grid, index
    return counts, grid, last
