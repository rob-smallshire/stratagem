"""The sprites' frames, the player's and the items' (items.py):
placeholder pixel art, in the sprite colour group (logical colours 0-7),
where colour 0 is transparent.

Each frame is PLAYER_WIDTH x PLAYER_HEIGHT pixels, three bytes wide. It is
stored as SPRITE_BYTES mask bytes then SPRITE_BYTES data bytes, byte
(line * 3 + column); the renderer draws each byte as
(screen AND mask) OR data, but leaves the screen's pixels in the sprite
colour group as they are (drawn_byte): those of pieces in front
(tiles.PIECE_FRONT), and of sprites drawn first, which stand in front of
those drawn after.
"""

from __future__ import annotations

from stratagem.inventory import KIND_COUNT, KIND_GEM, KIND_ORE, KIND_SOIL, KIND_STONE
from stratagem.items import ITEM_HEIGHT, ITEM_WIDTH, WOOD
from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH, Player
from stratagem.screen import mode2_byte

SPRITE_COLUMNS = PLAYER_WIDTH // 2
SPRITE_BYTES = SPRITE_COLUMNS * PLAYER_HEIGHT     # 72
assert ITEM_WIDTH == PLAYER_WIDTH       # drawn by the same code, three bytes wide
ITEM_BYTES = SPRITE_COLUMNS * ITEM_HEIGHT       # 18
LEFT_PIXEL_BITS = 0xAA
RIGHT_PIXEL_BITS = 0x55

_COLOURS = {".": 0, "R": 1, "G": 2, "Y": 3, "B": 4, "M": 5, "C": 6, "W": 7}

_HEAD_AND_BODY = """
..RRR.
.RRRRY
.RRRRY
RRRRRR
.WWWW.
.WWBW.
.WWWW.
..WW..
.CCCC.
CCCCCC
CCCCCC
CCCCCW
CCCCCW
.CCCC.
.CCCC.
.YYYY.
.BBBB.
.BBBB.
.BBBB.
"""

_LEGS = {
    "stand": """
.B..B.
.B..B.
.B..B.
.RR.RR
.RR.RR
""",
    "walk1": """
.B..B.
B....B
B....B
RR..RR
RR..RR
""",
    "walk2": """
..BB..
..BB..
..BB..
..RRR.
..RRR.
""",
    "jump": """
.BBBB.
.B..B.
.RR.RR
.RR.RR
......
""",
}

# Each kind of item (items.py, the inventory's kinds), lying on the ground
# or shown above the miner as the hand: a log, its cut end showing its
# rings; a clod of soil; a chunk of stone (white, black being clear); one
# of ore; a gem.
_ITEMS = {
    WOOD: """
RRRRY.
RRRYYY
RRRYRY
RRRYYY
RRRRY.
""",
    KIND_SOIL: """
.RRYR.
RRRRRY
RYRRRR
RRRRYR
.RRRR.
""",
    KIND_STONE: """
.WWWW.
WWBWWW
WWWWBW
WBWWWW
.WWWW.
""",
    KIND_ORE: """
.WWWW.
WYYWWW
WWYYBW
WBWYYW
.WWWW.
""",
    KIND_GEM: """
..CC..
.CMMC.
CMMMMC
.CMMC.
..CC..
""",
}
assert sorted(_ITEMS) == list(range(KIND_COUNT))

POSES = ["stand", "walk1", "walk2", "jump"]
STAND, WALK1, WALK2, JUMP = range(len(POSES))
LEFT_FACING = len(POSES)    # frames LEFT_FACING onwards face left


def _rows(art: str) -> list[list[int]]:
    return [[_COLOURS[c] for c in line[:PLAYER_WIDTH]] for line in art.split()]


def frame_pixels(pose: str, facing_left: bool) -> list[list[int]]:
    rows = _rows(_HEAD_AND_BODY) + _rows(_LEGS[pose])
    assert len(rows) == PLAYER_HEIGHT and all(len(row) == PLAYER_WIDTH for row in rows), pose
    return [row[::-1] for row in rows] if facing_left else rows


def item_pixels(kind: int) -> list[list[int]]:
    rows = [[_COLOURS[c] for c in line] for line in _ITEMS[kind].split()]
    assert len(rows) == ITEM_HEIGHT and all(len(row) == ITEM_WIDTH for row in rows), kind
    return rows


def encode_frame(pixels: list[list[int]]) -> bytes:
    masks, data = bytearray(), bytearray()
    for row in pixels:
        for column in range(SPRITE_COLUMNS):
            left, right = row[2 * column], row[2 * column + 1]
            masks.append((LEFT_PIXEL_BITS if left == 0 else 0) | (RIGHT_PIXEL_BITS if right == 0 else 0))
            data.append(mode2_byte(left, right))
    return bytes(masks + data)


def drawable(under: int) -> int:
    """The bits of a screen byte that a sprite may be drawn over: those of
    its pixels in the tile colour group (colour bit 3, bits 7 and 6)."""
    return (LEFT_PIXEL_BITS if under & 0x80 else 0) | (RIGHT_PIXEL_BITS if under & 0x40 else 0)


def drawn_byte(under: int, mask: int, data: int) -> int:
    """A sprite's byte drawn over the screen byte `under`: the renderer's
    (under AND mask) OR data where under's pixel is drawable, else under's."""
    keep = drawable(under)
    return under ^ ((under ^ (under & mask | data)) & keep)


def sprite_frames() -> list[bytes]:
    """Every frame's mask and data, right-facing poses then left-facing."""
    return [encode_frame(frame_pixels(pose, facing_left)) for facing_left in (False, True) for pose in POSES]


def item_frames() -> list[bytes]:
    """Each kind of item's frame, its mask and data, by kind."""
    return [encode_frame(item_pixels(kind)) for kind in sorted(_ITEMS)]


def frame_for(player: Player) -> int:
    if not player.on_ground:
        pose = JUMP
    elif player.vx == 0:
        pose = STAND
    else:
        pose = WALK1 + (player.px >> 2 & 1)
    return pose + (LEFT_FACING if player.facing < 0 else 0)
