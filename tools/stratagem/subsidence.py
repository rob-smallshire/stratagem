"""Subsidence (docs/building.md): soil held from below only, failing slowly
and by chance, from below upwards, a model to try before building.

Soil is loose: held by what is under it, never from the side, so it can't
bridge or overhang. Which soil is loose is the choice under test: only
soil put down by the player (natural soil anchored, as terrain is today),
or all of it, grass included (grass is soil with grass on it).

A loose tile is at risk while the tile under it is open (passable). Each
frame, up to `checks` tiles at risk are rolled for, each failing with
probability `chance`, less where it is wedged between solid neighbours
(an arch: `chance` divided by 1 + `arch` for each solid side). A tile that
fails is gone (dust: nothing falls, nothing is gathered), which puts the
tile above it at risk, and the tiles beside it lose a side. So subsidence
starts from below and climbs, slowly; soil can stand unsupported for a
while; and the work is a fixed few rolls a frame, however much is at risk.
At most `falls` tiles fail in a frame (each is a changed tile to send).

A tree standing on soil that fails comes down at once (the game's support
does that, a piece at a time; here, whole, as pieces aren't the subject).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from stratagem.tiles import GRASS, PASSABLE, SHAPE_FULL, SOIL, TREE_PARTS, background
from stratagem.world import World, background_bits

ALL_SOIL, PLACED_SOIL = "all soil", "placed soil"


@dataclass(frozen=True)
class Rules:
    loose: str = ALL_SOIL           # which soil is loose
    chance: float = 1 / 64          # of failing, at a roll, with no solid side
    arch: float = 2.0               # each solid side divides the chance by 1 + this
    checks: int = 4                 # rolls a frame
    falls: int = 2                  # failures a frame, at most
    slump: float = 0.0              # of failing, at a roll, for an exposed face (below)
    slump_drop: int = 4             # an exposed face: open beside it for so many tiles down


def opened(x: int, y: int) -> tuple[int, int]:
    """What a tile is once emptied: sky or cave, by its background."""
    bits = background_bits(x, y)
    return background(bits), SHAPE_FULL | bits


@dataclass
class Subsidence:
    world: World
    rules: Rules
    seed: int = 1
    placed: set[tuple[int, int]] = field(default_factory=set)
    at_risk: list[tuple[int, int]] = field(default_factory=list)
    frame: int = 0
    gone: int = 0

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def loose(self, x: int, y: int) -> bool:
        material = self.world.tile_at(x, y)[0]
        if self.rules.loose == PLACED_SOIL:
            return (x, y) in self.placed
        return material in (SOIL, GRASS)

    def open(self, x: int, y: int) -> bool:
        return self.world.tile_at(x, y)[0] in PASSABLE

    def exposed(self, x: int, y: int) -> bool:
        """A face: open beside it for slump_drop tiles down, steeper than
        any step of the hills as generated (3 tiles at most), so it slumps
        if slumping is on, until no drop beside it is so deep."""
        return self.rules.slump > 0 and any(all(self.open(x + d, y + k) for k in range(self.rules.slump_drop))
                                            for d in (-1, 1))

    def at_risk_here(self, x: int, y: int) -> bool:
        return self.loose(x, y) and (self.open(x, y + 1) or self.exposed(x, y))

    def place(self, x: int, y: int) -> None:
        self.world.set_tile(x, y, (SOIL, SHAPE_FULL | background_bits(x, y)))
        self.placed.add((x, y))
        self.note(x, y)

    def dig(self, x: int, y: int) -> None:
        """Empty a tile (the player digging it), noting what's now at risk."""
        self.world.set_tile(x, y, opened(x, y))
        self.placed.discard((x, y))
        self.note(x, y - 1)
        self.fell_trees(x, y - 1)

    def note(self, x: int, y: int) -> None:
        """Tile (x, y), opened (or its tile below), may have put those
        around it at risk: above it, and beside it up to a face's height
        above (a drop beside them deepened)."""
        around = [(x, y), (x, y - 1), (x - 1, y), (x + 1, y)]
        if self.rules.slump:
            around += [(x + d, y + 1 - k) for d in (-1, 1) for k in range(self.rules.slump_drop + 1)]
        for tx, ty in around:
            if self.at_risk_here(tx, ty) and (tx, ty) not in self.at_risk:
                self.at_risk.append((tx, ty))

    def fell_trees(self, x: int, y: int) -> None:
        """A tree whose root has lost its ground comes down, whole."""
        if self.world.tile_at(x, y)[0] not in TREE_PARTS:
            return
        stack = [(x, y)]
        while stack:
            tx, ty = stack.pop()
            if self.world.tile_at(tx, ty)[0] in TREE_PARTS:
                self.world.set_tile(tx, ty, opened(tx, ty))
                stack += [(tx, ty - 1), (tx - 1, ty), (tx + 1, ty)]

    def sides(self, x: int, y: int) -> int:
        return sum(not self.open(x + d, y) for d in (-1, 1))

    def step(self) -> int:
        """A frame: up to `checks` rolls; returns the tiles that failed."""
        self.frame += 1
        failed = 0
        for _ in range(min(self.rules.checks, len(self.at_risk))):
            if failed >= self.rules.falls:
                break
            x, y = self.at_risk.pop(0)
            if not self.at_risk_here(x, y):
                continue                        # held again, or gone
            if self.open(x, y + 1):
                chance = self.rules.chance / (1 + self.rules.arch * self.sides(x, y))
            else:
                chance = self.rules.slump
            if self.rng.random() < chance:
                self.world.set_tile(x, y, opened(x, y))
                self.placed.discard((x, y))
                self.gone += 1
                failed += 1
                self.fell_trees(x, y - 1)
                self.note(x, y - 1)
                self.note(x - 1, y)
                self.note(x + 1, y)
            else:
                self.at_risk.append((x, y))     # still at risk: rolled again later
        return failed

