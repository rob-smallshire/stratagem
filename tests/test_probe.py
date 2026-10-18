"""The PROBE program identifies each target machine and its sideways RAM."""

from conftest import boot_until_ready

# asm/zeropage.asm
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS = 2

EXPECTED = {
    "b-plus-128k": (MACHINE_B_PLUS, {0, 1, 12, 13}),
    "integra-b": (MACHINE_INTEGRA_B, {4, 5, 6, 7}),
}


def test_probe_identifies_machine_and_sideways_ram(launch_bbc, machine, game_build):
    bbc = launch_bbc(machine)
    labels = boot_until_ready(bbc, game_build, "PROBE")
    peek = bbc.memory.address.peek
    expected_machine, expected_banks = EXPECTED[machine.name]

    count = peek[labels["ram_bank_count"]]
    banks = {peek[labels["ram_banks"] + i] for i in range(count)}

    assert peek[labels["zp_machine"]] == expected_machine
    assert banks == expected_banks
    assert "Machine:" in bbc.video.screen_text().text
