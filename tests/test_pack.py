"""The pack screen (pack.py): on the parasite, P opens and closes it, the
game pausing meanwhile, and the arrow keys move the hand, each frame's
packet carrying what the panel shows (py65, test_daylight.ParasiteGame);
on the host, render_pack draws the panel (py65); and in the game, the
panel is drawn, the hand chosen and the view redrawn on closing
(Beebium)."""

import random

import pytest

from conftest import RUN_TIMEOUT_EMULATED_SECONDS
from mos6502 import Machine6502
from stratagem import inventory, pack, sprites
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.inventory import KIND_COUNT
from stratagem.pack import INPUT_PACK, KEY_CYCLE, Pack
from stratagem.screen import SCREEN_END, SCREEN_START
from test_daylight import (MAILBOX_FRAME, MAILBOX_INPUT, MAILBOX_KEYS, PACKET_PACK, PACKET_PACK_DRAW, PACKET_PACK_MOVED,
                           PACKET_REDRAW, ParasiteGame)

INPUTS = [0, 0, INPUT_PACK, INPUT_LEFT, INPUT_RIGHT, INPUT_UP, INPUT_DOWN, INPUT_LEFT | INPUT_RIGHT,
          INPUT_PACK | INPUT_RIGHT, INPUT_RIGHT | INPUT_DOWN]


def test_the_hand_moves_across_the_kinds_shown():
    counts = (3, 0, 12, 0, 99, 0, 0, 0)
    assert pack.shown(counts, inventory.KIND_SOIL) == [0, 1, 2, 4]
    opened, hand = pack.step(Pack(), counts, 1, INPUT_PACK)
    assert opened.open and opened.draw and hand == 1
    moved, hand = pack.step(opened, counts, hand, INPUT_RIGHT)
    assert moved.moved and not moved.draw and hand == 2
    held, hand = pack.step(moved, counts, hand, INPUT_RIGHT)      # held, not pressed again
    assert not held.moved and hand == 2
    closed, hand = pack.step(held, counts, hand, INPUT_PACK)
    assert not closed.open and closed.closed and hand == 2


def test_tab_cycles_the_hand_through_kinds_placed():
    counts = (7, 3, 0, 2, 0, 0, 0, 0)       # wood, soil, no stone, ore, nothing else
    assert inventory.cycle(counts, inventory.KIND_SOIL) == inventory.KIND_ORE
    assert inventory.cycle(counts, inventory.KIND_ORE) == inventory.KIND_SOIL      # round again, past the wood
    assert inventory.cycle(counts, inventory.KIND_WOOD) == inventory.KIND_SOIL
    assert inventory.cycle((7,) + (0,) * (KIND_COUNT - 1), inventory.KIND_SOIL) == inventory.KIND_SOIL    # nothing to place
    state, hand = pack.step(Pack(), counts, inventory.KIND_SOIL, 0, KEY_CYCLE)
    assert hand == inventory.KIND_ORE
    state, hand = pack.step(state, counts, hand, 0, KEY_CYCLE)      # held, not pressed again
    assert hand == inventory.KIND_ORE


def send(game, inputs: int, keys: int = 0) -> list[int]:
    """One frame, the game's or the pack's: returns its packet."""
    memory, labels = game.memory, game.labels
    memory[MAILBOX_KEYS] = keys
    memory[MAILBOX_INPUT] = inputs
    memory[MAILBOX_FRAME] = memory[labels["para_sent"]]
    game.machine.step()
    game.run_to(labels["para_send"])
    packet = game.packet()
    game.run_to(labels["para_loop"])
    return packet


