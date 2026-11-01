"""Subsidence (stratagem.subsidence, asm/subsidence.asm): the model's soil
held from below only, failing slowly from below; and the parasite's,
frame by frame as the model's, in py65."""

from conftest import NOON
from test_daylight import ParasiteGame

from stratagem import subsidence
from stratagem.subsidence import QUEUE, Subsidence, opened
from stratagem.tiles import PASSABLE, STONE, TREE_PARTS
from stratagem.world import HEIGHTS, World, background_bits

FRAMES = 3000


def settle(model: Subsidence, frames: int = 30_000) -> None:
    for _ in range(frames):
        if not model.queue:
            return
        model.step()
    raise AssertionError("it didn't settle")


def rock_row(world: World, x: int) -> int:
    y = HEIGHTS[x] + 1
    while world.tile_at(x, y)[0] != STONE:
        y += 1
    return y


def test_a_tunnel_through_the_soil_subsides_to_the_sky():
    model = Subsidence(World())
    for x in range(64, 76):
        model.dig(x, HEIGHTS[x] + 3)
        model.dig(x, HEIGHTS[x] + 2)
    settle(model)
    assert all(model.open(x, y) for x in range(64, 76) for y in range(HEIGHTS[x], HEIGHTS[x] + 4))


def test_a_tunnel_in_the_rock_stands_and_the_hills_stay():
    model = Subsidence(World())
    for x in range(64, 76):
        rock = rock_row(model.world, x)
        model.dig(x, rock + 2)
        model.dig(x, rock + 1)
    settle(model)
    assert all(model.world.tile_at(x, rock_row(World(), x))[0] == STONE for x in range(64, 76))
    # (Near the hill's top, at 65-68, the tunnel opens on a natural cave
    # under thin soil, which slumps a little.)
    assert all(model.world.tile_at(x, y) == World().tile_at(x, y)
               for x in range(70, 76) for y in range(HEIGHTS[x], rock_row(World(), x)))


def test_soil_put_down_over_a_drop_falls():
    model = Subsidence(World())
    x = 71
    for column in (x + 1, x + 2):
        for y in range(HEIGHTS[column], rock_row(model.world, column) + 2):
            model.dig(column, y)
    model.place(x + 1, HEIGHTS[x] - 1)
    settle(model)
    assert model.open(x + 1, HEIGHTS[x] - 1), "a bridge of soil stood"


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
        gone = model.step()
        game.frame(0)
        assert queue() == model.queue, f"frame {frame}: the queue"
        assert random_state() == model.random.state, f"frame {frame}: the random generator"
        if gone is not None:
            failed += 1
            assert game.tile_at(*gone)[0] in PASSABLE, f"frame {frame}: {gone} didn't fail"
        if not model.queue:
            break
    print(f"\n{failed} tiles failed over {frame + 1} frames")
    assert failed >= 5, f"only {failed} tiles failed"
    assert not model.queue, "it didn't settle"


assert subsidence.GAME_RULES.loose == subsidence.ALL_SOIL and background_bits and NOON
