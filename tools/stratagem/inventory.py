"""A model of the miner's inventory, as asm/inventory.asm, actions.asm and
items.asm keep it: a count of each kind of thing carried, a binary byte up
to COUNT_MAX, and the kind in hand, which placing puts down.

A tile dug away entirely gives one of the kind its material YIELDS (dug
grass is soil); the hand stays as it was. A tree's part gives nothing
directly: its wood is thrown out as items (items.py), each gathered in
adding one WOOD. Placing puts down the material the kind in hand PLACES;
if none of that kind is left, the hand moves first to the first kind held
that places something, in kind order. A kind in hand that places nothing
(wood, chosen in the pack: pack.py) places nothing. In play, TAB cycles
the hand to the next kind held that places something (cycle).

Planks, torches and the workbench are made (crafting.py). Torches are
placed as blocks are, at most TORCH_MAX in the world (asm/torches.asm), and
the miner starts with STARTING_TORCHES. The workbench is placed as a
piece, and dug it breaks whole, thrown out as an item (items.py); planks
place nothing yet. Pickaxes (TOOLS) are made at the workbench.
"""

from stratagem.tiles import BENCH, GEM, GRASS, ORE, SOIL, STONE, TORCH

(KIND_WOOD, KIND_SOIL, KIND_STONE, KIND_ORE, KIND_GEM, KIND_PLANKS, KIND_TORCH, KIND_BENCH, KIND_WOOD_PICK,
 KIND_STONE_PICK) = range(10)
KIND_COUNT = 10
TOOLS = [KIND_WOOD_PICK, KIND_STONE_PICK]            # kinds held in the tool hand, not placed
TOOL_FIRST = TOOLS[0]
assert TOOLS == list(range(TOOL_FIRST, KIND_COUNT))  # the last kinds
COUNT_MAX = 99
STARTING_TORCHES = 8
TORCH_MAX = 24                      # torches in the world at once

YIELDS = {GRASS: KIND_SOIL, SOIL: KIND_SOIL, STONE: KIND_STONE, ORE: KIND_ORE, GEM: KIND_GEM}
PLACES = {KIND_SOIL: SOIL, KIND_STONE: STONE, KIND_ORE: ORE, KIND_GEM: GEM, KIND_TORCH: TORCH, KIND_BENCH: BENCH}
assert set(YIELDS.values()) <= set(PLACES)
assert KIND_COUNT < 0x80 and max(PLACES.values()) < 0x80     # &FF means none in the tables

EMPTY = (0,) * KIND_COUNT
STARTING = tuple(STARTING_TORCHES if kind == KIND_TORCH else 0 for kind in range(KIND_COUNT))


def gain(counts: tuple[int, ...], kind: int) -> tuple[int, ...]:
    """One more of `kind`, unless there are COUNT_MAX already."""
    if counts[kind] >= COUNT_MAX:
        return counts
    return counts[:kind] + (counts[kind] + 1,) + counts[kind + 1:]


def spend(counts: tuple[int, ...], kind: int) -> tuple[int, ...]:
    """One fewer of `kind`, of which there is at least one."""
    assert counts[kind]
    return counts[:kind] + (counts[kind] - 1,) + counts[kind + 1:]


def cycle(counts: tuple[int, ...], hand: int) -> int:
    """The next kind after the hand, in kind order and round again, that is
    held and places something; the hand if there is none."""
    for step in range(1, KIND_COUNT + 1):
        kind = (hand + step) % KIND_COUNT
        if kind in PLACES and counts[kind]:
            return kind
    return hand


def in_hand(counts: tuple[int, ...], hand: int) -> int | None:
    """The kind placing puts down: the hand, if any of it is left, otherwise
    the first kind held that places something; None if there is none, or
    if the hand places nothing."""
    if hand not in PLACES:
        return None
    if counts[hand]:
        return hand
    for kind in range(KIND_COUNT):
        if kind in PLACES and counts[kind]:
            return kind
    return None

