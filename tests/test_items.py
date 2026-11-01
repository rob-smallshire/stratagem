"""Items on the parasite (asm/items.asm): the wood a felled tree throws out
flies, rests and is gathered in exactly as items.py says, and each packet
carries the items in view (items.shown). The game runs in py65, the host's
part played by FakeHost (test_daylight.ParasiteGame)."""

import random

import pytest

from stratagem import items, sprites
from stratagem.camera import INPUT_ACTION, INPUT_LEFT
from stratagem.inventory import KIND_SOIL, KIND_STONE, KIND_WOOD
from stratagem.pack import KEY_CYCLE
from stratagem.player import PLAYER_HEIGHT, Player
from stratagem.tiles import PIECES, ROOT
from stratagem.world import HEIGHTS, TRUNKS, generate_tile
from test_daylight import MAILBOX_KEYS, ParasiteGame

TILE_CACHE_SIZE = 32
ITEMS_UNTOUCHED = 0x80      # in the packet's count of items: nothing redrawn under them
ITEM_BY_MINER = 0x80        # in an item's frame: it meets the miner's sprite, this frame or last


def word(memory, address: int) -> int:
    return memory[address] | memory[address + 1] << 8


def signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def wood(game) -> int:
    """The wood the miner carries."""
    return game.memory[game.labels["inventory"] + KIND_WOOD]


def held_items(game) -> list[items.Item]:
    memory, labels = game.memory, game.labels

    def at(name, i):
        return memory[labels[name] + i]
    return [items.Item(at("item_x_low", i) | at("item_x_high", i) << 8, at("item_y_low", i) | at("item_y_high", i) << 8,
                       signed(at("item_vx", i)), signed(at("item_vy", i)), at("item_state", i), at("item_timer", i),
                       at("item_kind", i))
            for i in range(game.byte("item_count"))]


