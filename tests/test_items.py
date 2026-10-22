"""Items on the parasite (asm/items.asm): the wood a felled tree drops falls
and is picked up exactly as items.py says, and each packet carries the
items in view (items.shown). The game runs in py65, the host's part played
by FakeHost (test_daylight.ParasiteGame)."""

from stratagem import items, sprites
from stratagem.camera import INPUT_ACTION, INPUT_LEFT, INPUT_RIGHT
from stratagem.player import Player
from stratagem.tiles import PIECES
from stratagem.world import HEIGHTS, TRUNKS
from test_daylight import ParasiteGame

TILE_CACHE_SIZE = 32
ITEM_RESTING = 0x80         # asm/items.asm: an item lying where it would land
ITEMS_UNTOUCHED = 0x80      # in the packet's count of items: nothing redrawn under them


def word(memory, address: int) -> int:
    return memory[address] | memory[address + 1] << 8


def held_items(game) -> list[items.Item]:
    memory, labels = game.memory, game.labels
    return [items.Item(memory[labels["item_x_low"] + i] | memory[labels["item_x_high"] + i] << 8,
                       memory[labels["item_y_low"] + i] | memory[labels["item_y_high"] + i] << 8,
                       memory[labels["item_vy"] + i] & ~ITEM_RESTING, memory[labels["item_kind"] + i])
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

    def end(self, _mpu):
        expected, picked = items.step(self.before, self.player, self.tiles, self.in_cache)
        self.after = held_items(self.game)
        assert self.after == expected
        assert self.game.byte("wood") == self.wood + picked
        self.picked += picked


def check_packet(game):
    """The packet's items, after the chunk to fetch: those in view; their
    count marked if nothing is redrawn under them."""
    memory = game.memory
    at = word(memory, game.labels["para_write"])
    count = memory[at] & ~ITEMS_UNTOUCHED
    sent = [tuple(memory[at + 1 + 3 * i:at + 4 + 3 * i]) for i in range(count)]
    redrawn = game.byte("zp_redraw") or game.byte("para_changes") or game.byte("sl_list_count")
    assert bool(memory[at] & ITEMS_UNTOUCHED) == (not redrawn)
    camera_x, camera_y = word(memory, game.labels["zp_camera_x"]), word(memory, game.labels["zp_camera_y"])
    first = len(sprites.sprite_frames())
    shown = [(column, line, first + kind) for column, line, kind in items.shown(held_items(game), camera_x, camera_y)]
    assert sent == shown
    return len(sent)


def test_felled_wood_falls_and_is_picked_up():
    """Dig at the tree beside the start, and step back: its root and each
    part of its trunk drop a log as they break, which fall to the ground,
    where the miner, walking left over them, picks them up."""
    from stratagem.build import build
    game = ParasiteGame(build())
    watch = ItemWatch(game)
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
    play(20, INPUT_RIGHT)
    play(60, 0)
    ground = HEIGHTS[trunk]
    assert watch.dropped == 1 + TRUNKS[trunk], "the root and each part of the trunk"
    lying = held_items(game)
    assert len(lying) == watch.dropped
    assert all(item.py + items.ITEM_HEIGHT == ground * 16 and item.vy == 0 for item in lying), \
        "they lie on the ground"
    assert shown == watch.dropped, "they were in view"
    play(40, INPUT_LEFT)
    assert game.byte("item_count") == 0, "not all picked up"
    assert watch.picked == watch.dropped
    assert game.byte("wood") == watch.dropped
