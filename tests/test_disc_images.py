"""The disc images: named for the version, saying it in their catalogues,
and the ADFS copy holding the DFS disc's files, with their addresses and
boot option (tools/stratagem/disc_files.py, tools/stratagem/build.py)."""

import pytest

from stratagem._version import __version__
from stratagem.build import ADFS_DISC_FILEPATH, DISC_FILEPATH
from stratagem.disc_files import (DFS_TITLE, LICENSE_FILENAME, README_FILENAME, README_WIDTH, acorn_text, adfs_title,
                                  disc_filename, license_text, readme_text, version_filename, version_text)


def test_the_images_are_named_for_the_version():
    assert disc_filename(".ssd", "0.2.0") == "stratagem-v0.2.0.ssd"
    assert DISC_FILEPATH.name == f"stratagem-v{__version__}.ssd"
    assert ADFS_DISC_FILEPATH.name == f"stratagem-v{__version__}.adl"


@pytest.mark.parametrize("version, name", [
    ("0.1.0", "0_1_0"),
    ("1.12.3", "1_12_3"),
    ("10.11.12", "v101112"),        # x_y_z would be 8 characters: zero-padded
    ("0.12.13", "0_12_13"),         # just fits
])
def test_the_version_file_is_named_for_the_version(version, name):
    assert version_filename(version) == name
    assert len(name) <= 7 and "." not in name


def test_a_version_too_long_to_name_is_refused():
    with pytest.raises(ValueError):
        version_filename("100.100.0")


def test_the_adfs_title_is_the_game_and_its_version():
    assert adfs_title("0.1.0") == "Stratagem 0.1.0"
    assert len(adfs_title("10.11.12")) <= 19
    with pytest.raises(ValueError):
        adfs_title("100.100.100")


def test_the_readme_fits_a_mode_7_line_and_points_to_the_repository():
    text = readme_text()
    assert all(len(line) <= README_WIDTH for line in text.splitlines())
    assert "github.com/rob-smallshire/stratagem" in text and "*TYPE LICENSE" in text


def test_text_is_acorn_text():
    assert acorn_text("A\nB\n") == b"A\rB\r"


def files(root):
    return {source.path.rsplit(".", 1)[1]: (source.stat().load_address, source.stat().exec_address,
                                           source.read_bytes())
            for source in root.iterdir()}


def test_the_discs_carry_the_version_and_the_same_files(game_build):
    from oaknut.adfs import ADFS
    from oaknut.dfs.dfs import DFS

    assert game_build.disc_filepath == DISC_FILEPATH
    with DFS.from_file(DISC_FILEPATH, read_only=True) as dfs, \
            ADFS.from_file(ADFS_DISC_FILEPATH, read_only=True) as adfs:
        dfs_files = files(dfs.root / "$")
        assert "STRAT" in dfs_files and "PGAME" in dfs_files
        assert dfs_files[version_filename()][2] == acorn_text(version_text())
        assert dfs_files[README_FILENAME][2] == acorn_text(readme_text())
        assert dfs_files[LICENSE_FILENAME][2] == acorn_text(license_text())
        assert dfs.title.strip() == DFS_TITLE
        assert files(adfs.root) == dfs_files
        assert adfs.boot_option == dfs.boot_option
        assert adfs.title == adfs_title()


def mode_7(text: str) -> str:
    """Text as Beebium reads it back from the MODE 7 screen: the MOS stores
    "_" as &60, read back as "`"."""
    return text.replace("_", "`")


def test_star_cat_shows_the_version_and_star_type_says_it(launch_bbc, machine, game_build):
    from conftest import type_line, wait_for_prompt

    bbc = launch_bbc(machine)
    wait_for_prompt(bbc)
    bbc.disc.set_spin_up_delay(False)
    bbc.disc.drive(0).insert(str(DISC_FILEPATH))

    def shown_after(command, wanted):
        type_line(bbc, command)
        text = lambda: bbc.video.screen_text().text
        bbc.run_until_or_timeout(lambda: wanted in text() and text().rstrip().endswith(">"), 5)
        return bbc.video.screen_text().text

    shown = shown_after("*CAT", mode_7(LICENSE_FILENAME))
    for name in (DFS_TITLE, version_filename(), README_FILENAME, LICENSE_FILENAME):
        assert mode_7(name) in shown, shown
    wanted = f"Stratagem version {__version__}"
    assert wanted in shown_after(f"*TYPE {version_filename()}", wanted)
