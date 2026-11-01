"""Subsidence (docs/building.md): soil held from below only, failing slowly
and by chance, from below upwards. The model the parasite's
asm/subsidence.asm follows exactly, and the subsidence lab runs.

Soil is loose: held by what is under it, never from the side, so it can't
bridge or overhang. Which soil is loose is a rule: all of it, grass
included (grass is soil with grass on it), as the game has it; or, for the
lab, only soil put down.

A loose tile is at risk while the tile under it is empty (air or sky: a
torch, a tree's part or water under it holds it). Soil has no strength
sideways: only a tile directly undermined is at risk, and a cut into a
hillside stands, its face as it was dug.

A tile that fails drops a tile, into the empty one below, as sand does in
some games but slowly and by chance: the soil is kept until it is mined,
and a tunnel through soil fills from above while the ground over it sinks.
It drops as soil (disturbed grass is soil), never onto the miner (it waits
while the tile below overlaps him: `blocked`), and takes two frames, as
the game changes one tile a frame: the tile below becomes soil, then
(`pending`) the tile itself empties; nothing else is rolled for meanwhile.
A tile emptied so is sky if the tile above it is sky (or it is above its
column's surface), otherwise cave: sinking ground shows the sky behind it,
not the black of a cave in the shape of the hill that was (`emptied`). (For the lab, rules
may also wedge soil between solid sides, an arch, or let a face slump;
the game's have neither: GAME_RULES.)

It happens only where the parasite's tile cache is (`bounds`), so that
every tile it reads is a quick look in the cache: a tile outside it is
solid, and not loose; one outside it isn't noted; and one queued that has
left it goes to the back unread, until the miner comes back.

Tiles at risk wait in a queue (QUEUE tiles at most, each once). Each frame
up to CHECKS are taken from its head: one outside the cache goes to the
back; one no longer at risk is dropped; one that can't fail now (the
frame's changed tile taken: `can_fail`) goes to the back unrolled;
otherwise a roll: the random generator stepped 8 times, its 16 bits against the
threshold.
One that survives goes to the back; one that fails drops, and at most one
fails a frame. Every changed tile, the player's
or subsidence's, is noted: the tiles it may have put at risk join the
queue (`note`).

The random generator is the 16-bit Galois LFSR of MBANK's director
(asm/mbank.asm): shift right, and on a carry out EOR the high byte with
&B4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from stratagem.tiles import AIR, BACKGROUND_SKY, GRASS, PASSABLE, SHAPE_FULL, SKY, SOIL, TREE_PARTS, background
from stratagem.world import World, background_bits

ALL_SOIL, PLACED_SOIL = "all soil", "placed soil"
EMPTY = (AIR, SKY)                  # what soil drops into
QUEUE = 64
CHECKS = 2
SLUMP_DROP = 4
ROLL_STEPS = 8
SEED = 0xACE1


@dataclass(frozen=True)
class Rules:
    loose: str = ALL_SOIL           # which soil is loose
    chance: float = 1 / 64          # of failing, at a roll, with no solid side
    arch: float = 2.0               # each solid side divides the chance by 1 + this
    slump: float = 1 / 512          # of failing, at a roll, for a face (0: no slumping)

    def thresholds(self) -> list[int]:
        """The 16-bit thresholds a roll must be under to fail: by solid
        sides (0, 1, 2), then a face's."""
        return [round(0x10000 * self.chance / (1 + self.arch * sides)) for sides in range(3)] + \
            [round(0x10000 * self.slump)]


GAME_RULES = Rules(arch=0, slump=0)     # no strength sideways (decided 2026-11-01)


class Random:
    """MBANK's LFSR."""

    def __init__(self, state: int = SEED):
        self.state = state

    def step(self) -> None:
        carry = self.state & 1
        self.state >>= 1
        if carry:
            self.state ^= 0xB400

    def roll(self) -> int:
        for _ in range(ROLL_STEPS):
            self.step()
        return self.state


def opened(x: int, y: int) -> tuple[int, int]:
    """What a tile is once emptied: sky or cave, by its background."""
    bits = background_bits(x, y)
    return background(bits), SHAPE_FULL | bits


def noted(x: int, y: int, rules: Rules = GAME_RULES) -> list[tuple[int, int]]:
    """The tiles a change at (x, y) may put at risk, in the order noted:
    itself (put down over a drop), and the tile above it (undermined); with
    an arch or slumping, beside it too, and beside it up to a face's height
    above (a drop beside them deepened)."""
    tiles = [(x, y), (x, y - 1)]
    if rules.arch or rules.slump:
        tiles += [(x - 1, y), (x + 1, y)]
    if rules.slump:
        for d in (-1, 1):
            tiles += [(x + d, y + 1 - k) for k in range(SLUMP_DROP + 1) if k != 1]
    return tiles


