"""Fixtures for driving Stratagem in Beebium.

`machine` is parametrised over the target machines, so a test that takes it
runs once on each. `launch_bbc` is a factory that launches a machine and
shuts it down at the end of the test.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError

from stratagem.build import BuildResult, build

BOOT_READY = 0xFF   # asm/zeropage.asm; `=` constants are not exported as labels
BOOT_TIMEOUT_EMULATED_SECONDS = 20.0
SETTLE_EMULATED_SECONDS = 0.06     # three fields, so the screen has been scanned out


@dataclass(frozen=True)
class Machine:
    name: str
    variant: str
    preset: str
    screen_region: str      # the Beebium memory region the video reads


MACHINES = [
    Machine("b-plus-128k", "model-b-plus-128k", "model-b-plus-128k", "shadow_ram"),
    Machine("integra-b", "model-b-integra-b", "model-b-integra-b-disc", "main_ram"),
]

Launcher = Callable[[Machine], Beebium]


@pytest.fixture(params=MACHINES, ids=[m.name for m in MACHINES])
def machine(request) -> Machine:
    return request.param


@pytest.fixture
def launch_bbc() -> Iterator[Launcher]:
    with contextlib.ExitStack() as stack:

        def launch(machine: Machine) -> Beebium:
            try:
                bbc = stack.enter_context(Beebium.launch(variant=machine.variant, preset=machine.preset))
            except ServerNotFoundError as e:
                pytest.skip(str(e))
            bbc.system.set_speed_multiplier(0.0)
            return bbc

        yield launch


@pytest.fixture(scope="session")
def game_build() -> BuildResult:
    """Build the game disc once per test session."""
    try:
        return build()
    except FileNotFoundError as e:
        pytest.skip(str(e))


def parasite_machine(game_build: BuildResult):
    """The parasite's game (PGAME, PWORLD, PLIGHT) in py65's 65C02, for
    calling its routines directly; returns it and its labels."""
    from mos6502 import Machine6502
    from stratagem.build import read_disc_file

    machine = Machine6502(cmos=True)
    for name in ("PGAME", "PWORLD", "PLIGHT"):
        machine.load(*read_disc_file(game_build.disc_filepath, name))
    return machine, game_build.labels["PARASITE"]


# The store of changed chunks (asm/tube_layout.asm, asm/world.asm)
OSWRCH = 0xFFEE
COMMAND_FRAME, COMMAND_FETCH = 128, 129
MAILBOX_FETCHED = 0x8C
STORE_QUEUE, STORE_CHUNK = 32, 0xFF
SLOT_BYTES, CHUNK_TILES = 128, 64


class FakeHost:
    """The host's side of the store of changed chunks, for the parasite in
    py65: it keeps the store, takes the changes the parasite sends (from
    the queue, for tests that call routines, or from each packet), and
    copies chunks to the parasite as the packet or COMMAND_FETCH asks."""

    def __init__(self, machine, labels):
        self.labels = labels
        self.memory = machine.mpu.memory
        self.store: dict[int, list[int]] = {}   # slot -> its chunk
        self.expect, self.command, self.arguments = 0, None, []
        self.fetched = 0            # chunks fetched at once
        self.prefetched = 0         # chunks fetched ahead of need, by packets
        self.memory[OSWRCH] = 0x60  # RTS, after the hook
        machine.hooks[OSWRCH] = self.oswrch

    def cached(self, slot: int) -> list[int]:
        """The parasite's cached copy of slot."""
        cache_slot = self.memory[self.labels["cache_of"] + slot]
        assert cache_slot, f"slot {slot} isn't cached"
        base = self.labels["world_slots"] + (cache_slot - 1) * SLOT_BYTES
        return list(self.memory[base:base + SLOT_BYTES])

    def apply(self, slot: int, offset: int, material: int, shape: int, chunk=None) -> None:
        if offset == STORE_CHUNK:
            self.store[slot] = list(chunk)
        else:
            self.store[slot][offset] = material
            self.store[slot][offset + CHUNK_TILES] = shape

    def take_queue(self) -> None:
        """Take the queued changes, as store_emit sends them."""
        memory, labels = self.memory, self.labels
        head, tail = memory[labels["store_head"]], memory[labels["store_tail"]]
        while head != tail:
            slot, offset = memory[labels["store_queue_slot"] + head], memory[labels["store_queue_offset"] + head]
            chunk = self.cached(slot) if offset == STORE_CHUNK else None
            self.apply(slot, offset, memory[labels["store_queue_material"] + head],
                       memory[labels["store_queue_shape"] + head], chunk)
            head = (head + 1) % STORE_QUEUE
        memory[labels["store_head"]] = head

    def take_packet(self, mpu=None) -> None:
        """Take the packet's changes and copy the chunk it asks for (at
        para_send, after store_emit and cache_prefetch)."""
        memory, pointer = self.memory, self.labels["zp_store_count"]
        at = memory[pointer] | memory[pointer + 1] << 8
        count, at = memory[at], at + 1
        for _ in range(count):
            slot, offset = memory[at], memory[at + 1]
            if offset == STORE_CHUNK:
                self.apply(slot, offset, 0, 0, memory[at + 2:at + 2 + SLOT_BYTES])
                at += 2 + SLOT_BYTES
            else:
                self.apply(slot, offset, memory[at + 2], memory[at + 3])
                at += 4
        if memory[at]:
            self.copy(memory[at], memory[at + 1] | memory[at + 2] << 8)
            self.prefetched += 1

    def copy(self, slot: int, address: int) -> None:
        self.memory[address:address + SLOT_BYTES] = self.store[slot]

    def oswrch(self, mpu) -> None:
        if self.expect:
            self.arguments.append(mpu.a)
            self.expect -= 1
            if not self.expect and self.command == COMMAND_FETCH:
                slot, low, high = self.arguments
                self.copy(slot, low | high << 8)
                self.memory[MAILBOX_FETCHED] = 0xFF
                self.fetched += 1
        elif mpu.a in (COMMAND_FRAME, COMMAND_FETCH):
            self.command, self.arguments = mpu.a, []
            self.expect = 1 if mpu.a == COMMAND_FRAME else 3

    def check_cache(self) -> None:
        """Every chunk the parasite caches is the host's, unless changes to
        it are still queued."""
        memory, labels = self.memory, self.labels
        head, tail = memory[labels["store_head"]], memory[labels["store_tail"]]
        queued = {memory[labels["store_queue_slot"] + i % STORE_QUEUE] for i in range(head, head + (tail - head) % STORE_QUEUE)}
        for slot in range(1, 256):
            if memory[labels["cache_of"] + slot] and slot not in queued:
                assert self.cached(slot) == self.store[slot], f"slot {slot}: the cached chunk isn't the host's"

    def tile_at(self, x: int, y: int):
        """The world as the parasite and this host hold it."""
        from stratagem.world import CHUNK_SIZE, CHUNKS_ACROSS, generate_tile
        index = (y // CHUNK_SIZE) * CHUNKS_ACROSS + x // CHUNK_SIZE
        slot = self.memory[self.labels["world_directory"] + index]
        if not slot:
            return generate_tile(x, y)
        chunk = self.cached(slot) if self.memory[self.labels["cache_of"] + slot] else self.store[slot]
        offset = (y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE
        return chunk[offset], chunk[offset + CHUNK_TILES]


def wait_for_prompt(bbc: Beebium) -> None:
    prompt = bbc.run_until_or_timeout(
        lambda: bbc.video.screen_text().text.rstrip().endswith(">"),
        BOOT_TIMEOUT_EMULATED_SECONDS,
    )
    assert prompt, "no prompt"


def boot_until_ready(bbc: Beebium, game_build: BuildResult, source: str, command: str | None = None) -> dict[str, int]:
    """Boot the game disc, or with `command` insert it and type that command
    instead, and run until the program reports BOOT_READY. Returns the
    labels of the source that program was assembled from."""
    labels = game_build.labels[source]
    status_address = labels["zp_boot_status"]
    # Shift-Break before the OS has finished starting garbles the boot
    # (beebium #125), so wait for the language's prompt first.
    wait_for_prompt(bbc)
    bbc.disc.set_spin_up_delay(False)
    if command is None:
        bbc.boot_disc(str(game_build.disc_filepath))
    else:
        bbc.disc.drive(0).insert(str(game_build.disc_filepath))
        bbc.keyboard.type(command + "\r")
    ready = bbc.run_until_or_timeout(
        lambda: bbc.memory.address.peek[status_address] == BOOT_READY,
        BOOT_TIMEOUT_EMULATED_SECONDS,
    )
    assert ready, f"{source} did not become ready within {BOOT_TIMEOUT_EMULATED_SECONDS} emulated seconds"
    bbc.run_for_emulated_seconds(SETTLE_EMULATED_SECONDS)
    return labels


# Machines with a second processor (a 3 MHz 65C02)

TUBE_EXTENSION = "--tube-65c02"
RUN_TIMEOUT_EMULATED_SECONDS = 20.0


@pytest.fixture(params=MACHINES, ids=[m.name for m in MACHINES])
def tube_machine(request) -> Machine:
    return request.param


@pytest.fixture
def tube_bbc(tube_machine):
    machine = tube_machine
    with contextlib.ExitStack() as stack:
        try:
            bbc = stack.enter_context(Beebium.launch(variant=machine.variant, preset=machine.preset,
                                                     extra_args=[TUBE_EXTENSION]))
        except ServerNotFoundError as e:
            pytest.skip(str(e))
        bbc.system.set_speed_multiplier(0.0)
        wait_for_prompt(bbc)
        yield bbc


def type_line(bbc: Beebium, line: str) -> None:
    # Type with the machine running, and wait for it (beebium #206).
    bbc.debugger.ensure_running()
    bbc.keyboard.type(line + "\r")
    bbc.keyboard.wait_until_typing_complete()


def run_on_tube(bbc: Beebium, game_build: BuildResult, host_file: str, parasite_file: str) -> None:
    """Insert the game disc, install the host file, then run the parasite's."""
    bbc.disc.set_spin_up_delay(False)
    bbc.disc.drive(0).insert(str(game_build.disc_filepath))
    type_line(bbc, f"*RUN {host_file}")
    bbc.keyboard.type(f"*RUN {parasite_file}\r")


def collect_marks(bbc: Beebium, hit_address: int, id_address: int, count: int) -> dict[int, int]:
    """Run to each of `count` marks the host notes: mark -> host cycle count."""
    marks = {}
    for _ in range(count):
        bbc.debugger.run_to(hit_address, skip_current=True)
        marks[bbc.memory.address.peek[id_address]] = bbc.debugger.cycle_count
    assert list(marks) == list(range(1, count + 1))
    return marks
