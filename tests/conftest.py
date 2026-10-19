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
