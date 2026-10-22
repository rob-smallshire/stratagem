"""Items on the parasite (asm/items.asm): the wood a felled tree drops falls
and is picked up exactly as items.py says, and each packet carries the
items in view (items.shown). The game runs in py65, the host's part played
by FakeHost (test_daylight.ParasiteGame)."""

import pytest

from stratagem import items, sprites
from stratagem.camera import INPUT_ACTION, INPUT_LEFT, INPUT_PICK, INPUT_RIGHT
from stratagem.player import PLAYER_HEIGHT, Player
from stratagem.tiles import PIECES, ROOT
from stratagem.world import HEIGHTS, TRUNKS, generate_tile
from test_daylight import ParasiteGame

TILE_CACHE_SIZE = 32
ITEM_STILL = 0x80           # asm/items.asm: in vy, an item that would stay as it is
ITEMS_UNTOUCHED = 0x80      # in the packet's count of items: nothing redrawn under them
ITEM_BY_MINER = 0x80        # in an item's frame: it meets the miner's sprite, this frame or last


def word(memory, address: int) -> int:
    return memory[address] | memory[address + 1] << 8


def held_items(game) -> list[items.Item]:
    memory, labels = game.memory, game.labels
    return [items.Item(memory[labels["item_x_low"] + i] | memory[labels["item_x_high"] + i] << 8,
                       memory[labels["item_y_low"] + i] | memory[labels["item_y_high"] + i] << 8,
                       memory[labels["item_vy"] + i] & ~ITEM_STILL, memory[labels["item_kind"] + i])
            for i in range(game.byte("item_count"))]