@dataclass
class Subsidence:
    world: World
    rules: Rules = GAME_RULES
    random: Random = field(default_factory=Random)
    placed: set[tuple[int, int]] = field(default_factory=set)
    queue: list[tuple[int, int]] = field(default_factory=list)
    can_fail: object = None         # () -> bool; None: always
    blocked: object = None          # (x, y) -> bool: the miner is in the tile; None: never
    pending: tuple[int, int] | None = None     # a tile dropped, to be emptied next
    bounds: tuple[int, int, int, int] | None = None    # the tile cache: left, right, top, bottom; None: everywhere
    trees: bool = False             # bring trees down here (the game's support does)
    frame: int = 0
    gone: int = 0

    def cached(self, x: int, y: int) -> bool:
        if self.bounds is None:
            return True
        left, right, top, bottom = self.bounds
        return left <= x <= right and top <= y <= bottom

    def loose(self, x: int, y: int) -> bool:
        if not self.cached(x, y):
            return False
        if self.rules.loose == PLACED_SOIL:
            return (x, y) in self.placed
        return self.world.tile_at(x, y)[0] in (SOIL, GRASS)

    def open(self, x: int, y: int) -> bool:
        return self.cached(x, y) and self.world.tile_at(x, y)[0] in PASSABLE

    def face(self, x: int, y: int) -> bool:
        return bool(self.rules.slump) and any(all(self.open(x + d, y + k) for k in range(SLUMP_DROP))
                                              for d in (-1, 1))

    def empty(self, x: int, y: int) -> bool:
        return self.cached(x, y) and self.world.tile_at(x, y)[0] in EMPTY

    def at_risk(self, x: int, y: int) -> bool:
        return self.loose(x, y) and (self.empty(x, y + 1) or self.face(x, y))

    def note(self, x: int, y: int) -> None:
        """Tile (x, y) changed."""
        for tile in noted(x, y, self.rules):
            if len(self.queue) < QUEUE and tile not in self.queue and self.at_risk(*tile):
                self.queue.append(tile)

    def set_tile(self, x: int, y: int, tile: tuple[int, int]) -> None:
        self.world.set_tile(x, y, tile)
        self.note(x, y)

    def dig(self, x: int, y: int) -> None:
        self.placed.discard((x, y))
        self.set_tile(x, y, opened(x, y))
        if self.trees:
            self.fell_trees(x, y - 1)

    def place(self, x: int, y: int) -> None:
        self.placed.add((x, y))
        self.set_tile(x, y, (SOIL, SHAPE_FULL | background_bits(x, y)))

    def fell_trees(self, x: int, y: int) -> None:
        """A tree whose root has lost its ground comes down, whole (the lab's
        stand-in for the game's support)."""
        stack = [(x, y)]
        while stack:
            tx, ty = stack.pop()
            if self.world.tile_at(tx, ty)[0] in TREE_PARTS:
                self.world.set_tile(tx, ty, opened(tx, ty))
                stack += [(tx, ty - 1), (tx - 1, ty), (tx + 1, ty)]

    def emptied(self, x: int, y: int) -> tuple[int, int]:
        """What a dropped tile leaves: sky if the tile above is (or above
        the surface), otherwise cave."""
        if background_bits(x, y) or (self.cached(x, y - 1) and self.world.tile_at(x, y - 1)[0] == SKY):
            return SKY, SHAPE_FULL | BACKGROUND_SKY
        return AIR, SHAPE_FULL

    def threshold(self, x: int, y: int) -> int:
        thresholds = self.rules.thresholds()
        if self.open(x, y + 1):
            return thresholds[sum(not self.open(x + d, y) for d in (-1, 1))]
        return thresholds[3]

    def step(self) -> tuple[int, int] | None:
        """A frame; returns the tile changed, if one was: a tile dropped
        into, or a tile emptied, completing a drop."""
        self.frame += 1
        if self.pending is not None:
            if self.can_fail is not None and not self.can_fail():
                return None
            x, y = self.pending
            self.pending = None
            if not self.loose(x, y):
                return None             # (mined meanwhile)
            self.placed.discard((x, y))
            self.set_tile(x, y, self.emptied(x, y))
            if self.trees:
                self.fell_trees(x, y - 1)
            return x, y
        for _ in range(min(CHECKS, len(self.queue))):
            x, y = self.queue.pop(0)
            if not self.cached(x, y):
                self.queue.append((x, y))
                continue
            if not self.at_risk(x, y):
                continue
            if self.can_fail is not None and not self.can_fail():
                self.queue.append((x, y))
                continue
            if self.blocked is not None and self.blocked(x, y + 1):
                self.queue.append((x, y))
                continue
            if self.random.roll() < self.threshold(x, y):
                self.gone += 1
                if (x, y) in self.placed:
                    self.placed.add((x, y + 1))
                self.set_tile(x, y + 1, (SOIL, SHAPE_FULL | background_bits(x, y + 1)))
                self.pending = x, y
                return x, y + 1
            self.queue.append((x, y))
        return None


def generate(generated_dirpath) -> None:
    """subsidence.asm: the game's rules, as the parasite's constants: the
    threshold a roll must be under to fail."""
    rules = GAME_RULES
    assert rules.loose == ALL_SOIL and not rules.arch and not rules.slump      # as subsidence.asm has them
    threshold = rules.thresholds()[0]
    assert 0 < threshold < 0x10000
    lines = ["\\ Generated by stratagem.subsidence: do not edit.",
             f"SUBSIDE_QUEUE = {QUEUE}", f"SUBSIDE_CHECKS = {CHECKS}",
             f"SUBSIDE_ROLL_STEPS = {ROLL_STEPS}", f"SUBSIDE_SEED = &{SEED:04X}",
             f"SUBSIDE_THRESHOLD = &{threshold:04X}"]
    (generated_dirpath / "subsidence.asm").write_text("\n".join(lines) + "\n")
