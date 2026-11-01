"""Subsidence (stratagem.subsidence, asm/subsidence.asm): the model's soil
held from below only, failing slowly from below; and the parasite's,
frame by frame as the model's, in py65."""

from conftest import NOON
from test_daylight import ParasiteGame

from stratagem import subsidence
from stratagem.subsidence import QUEUE, Subsidence, opened
from stratagem.actions import overlaps_player
from stratagem.player import Player
from stratagem.tiles import PASSABLE, SKY, SOIL, STONE, TREE_PARTS
from stratagem.world import HEIGHTS, World, background_bits

FRAMES = 3000


def settle(model: Subsidence, frames: int = 30_000) -> None:
    for _ in range(frames):
        if not model.queue and model.pending is None:
            return
        model.step()
    raise AssertionError("it didn't settle")


def rock_row(world: World, x: int) -> int:
    y = HEIGHTS[x] + 1
    while world.tile_at(x, y)[0] != STONE:
        y += 1
    return y


def test_a_tunnel_through_the_soil_fills_and_the_ground_sinks_to_it():
    """The soil over a tunnel two high drops into it, a tile at a time: the
    tunnel fills, and each column's top two tiles are sky. (Soil left
    undisturbed over a natural cave stands, until something near it
    changes.)"""
    model = Subsidence(World())
    for x in range(64, 76):
        model.dig(x, HEIGHTS[x] + 3)
        model.dig(x, HEIGHTS[x] + 2)
    settle(model)
    for x in range(64, 76):
        rock = rock_row(World(), x)
        if any(World().tile_at(x, y)[0] in PASSABLE for y in range(HEIGHTS[x], rock)):
            continue                # (a natural cave in its soil, undisturbed: it stands)
        assert [model.world.tile_at(x, y)[0] for y in (HEIGHTS[x], HEIGHTS[x] + 1)] == [SKY, SKY], x
        assert all(model.world.tile_at(x, y)[0] == SOIL for y in range(HEIGHTS[x] + 2, rock)), x


def test_a_tunnel_in_the_rock_stands_and_the_hills_stay():
    model = Subsidence(World())
    for x in range(64, 76):
        rock = rock_row(model.world, x)
        model.dig(x, rock + 2)
        model.dig(x, rock + 1)
    settle(model)
    assert all(model.world.tile_at(x, y) == World().tile_at(x, y)
               for x in range(60, 80) for y in range(HEIGHTS[x] - 4, rock_row(World(), x) + 1))


def test_a_cut_into_a_hillside_stands():
    """Soil has no strength sideways, and needs none: a face dug into it
    stands, and only what's undermined falls."""
    model = Subsidence(World())
    x = 74
    for y in range(HEIGHTS[x], rock_row(model.world, x)):
        model.dig(x, y)
    for y in range(HEIGHTS[x + 1], rock_row(model.world, x + 1)):
        model.dig(x + 1, y)
    settle(model)
    assert all(model.world.tile_at(c, y) == World().tile_at(c, y)
               for c in (x - 2, x - 1, x + 2, x + 3) for y in range(HEIGHTS[c], rock_row(World(), c)))


def test_soil_put_down_over_a_drop_falls_to_its_bottom():
    model = Subsidence(World())
    x = 71
    bottom = rock_row(model.world, x + 1) + 2
    for column in (x + 1, x + 2):
        for y in range(HEIGHTS[column], bottom):
            model.dig(column, y)
    model.place(x + 1, HEIGHTS[x] - 1)
    settle(model)
    assert model.open(x + 1, HEIGHTS[x] - 1), "a bridge of soil stood"
    assert model.world.tile_at(x + 1, bottom - 1)[0] == SOIL, "it didn't come to rest at the bottom"


def test_the_queue_holds_each_tile_once_and_no_more_than_it_can():
    model = Subsidence(World())
    for x in range(40, 140):
        model.dig(x, HEIGHTS[x] + 2)
    assert len(model.queue) == QUEUE == len(set(model.queue))


def test_the_parasites_subsidence_is_the_models(game_build):
    """A tunnel dug through the soil beside the miner (by change_target, as
    digging does): each frame, the parasite's queue, random generator and
    world are the model's."""
    game = ParasiteGame(game_build)
    labels, memory = game.labels, game.memory
    for _ in range(5):
        game.frame(0)
    px = (memory[labels["zp_player_x"]] | memory[labels["zp_player_x"] + 1] << 8) >> 7
    left = next(x for x in range(px + 1, px + 8)
                if not any(World().tile_at(c, y)[0] in TREE_PARTS for c in range(x - 1, x + 4)
                           for y in range(HEIGHTS[c] - 8, HEIGHTS[c])))
    def bounds():
        return tuple(game.byte(n) for n in ("cached_left", "cached_right", "cached_top", "cached_bottom"))

    model = Subsidence(World(), bounds=bounds())
    for x in range(left, left + 3):
        for y in (HEIGHTS[x] + 3, HEIGHTS[x] + 2):
            material, shape = opened(x, y)
            memory[labels["target_x"]], memory[labels["target_y"]] = x, y
            memory[labels["zp_world_new_shape"]] = shape
            game.call("change_target", a=material)
            model.dig(x, y)
    memory[labels["redraw_tile"]] = 0           # (the digs drawn, as far as the test is concerned)

    def queue():
        head, count = game.byte("subside_head"), game.byte("subside_count")
        return [(memory[labels["subside_queue_x"] + (head + i) % QUEUE],
                 memory[labels["subside_queue_y"] + (head + i) % QUEUE]) for i in range(count)]

    def random_state():
        return memory[labels["subside_random"]] | memory[labels["subside_random"] + 1] << 8

    assert queue() == model.queue and random_state() == model.random.state
    failed = 0
    for frame in range(FRAMES):
        free = game.byte("redraw_tile") == 0
        model.can_fail = lambda: free
        model.bounds = bounds()
        player = Player(x=memory[labels["zp_player_x"]] | memory[labels["zp_player_x"] + 1] << 8,
                        y=memory[labels["zp_player_y"]] | memory[labels["zp_player_y"] + 1] << 8)
        model.blocked = lambda x, y: overlaps_player(player, x, y)
        changed = model.step()
        game.frame(0)
        assert queue() == model.queue, f"frame {frame}: the queue"
        assert random_state() == model.random.state, f"frame {frame}: the random generator"
        if changed is not None:
            failed += 1
            assert game.tile_at(*changed) == model.world.tile_at(*changed), f"frame {frame}: {changed}"
        if not model.queue and model.pending is None:
            break
    print(f"\n{failed} tiles failed over {frame + 1} frames")
    assert failed >= 5, f"only {failed} tiles changed"
    assert not model.queue, "it didn't settle"
    assert all(game.tile_at(x, y) == model.world.tile_at(x, y) for x in range(left - 1, left + 4)
               for y in range(HEIGHTS[x] - 2, HEIGHTS[x] + 6)), "the world isn't the model's"


assert subsidence.GAME_RULES.loose == subsidence.ALL_SOIL and background_bits and NOON
