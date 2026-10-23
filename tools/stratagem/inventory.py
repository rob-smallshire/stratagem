"""A model of the miner's inventory, as asm/inventory.asm, actions.asm and
items.asm keep it: a count of each kind of thing carried, a binary byte up
to COUNT_MAX, and the kind in hand, which placing puts down.

A tile dug away entirely gives one of the kind its material YIELDS (dug
grass is soil), and puts that kind in hand. A tree's part gives nothing
directly: its wood is thrown out as items (items.py), each gathered in
adding one WOOD. Placing puts down the material the kind in hand PLACES;
if none of that kind is left, the hand moves first to the first kind held
that places something, in kind order. (Choosing the hand comes later.)
"""

from stratagem.tiles import GEM, GRASS, ORE, SOIL, STONE

KIND_WOOD, KIND_SOIL, KIND_STONE, KIND_ORE, KIND_GEM = range(5)
KIND_COUNT = 5
COUNT_MAX = 99

YIELDS = {GRASS: KIND_SOIL, SOIL: KIND_SOIL, STONE: KIND_STONE, ORE: KIND_ORE, GEM: KIND_GEM}
PLACES = {KIND_SOIL: SOIL, KIND_STONE: STONE, KIND_ORE: ORE, KIND_GEM: GEM}
assert set(YIELDS.values()) <= set(PLACES)
assert KIND_COUNT < 0x80 and max(PLACES.values()) < 0x80     # &FF means none in the tables

EMPTY = (0,) * KIND_COUNT


def gain(counts: tuple[int, ...], kind: int) -> tuple[int, ...]:
    """One more of `kind`, unless there are COUNT_MAX already."""
    if counts[kind] >= COUNT_MAX:
        return counts
    return counts[:kind] + (counts[kind] + 1,) + counts[kind + 1:]


def spend(counts: tuple[int, ...], kind: int) -> tuple[int, ...]:
    """One fewer of `kind`, of which there is at least one."""
    assert counts[kind]
    return counts[:kind] + (counts[kind] - 1,) + counts[kind + 1:]


def in_hand(counts: tuple[int, ...], hand: int) -> int | None:
    """The kind placing puts down: the hand, if any of it is left, otherwise
    the first kind held that places something; None if there is none."""
    if counts[hand]:
        return hand
    for kind in range(KIND_COUNT):
        if kind in PLACES and counts[kind]:
            return kind
    return None