class ItemWatch:
    """Checks each frame's items_step against items.step, from the items,
    the miner and the tile cache as they were when it began; and that every
    item dropped since is one a broken trunk's part dropped."""

    def __init__(self, game):
        self.game = game
        self.after: list[items.Item] = []
        self.dropped = self.picked = 0
        labels = game.labels
        game.machine.hooks[labels["items_step"]] = self.begin
        game.machine.hooks[labels["para_items_moved"]] = self.end

    def begin(self, _mpu):
        game, memory, labels = self.game, self.game.memory, self.game.labels
        self.before = held_items(game)
        assert self.before[:len(self.after)] == self.after, "items changed between frames"
        for item in self.before[len(self.after):]:
            tx, ty = item.x // 8, item.y // 16 // 16
            assert item == items.dropped(tx, ty), item
            assert game.tile_at(tx, ty)[0] not in PIECES, "dropped from a part still standing"
            self.dropped += 1
        self.player = Player(x=word(memory, labels["zp_player_x"]), y=word(memory, labels["zp_player_y"]))
        size = TILE_CACHE_SIZE * TILE_CACHE_SIZE
        materials = list(memory[labels["tile_cache"]:labels["tile_cache"] + size])
        shapes = list(memory[labels["tile_cache_shapes"]:labels["tile_cache_shapes"] + size])
        self.tiles = lambda x, y: (materials[(y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE],
                                   shapes[(y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE])
        left, right, top, bottom = (game.byte(name) for name in ("cached_left", "cached_right", "cached_top",
                                                                 "cached_bottom"))
        self.in_cache = lambda x, y: left <= x <= right and top <= y <= bottom
        self.wood = game.byte("wood")
        self.picking = bool(game.byte("zp_input") & INPUT_PICK)

    def end(self, _mpu):
        expected, picked = items.step(self.before, self.player, self.tiles, self.in_cache, self.picking)
        self.after = held_items(self.game)
        assert self.after == expected
        assert self.game.byte("wood") == self.wood + picked
        self.picked += picked


class PacketCheck:
    """The packet's items, after the chunk to fetch: those in view, each
    marked if it meets the miner's sprite this frame or last; their count
    marked if nothing is redrawn under them."""

    def __init__(self, game):
        self.last = (word(game.memory, game.labels["item_miner_column"]),   # the miner's sprite
                     word(game.memory, game.labels["item_miner_line"]))     # last frame

    def __call__(self, game):
        memory = game.memory
        at = word(memory, game.labels["para_write"])
        count = memory[at] & ~ITEMS_UNTOUCHED
        sent = [tuple(memory[at + 1 + 3 * i:at + 4 + 3 * i]) for i in range(count)]
        redrawn = game.byte("zp_redraw") or game.byte("para_changes") or game.byte("sl_list_count")
        assert bool(memory[at] & ITEMS_UNTOUCHED) == (not redrawn)
        camera_x, camera_y = word(memory, game.labels["zp_camera_x"]), word(memory, game.labels["zp_camera_y"])
        miner = word(memory, game.labels["zp_player_x"]) >> 5, word(memory, game.labels["zp_player_y"]) >> 4
        first = len(sprites.sprite_frames())
        lying = held_items(game)
        expected = []
        for column, line, kind in items.shown(lying, camera_x, camera_y):
            item = next(i for i in lying if (i.x >> 1) - camera_x == column and i.py - camera_y * 8 == line)
            left, right = min(miner[0], self.last[0]), max(miner[0], self.last[0]) + sprites.SPRITE_COLUMNS
            top, bottom = min(miner[1], self.last[1]), max(miner[1], self.last[1]) + PLAYER_HEIGHT
            by = (left < (item.x >> 1) + sprites.SPRITE_COLUMNS and item.x >> 1 < right
                  and top < item.py + items.ITEM_HEIGHT and item.py < bottom)
            expected.append((column, line, first + kind | (ITEM_BY_MINER if by else 0)))
        self.last = miner
        assert sent == expected
        return len(sent)


def test_felled_wood_piles_up_and_is_picked_up():
    """Dig at the tree beside the start: its root and each part of its
    trunk drop a log as they break, which fall and pile up about the miner,
    who passes them by; then, holding P, he walks over them and picks them
    up."""
    from stratagem.build import build
    game = ParasiteGame(build())
    watch = ItemWatch(game)
    check_packet = PacketCheck(game)
    trunk = 127
    assert trunk in TRUNKS
    shown = 0

    def play(frames, inputs):
        nonlocal shown
        for _ in range(frames):
            game.frame(inputs)
            game.host.check_cache()
            shown = max(shown, check_packet(game))

    for _ in range(12):
        play(1, INPUT_LEFT | INPUT_ACTION)
        if watch.dropped:
            break
    assert watch.dropped == 1, "the root"
    play(60, 0)
    ground = HEIGHTS[trunk]
    assert watch.dropped == 1 + TRUNKS[trunk], "the root and each part of the trunk"
    assert watch.picked == 0, "picked up without P"
    lying = held_items(game)
    assert len(lying) == watch.dropped
    assert all(item.vy == 0 for item in lying), "they lie still"
    assert any(item.py + items.ITEM_HEIGHT == ground * 16 for item in lying), "on the ground"
    assert any(item.py + items.ITEM_HEIGHT < ground * 16 for item in lying), "piled up"
    assert not any(a.x < b.x + items.ITEM_WIDTH and b.x < a.x + items.ITEM_WIDTH
                   and a.py < b.py + items.ITEM_HEIGHT and b.py < a.py + items.ITEM_HEIGHT
                   for n, a in enumerate(lying) for b in lying[n + 1:]), "none overlap"
    assert shown == len(lying), "they were in view"
    play(10, INPUT_RIGHT | INPUT_PICK)
    play(40, INPUT_LEFT | INPUT_PICK)
    assert game.byte("item_count") == 0, "not all picked up"
    assert watch.picked == watch.dropped
    assert game.byte("wood") == watch.dropped


@pytest.mark.parametrize("seed", [1988, 1, 2, 3])
def test_logs_dropped_about_pile_and_slide_as_the_model_says(seed):
    """Logs dropped on the slopes round the start, some on one spot, fall,
    pile up and slide exactly as items.py says, the miner standing by."""
    import random
    from stratagem.build import build
    game = ParasiteGame(build())
    watch = ItemWatch(game)
    rng = random.Random(seed)
    left, right = game.byte("cached_left") + 2, game.byte("cached_right") - 2
    open_columns = [tx for tx in range(left, right + 1) if generate_tile(tx, HEIGHTS[tx] - 4)[0] not in PIECES]
    spots = [rng.choice(open_columns) for _ in range(3)]
    slides = 0
    for frame in range(240):
        if frame % 6 == 0 and game.byte("item_count") < items.ITEM_MAX:
            tx = rng.choice(spots) if rng.random() < 0.7 else rng.choice(open_columns)
            game.call("item_drop", a=ROOT, x=tx, y=HEIGHTS[tx] - 4)
        before = held_items(game)
        game.frame(0)
        after = held_items(game)
        slides += sum(1 for a, b in zip(before, after) if a.x != b.x)
    lying = held_items(game)
    assert len(lying) == items.ITEM_MAX
    assert slides >= 4, "too few slides to test"
    assert all(item.vy == 0 for item in lying), "they come to rest"