class ItemWatch:
    """Checks each frame's items_step against items.step, from the items,
    the miner and the tile cache as they were when it began; and that every
    item thrown since is one a broken trunk's part threw, sprayed by the
    count thrown."""

    def __init__(self, game):
        self.game = game
        self.after: list[items.Item] = []
        self.thrown = self.gathered = 0
        self.states = set()
        self.bounced = False
        labels = game.labels
        game.machine.hooks[labels["items_step"]] = self.begin
        game.machine.hooks[labels["para_items_moved"]] = self.end

    def begin(self, _mpu):
        game, memory, labels = self.game, self.game.memory, self.game.labels
        self.before = held_items(game)
        assert self.before[:len(self.after)] == self.after, "items changed between frames"
        new = self.before[len(self.after):]
        count = game.byte("item_thrown") - len(new)
        for n, item in enumerate(new):
            tx, ty = item.px // 8, (item.py + items.ITEM_HEIGHT) // 16 - 1
            assert item == items.thrown(tx, ty, (count + n) % 256), item
            assert game.tile_at(tx, ty)[0] not in PIECES, "thrown from a part still standing"
            self.thrown += 1
        self.player = Player(x=word(memory, labels["zp_player_x"]), y=word(memory, labels["zp_player_y"]))
        size = TILE_CACHE_SIZE * TILE_CACHE_SIZE
        materials = list(memory[labels["tile_cache"]:labels["tile_cache"] + size])
        shapes = list(memory[labels["tile_cache_shapes"]:labels["tile_cache_shapes"] + size])
        self.tiles = lambda x, y: (materials[(y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE],
                                   shapes[(y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE])
        left, right, top, bottom = (game.byte(name) for name in ("cached_left", "cached_right", "cached_top",
                                                                 "cached_bottom"))
        self.in_cache = lambda x, y: left <= x <= right and top <= y <= bottom
        self.wood = wood(game)

    def end(self, _mpu):
        expected, gathered = items.step(self.before, self.player, self.tiles, self.in_cache)
        self.after = held_items(self.game)
        assert self.after == expected
        assert wood(self.game) == self.wood + gathered
        self.gathered += gathered
        self.states |= {item.state for item in self.after}
        self.bounced |= any(b.state == items.FLYING and a.vy > 0 > b.vy for a, b in zip(self.before, self.after))


class PacketCheck:
    """The packet's items, after the chunk to fetch: those in view, each
    marked if it meets the miner's sprite this frame or last, then the hand
    if shown (items.hand_shown), marked so; their count marked if nothing
    is redrawn under them."""

    def __init__(self, game):
        self.hand = items.HandShown(game.byte("hand_last"), game.byte("hand_timer"), game.byte("tool_last"),
                                    game.byte("hand_kind"), bool(game.byte("zp_hand_tool")))
        self.numbers = 0            # frames with a tool's number shown
        self.hand_frames = 0
        self.last = (word(game.memory, game.labels["item_miner_x"]) >> 5,   # the miner's sprite
                     word(game.memory, game.labels["item_miner_y"]) >> 4)   # last frame

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
            item = next(i for i in lying if (i.px >> 1) - camera_x == column and i.py - camera_y * 8 == line)
            left, right = min(miner[0], self.last[0]), max(miner[0], self.last[0]) + sprites.SPRITE_COLUMNS
            top, bottom = min(miner[1], self.last[1]), max(miner[1], self.last[1]) + PLAYER_HEIGHT
            by = (left < (item.px >> 1) + sprites.SPRITE_COLUMNS and item.px >> 1 < right
                  and top < item.py + items.ITEM_HEIGHT and item.py < bottom)
            expected.append((column, line, first + kind | (ITEM_BY_MINER if by else 0)))
        tool = memory[game.labels["belt"] + game.byte("belt_slot")]
        chosen = bool(game.byte("tool_pressed") or game.byte("zp_tool_broke"))
        self.hand = items.show_hand(self.hand, game.byte("hand"), tool, chosen)
        assert game.byte("hand_timer") == self.hand.timer
        hero = Player(x=word(memory, game.labels["zp_player_x"]), y=word(memory, game.labels["zp_player_y"]))
        hand = items.hand_shown(self.hand, hero, camera_x, camera_y, game.byte("belt_slot"))
        for column, line, kind in hand:
            expected.append((column, line, first + kind | ITEM_BY_MINER))
        self.hand_frames += bool(hand)
        self.numbers += len(hand) == 2
        self.last = miner
        assert sent == expected
        return len(sent)


def test_felled_wood_is_thrown_out_and_gathered_in():
    """Dig at the tree beside the start: its root and each part of its
    trunk throw out a log as they break, which fly, bounce, and then are
    gathered in to the miner, who stands by."""
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
        if watch.thrown:
            break
    assert watch.thrown == 1, "the root"
    play(150, 0)
    assert watch.thrown == 1 + TRUNKS[trunk], "the root and each part of the trunk"
    assert game.byte("item_count") == 0, "not all gathered in"
    assert watch.gathered == watch.thrown
    assert wood(game) == watch.thrown
    assert watch.bounced, "none bounced"
    assert items.GATHERING in watch.states
    assert shown >= 3, "too few were in view at once"


def test_the_hand_is_shown_above_the_miner_when_it_changes():
    """TAB cycles the hand from the torches to the stone: it is shown above the
    miner for HAND_FRAMES frames, as items.py says, and then not."""
    from stratagem.build import build
    game = ParasiteGame(build())
    labels = game.labels
    game.memory[labels["inventory"] + KIND_SOIL] = 5          # (carried soil places nothing)
    game.memory[labels["inventory"] + KIND_STONE] = 3
    check_packet = PacketCheck(game)
    for frame in range(items.HAND_FRAMES + 20):
        game.memory[MAILBOX_KEYS] = KEY_CYCLE if frame == 5 else 0
        game.frame(0)
        check_packet(game)
    assert game.byte("hand") == KIND_STONE
    assert check_packet.hand_frames == items.HAND_FRAMES


def test_a_tool_chosen_is_shown_above_the_miner():
    """3 takes the belt's third slot, a wooden pickaxe, into the tool hand:
    it is shown for HAND_FRAMES frames; 3 again shows it again; 1, an empty
    slot, bare hands, shows nothing."""
    from stratagem.build import build
    from stratagem.inventory import KIND_WOOD_PICK
    from test_daylight import MAILBOX_TOOLS
    game = ParasiteGame(build())
    labels = game.labels
    game.memory[labels["belt"] + 2] = KIND_WOOD_PICK
    check_packet = PacketCheck(game)
    again = items.HAND_FRAMES + 10                  # 3 again, the pickaxe in hand: shown again
    empty = again + items.HAND_FRAMES + 5           # 1, an empty slot: bare hands, shown
    for frame in range(3 * items.HAND_FRAMES + 40):
        game.memory[MAILBOX_TOOLS] = 3 if frame in (5, again) else 1 if frame == empty else 0
        game.frame(0)
        check_packet(game)
    assert game.byte("belt_slot") == 0
    assert check_packet.hand_frames == 3 * items.HAND_FRAMES
    assert check_packet.numbers == 3 * items.HAND_FRAMES      # each a tool, with its number


def test_0_shows_the_tool_in_use_again():
    """0 shows the tool in use, with its slot's number, and chooses
    nothing."""
    from stratagem.build import build
    from stratagem.inventory import KIND_STONE_PICK
    from test_daylight import MAILBOX_TOOLS
    game = ParasiteGame(build())
    labels = game.labels
    game.memory[labels["belt"] + 4] = KIND_STONE_PICK
    game.memory[labels["inventory"] + KIND_STONE_PICK] = 1
    check_packet = PacketCheck(game)
    for frame in range(2 * items.HAND_FRAMES + 20):
        game.memory[MAILBOX_TOOLS] = 5 if frame == 2 else 10 if frame == items.HAND_FRAMES + 10 else 0
        game.frame(0)
        check_packet(game)
    assert game.byte("belt_slot") == 4
    assert check_packet.numbers == 2 * items.HAND_FRAMES


def test_a_tool_that_breaks_is_shown():
    """A wooden pickaxe one dig from breaking, in the tool hand: digging
    down, it breaks, its belt slot is empty, and bare hands are shown, as
    items.show_hand says."""
    from stratagem import actions
    from stratagem.build import build
    from stratagem.camera import INPUT_ACTION, INPUT_DOWN
    from stratagem.inventory import KIND_WOOD_PICK
    from test_daylight import MAILBOX_TOOLS
    game = ParasiteGame(build())
    labels = game.labels
    game.memory[labels["belt"] + 1] = KIND_WOOD_PICK
    game.memory[labels["belt_wear"] + 1] = actions.DURABILITY[KIND_WOOD_PICK] - 1
    game.memory[MAILBOX_TOOLS] = 2
    game.frame(0)
    game.memory[MAILBOX_TOOLS] = 0
    for frame in range(items.HAND_FRAMES + 5):          # the pickaxe chosen, shown, and gone
        game.frame(0)
    check_packet = PacketCheck(game)
    broke = None
    for frame in range(30):
        game.frame(INPUT_DOWN | INPUT_ACTION)
        check_packet(game)
        if broke is None and game.memory[labels["belt"] + 1] == items.NO_TOOL:
            broke = frame
            assert game.byte("hand_kind") == items.NO_TOOL
    assert broke is not None, "the pickaxe didn't break"
    assert check_packet.hand_frames >= 25, "what's in use wasn't shown"


@pytest.mark.parametrize("seed", [1988, 1, 2, 3])
def test_logs_thrown_about_fly_rest_and_gather_as_the_model_says(seed):
    """Logs thrown from the slopes round the start fly, bounce, rest and are
    gathered in exactly as items.py says, the miner standing by."""
    from stratagem.build import build
    game = ParasiteGame(build())
    watch = ItemWatch(game)
    rng = random.Random(seed)
    left, right = game.byte("cached_left") + 2, game.byte("cached_right") - 2
    spots = [(tx, HEIGHTS[tx] - up) for tx in range(left, right + 1) for up in range(1, 5)
             if generate_tile(tx, HEIGHTS[tx] - up)[0] not in PIECES]
    for frame in range(200):
        if frame % 5 == 0 and frame < 120 and game.byte("item_count") < items.ITEM_MAX:
            tx, ty = rng.choice(spots)
            game.call("item_drop", a=ROOT, x=tx, y=ty)
        game.frame(0)
    assert watch.thrown >= 15
    assert watch.bounced, "none bounced"
    assert {items.RESTING, items.GATHERING} <= watch.states
    assert game.byte("item_count") == 0, "not all gathered in"
    assert watch.gathered == watch.thrown