def test_parasite_pack_matches_model(game_build):
    game = ParasiteGame(game_build)
    memory, labels = game.memory, game.labels
    rng = random.Random(1984)
    state = Pack()
    inputs = 0
    seen = {"opened": 0, "moved": 0, "closed": 0, "paused": 0, "cycled": 0}
    keys = 0
    for frame in range(600):
        if not state.open and rng.random() < 0.1:
            for kind in range(KIND_COUNT):
                memory[labels["inventory"] + kind] = rng.choice([0, 0, 1, rng.randrange(100), 99])
            memory[labels["hand"]] = rng.randrange(KIND_COUNT)
        if rng.random() < 0.3:
            inputs = rng.choice(INPUTS)
        if rng.random() < 0.3:
            keys = rng.choice([0, KEY_CYCLE])
        counts = tuple(memory[labels["inventory"] + kind] for kind in range(KIND_COUNT))
        hand = memory[labels["hand"]]
        player = memory[labels["zp_player_x"]:labels["zp_player_x"] + 4]
        game_frame = memory[labels["zp_frame"]]
        was_open = state.open
        state, hand_after = pack.step(state, counts, hand, inputs, keys)
        packet = send(game, inputs, keys)
        assert bool(memory[labels["pack_open"]]) == state.open, f"frame {frame}"
        if state.open:
            assert memory[labels["hand"]] == hand_after, f"frame {frame}"
            kinds = list(state.kinds)
            assert packet[0] == PACKET_PACK | (PACKET_PACK_DRAW if state.draw else 0) | \
                (PACKET_PACK_MOVED if state.moved else 0), f"frame {frame}"
            assert packet[1:3] == [len(kinds), kinds.index(hand_after)]
            assert packet[3:3 + 2 * len(kinds)] == [b for kind in kinds for b in (kind, counts[kind])]
            assert memory[labels["zp_frame"]] == game_frame, "the game ran in the pack"
            assert memory[labels["zp_player_x"]:labels["zp_player_x"] + 4] == player
            seen["opened"] += state.draw and hand_after == hand
            seen["moved"] += hand_after != hand
            seen["paused"] += 1
        else:
            assert not packet[0] & PACKET_PACK, f"frame {frame}"
            if not was_open:
                assert memory[labels["hand"]] == hand_after, f"frame {frame}"
                seen["cycled"] += hand_after != hand
            if state.closed:
                assert packet[0] & PACKET_REDRAW, "the view wasn't redrawn on closing"
                assert memory[labels["zp_input"]] == 0, "the closing frame had input"
                seen["closed"] += 1
    assert min(seen.values()) >= 10, seen


