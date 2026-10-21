"""Machine identification and sideways RAM discovery, in PROBE."""

from conftest import boot_until_ready

# asm/zeropage.asm
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS = 2

EXPECTED = {
    "b-plus-128k": (MACHINE_B_PLUS, [13, 12, 1, 0]),
    "integra-b": (MACHINE_INTEGRA_B, [7, 6, 5, 4]),
}


def _detected(bbc, labels):
    peek = bbc.memory.address.peek
    count = peek[labels["ram_bank_count"]]
    return peek[labels["zp_machine"]], [peek[labels["ram_banks"] + i] for i in range(count)]


def test_probe_reports_machine_and_sideways_ram(launch_bbc, machine, game_build):
    bbc = launch_bbc(machine)
    labels = boot_until_ready(bbc, game_build, "PROBE", command="*RUN PROBE")
    assert _detected(bbc, labels) == EXPECTED[machine.name]
    assert "Machine:" in bbc.video.screen_text().text
