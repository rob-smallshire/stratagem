"""Tube prototype 1 (asm/tube_proto.asm): every way of exchanging data with
the parasite delivers its bytes intact, and what each costs the host.

Run with -s to see the costs, in host cycles (2 MHz)."""

import contextlib

import pytest
from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError

from conftest import MACHINES, wait_for_prompt

TUBE_EXTENSION = "--tube-65c02"
MARKS = 10
RUN_TIMEOUT_EMULATED_SECONDS = 20.0


@pytest.fixture(params=MACHINES, ids=[m.name for m in MACHINES])
def tube_bbc(request):
    machine = request.param
    with contextlib.ExitStack() as stack:
        try:
            bbc = stack.enter_context(Beebium.launch(variant=machine.variant, preset=machine.preset,
                                                     extra_args=[TUBE_EXTENSION]))
        except ServerNotFoundError as e:
            pytest.skip(str(e))
        bbc.system.set_speed_multiplier(0.0)
        wait_for_prompt(bbc)
        if machine.name == "integra-b":
            # IBOS leaves the Tube off by default (beebium #203).
            type_line(bbc, "*CONFIGURE TUBE")
            bbc.keyboard.ctrl_break()
            wait_for_prompt(bbc)
        yield bbc


def type_line(bbc: Beebium, line: str) -> None:
    # Type with the machine running, and wait for it (beebium #206).
    bbc.debugger.ensure_running()
    bbc.keyboard.type(line + "\r")
    bbc.keyboard.wait_until_typing_complete()


def test_tube_exchanges(tube_bbc, game_build):
    bbc = tube_bbc
    labels = game_build.labels["TUBE"]
    host = bbc.memory.address.peek
    copro = bbc.connect_coprocessor()
    para = copro.memory.address.peek
    assert para[0xF800:0xF802] != bytes(2), "no parasite"

    bbc.disc.set_spin_up_delay(False)
    bbc.disc.drive(0).insert(str(game_build.disc_filepath))
    type_line(bbc, "*RUN TUBEH")
    bbc.keyboard.type("*RUN TUBEP\r")

    marks = []
    for _ in range(MARKS):
        bbc.debugger.run_to(labels["host_mark_hit"], skip_current=True)
        marks.append((host[labels["host_mark_id"]], bbc.debugger.cycle_count))
    assert [m for m, _ in marks] == list(range(1, MARKS + 1))
    ran = bbc.run_until_or_timeout(lambda: para[labels["para_done"]] == 0xFF, RUN_TIMEOUT_EMULATED_SECONDS)
    assert ran, "the parasite did not finish"

    def block(peek, name, length=256):
        return bytes(peek[labels[name]:labels[name] + length])

    assert block(host, "host_stream_buffer") == bytes(range(256))
    assert block(host, "host_pulled") == bytes((3 + 7 * i) & 0xFF for i in range(256))
    assert block(para, "para_push_target") == bytes(i ^ 0xA5 for i in range(256))
    assert block(host, "host_word_in", 128)[2:] == bytes(range(2, 128))
    assert block(para, "para_echo_block", 128)[2:] == bytes(i ^ 0xFF for i in range(2, 128))

    cycles = {mark: count for mark, count in marks}
    mark = cycles[10] - cycles[9]
    costs = {
        "mark (2 OSWRCH bytes)": mark,
        "STREAM 256 bytes, per byte": (cycles[2] - cycles[1] - mark) / 258,
        "PULL 256 bytes": cycles[3] - cycles[2] - mark,
        "PUSH 256 bytes": cycles[4] - cycles[3] - mark,
        "ECHO OSWORD, 128 bytes each way": cycles[6] - cycles[5] - mark,
        "NULL OSWORD round trip": (cycles[8] - cycles[7] - mark) / 64,
    }
    print()
    for name, cost in costs.items():
        print(f"  {name:36} {cost:8.1f}")