def test_panel_matches_model(game_build):
    machine = Machine6502()
    machine.load(*read_disc_file(game_build.disc_filepath, "RENDER"))
    labels = game_build.labels["HOST"]
    memory = machine.mpu.memory
    rng = random.Random(1066)
    for trial in range(40):
        screen_start = SCREEN_START + rng.randrange((SCREEN_END - SCREEN_START) // 8) * 8
        if trial == 0:
            screen_start = SCREEN_END - 8       # the panel's rows wrap at once
        counts = tuple(rng.choice([0, 1, 9, 10, rng.randrange(100), 99]) for _ in range(KIND_COUNT))
        hand = rng.randrange(KIND_COUNT)
        kinds = pack.shown(counts, hand)
        before = bytes(rng.randrange(256) for _ in range(SCREEN_END - SCREEN_START))
        memory[SCREEN_START:SCREEN_END] = before
        memory[labels["zp_screen_start"]] = screen_start & 0xFF
        memory[labels["zp_screen_start"] + 1] = screen_start >> 8
        memory[labels["host_pack_count"]] = len(kinds)
        memory[labels["host_pack_index"]] = kinds.index(hand)
        for i, kind in enumerate(kinds):
            memory[labels["host_pack_kinds"] + i] = kind
            memory[labels["host_pack_counts"] + i] = counts[kind]
        machine.call(labels["render_pack"])
        expected = pack.panel(screen_start, counts, hand)
        for address in range(SCREEN_START, SCREEN_END):
            want = expected.get(address, before[address - SCREEN_START])
            assert memory[address] == want, f"trial {trial}: &{address:04X}"
        # The hand moves: only the arrowheads are redrawn.
        hand = rng.choice(kinds)
        memory[labels["host_pack_index"]] = kinds.index(hand)
        machine.call(labels["render_pack_marks"])
        expected = pack.panel(screen_start, counts, hand, kinds)
        for address in range(SCREEN_START, SCREEN_END):
            want = expected.get(address, before[address - SCREEN_START])
            assert memory[address] == want, f"trial {trial}, moved: &{address:04X}"


ITEM_FRAME_FIRST = len(sprites.sprite_frames())
PACK_KEY, LEFT_KEY, TAB_KEY = (3, 7), (1, 9), (6, 0)     # Beebium's keyboard matrix: P, cursor left, TAB


def frames(bbc, labels, count: int, keys=(), label: str = "host_frame_shown") -> None:
    for key in keys:
        bbc.keyboard.key_down(key)
    for _ in range(count):
        bbc.debugger.run_to(labels[label], skip_current=True)
    for key in keys:
        bbc.keyboard.key_up(key)


def tap(bbc, labels, key) -> None:
    """Press a key for two of the pack's frames, then let it go for one."""
    bbc.keyboard.matrix_down(*key)
    frames(bbc, labels, 2, label="host_pack_shown")
    bbc.keyboard.matrix_up(*key)
    frames(bbc, labels, 1, label="host_pack_shown")


def test_pack_in_the_game(tube_bbc, tube_machine, game_build):
    """Fell the tree beside the start and dig down, open the pack: the panel
    is drawn over the view, which is otherwise left as it was; choose the
    wood; close it: the view is redrawn whole, as the models say. Then,
    given some stone, TAB cycles the hand from the wood to the soil and the
    stone."""
    from test_tube_game import expected_screen
    bbc = tube_bbc
    labels, plabels = game_build.labels["HOST"], game_build.labels["PARASITE"]
    peek = bbc.memory.address.peek
    bbc.disc.set_spin_up_delay(False)
    bbc.boot_disc(str(game_build.disc_filepath))
    assert bbc.run_until_or_timeout(lambda: peek[labels["host_frame_count"]] >= 2, RUN_TIMEOUT_EMULATED_SECONDS)
    frames(bbc, labels, 4, ["Z", "L"])
    frames(bbc, labels, 40, ["M", "L"])
    frames(bbc, labels, 100)
    parasite = bbc.connect_coprocessor().memory.address.peek
    counts = tuple(parasite[plabels["inventory"] + kind] for kind in range(KIND_COUNT))
    hand = parasite[plabels["hand"]]
    assert counts[inventory.KIND_WOOD] and hand == inventory.KIND_SOIL, (counts, hand)
    screen = bbc.memory.region(tube_machine.screen_region).peek
    before = screen[SCREEN_START:SCREEN_END]

    tap(bbc, labels, PACK_KEY)
    assert parasite[plabels["pack_open"]], "the pack didn't open"
    screen_start = peek[labels["zp_screen_start"]] | peek[labels["zp_screen_start"] + 1] << 8
    panel = pack.panel(screen_start, counts, hand)
    shown = screen[SCREEN_START:SCREEN_END]
    differences = [hex(a) for a in range(SCREEN_START, SCREEN_END)
                   if shown[a - SCREEN_START] != panel.get(a, before[a - SCREEN_START])]
    assert differences[:8] == [], f"{len(differences)} screen bytes differ with the pack open"

    tap(bbc, labels, LEFT_KEY)
    assert parasite[plabels["hand"]] == inventory.KIND_WOOD, "the hand didn't move to the wood"
    panel = pack.panel(screen_start, counts, inventory.KIND_WOOD)
    shown = screen[SCREEN_START:SCREEN_END]
    assert all(shown[a - SCREEN_START] == b for a, b in panel.items()), "the panel wasn't redrawn"

    bbc.keyboard.matrix_down(*PACK_KEY)
    frames(bbc, labels, 1)
    bbc.keyboard.matrix_up(*PACK_KEY)
    assert not parasite[plabels["pack_open"]], "the pack didn't close"
    frames(bbc, labels, 2)
    expected = expected_screen(bbc, labels)
    actual = screen[SCREEN_START:SCREEN_END]
    differences = [hex(a) for a, b in expected.items() if actual[a - SCREEN_START] != b]
    assert differences[:8] == [], f"{len(differences)} screen bytes differ after closing"

    bbc.connect_coprocessor().memory.address.bus[plabels["inventory"] + inventory.KIND_STONE] = 4
    for kind in (inventory.KIND_SOIL, inventory.KIND_STONE):
        bbc.keyboard.matrix_down(*TAB_KEY)
        frames(bbc, labels, 2)
        bbc.keyboard.matrix_up(*TAB_KEY)
        frames(bbc, labels, 1)
        assert parasite[plabels["hand"]] == kind, "TAB didn't cycle the hand"
        frames(bbc, labels, 1)
        count = peek[labels["host_items"]]
        assert count and peek[labels["host_item_frame"] + count - 1] & 0x7F == ITEM_FRAME_FIRST + kind, \
            "the hand isn't shown"
        expected = expected_screen(bbc, labels)
        actual = screen[SCREEN_START:SCREEN_END]
        differences = [hex(a) for a, b in expected.items() if actual[a - SCREEN_START] != b]
        assert differences[:8] == [], f"{len(differences)} screen bytes differ with the hand shown"
