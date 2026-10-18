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


MACHINES = [
    Machine("b-plus-128k", "model-b-plus-128k", "model-b-plus-128k"),
    Machine("integra-b", "model-b-integra-b", "model-b-integra-b-disc"),
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


def boot_until_ready(bbc: Beebium, game_build: BuildResult, program: str) -> dict[str, int]:
    """Boot the game disc and run until `program` reports BOOT_READY.
    Returns that program's labels."""
    labels = game_build.labels[program]
    status_address = labels["zp_boot_status"]
    bbc.boot_disc(str(game_build.disc_filepath))
    ready = bbc.run_until_or_timeout(
        lambda: bbc.memory.address.peek[status_address] == BOOT_READY,
        BOOT_TIMEOUT_EMULATED_SECONDS,
    )
    assert ready, f"{program} did not become ready within {BOOT_TIMEOUT_EMULATED_SECONDS} emulated seconds"
    bbc.run_for_emulated_seconds(SETTLE_EMULATED_SECONDS)
    return labels
