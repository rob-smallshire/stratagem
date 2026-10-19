"""Tube prototype 1 (asm/tube_proto.asm): every way of exchanging data with
the parasite delivers its bytes intact, and what each costs the host.

Run with -s to see the costs, in host cycles (2 MHz)."""

from conftest import RUN_TIMEOUT_EMULATED_SECONDS, collect_marks, run_on_tube

MARKS = 10


def test_tube_exchanges(tube_bbc, game_build):
    bbc = tube_bbc
    labels = game_build.labels["TUBE"]
    host = bbc.memory.address.peek
    copro = bbc.connect_coprocessor()
    para = copro.memory.address.peek
    assert para[0xF800:0xF802] != bytes(2), "no parasite"

    run_on_tube(bbc, game_build, "TUBEH", "TUBEP")
    cycles = collect_marks(bbc, labels["host_mark_hit"], labels["host_mark_id"], MARKS)
    ran = bbc.run_until_or_timeout(lambda: para[labels["para_done"]] == 0xFF, RUN_TIMEOUT_EMULATED_SECONDS)
    assert ran, "the parasite did not finish"

    def block(peek, name, length=256):
        return bytes(peek[labels[name]:labels[name] + length])

    assert block(host, "host_stream_buffer") == bytes(range(256))
    assert block(host, "host_pulled") == bytes((3 + 7 * i) & 0xFF for i in range(256))
    assert block(para, "para_push_target") == bytes(i ^ 0xA5 for i in range(256))
    assert block(host, "host_word_in", 128)[2:] == bytes(range(2, 128))
    assert block(para, "para_echo_block", 128)[2:] == bytes(i ^ 0xFF for i in range(2, 128))

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
