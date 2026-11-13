"""The README, kept from drifting from the project: what it links and shows
is there, and the commands it gives exist."""

import re
import tomllib
from pathlib import Path

PROJECT_DIRPATH = Path(__file__).resolve().parents[1]
README_TEXT = (PROJECT_DIRPATH / "README.md").read_text()


def test_the_readmes_files_are_there():
    paths = re.findall(r'(?:src="|\]\()([^")#]+)', README_TEXT) + re.findall(r"`(presets/[^`]+)`", README_TEXT)
    local = [p for p in paths if "://" not in p]
    assert local, "no files found in the README"
    missing = [p for p in local if not (PROJECT_DIRPATH / p).exists()]
    assert not missing, f"the README names missing files: {missing}"


def test_the_readmes_commands_exist():
    scripts = tomllib.loads((PROJECT_DIRPATH / "pyproject.toml").read_text())["project"]["scripts"]
    commands = re.findall(r"uv run (?:--group \w+ )?(strat-[\w-]+)", README_TEXT)
    assert commands, "no commands found in the README"
    assert set(commands) <= set(scripts), f"not in pyproject.toml: {set(commands) - set(scripts)}"


def test_the_readme_needs_the_banks_the_host_needs():
    """The sideways RAM banks needed: the render bank and the store's."""
    layout = (PROJECT_DIRPATH / "asm" / "tube_layout.asm").read_text()
    store_banks = int(re.search(r"^STORE_BANKS = (\d+)", layout, re.M).group(1))
    words = {3: "three", 4: "four"}
    assert f"at least {words[1 + store_banks]} free 16K banks" in README_TEXT
