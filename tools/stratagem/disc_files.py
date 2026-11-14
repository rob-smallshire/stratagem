"""What the disc images say about themselves: their names, titles and the
small text files that make the version evident from a *CAT.

- The images are named for the version: stratagem-v0.1.0.ssd and .adl.
- The DFS title is DFS_TITLE (DFS allows 12 characters, too few for the
  version too); the ADFS disc's root directory title, which ADFS's *CAT
  shows first, is "Stratagem 0.1.0" (adfs_title; ADFS allows 19).
- A file named for the version, version_filename(): "0_1_0" (an Acorn
  name has no dots), or, if that would not fit DFS's seven characters,
  zero-padded "v001203" (for 0.12.3). *TYPE it for the version in full.
- README: what the game is, what it needs and where it comes from, short
  enough lines for a 40-column *TYPE.
- LICENSE: the project's licence (the repository's LICENSE file).

Text is in the Acorn character set (oaknut's "acorn" codec), lines ending
with CR, as *TYPE expects.
"""

from __future__ import annotations

from pathlib import Path

from stratagem._version import __version__

PROJECT_DIRPATH = Path(__file__).resolve().parents[2]
DISC_FILENAME_STEM = "stratagem"
GAME_NAME = "Stratagem"
DFS_TITLE = "STRATAGEM"             # DFS allows 12 characters
DFS_TITLE_LIMIT = 12
DFS_NAME_LIMIT = 7
ADFS_TITLE_LIMIT = 19
README_FILENAME = "README"
LICENSE_FILENAME = "LICENSE"
README_WIDTH = 39                   # characters: a MODE 7 line, short of wrapping
PROJECT_URL = "github.com/rob-smallshire/stratagem"
assert len(DFS_TITLE) <= DFS_TITLE_LIMIT and len(PROJECT_URL) + 2 <= README_WIDTH


def disc_filename(suffix: str, version: str = __version__) -> str:
    """The disc image's file name, e.g. stratagem-v0.1.0.ssd."""
    return f"{DISC_FILENAME_STEM}-v{version}{suffix}"


def version_parts(version: str = __version__) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def version_filename(version: str = __version__) -> str:
    """The name of the file that carries the version: "x_y_z", or, if that
    is longer than a DFS name may be, "vXXYYZZ"."""
    major, minor, patch = version_parts(version)
    name = f"{major}_{minor}_{patch}"
    if len(name) > DFS_NAME_LIMIT:
        name = f"v{major:02}{minor:02}{patch:02}"
    if len(name) > DFS_NAME_LIMIT:
        raise ValueError(f"version {version} has no DFS file name")
    return name


def adfs_title(version: str = __version__) -> str:
    """The ADFS root directory title: the game and its version."""
    title = f"{GAME_NAME} {version}"
    if len(title) > ADFS_TITLE_LIMIT:
        raise ValueError(f"version {version} does not fit an ADFS title")
    return title


def version_text(version: str = __version__) -> str:
    return f"{GAME_NAME} version {version}\n{PROJECT_URL}\n"


def readme_text(version: str = __version__) -> str:
    """The README file's text."""
    lines = [
        f"{GAME_NAME} {version}",
        "",
        "Unfinished, and in development.",
        "",
        "An open-world digging and building",
        "game. Needs a BBC B+ 128K, a Model B",
        "with Integra-B (both with DFS), or a",
        "Master 128; three free banks of",
        "sideways RAM (a fourth for the music),",
        "a 6502 second processor, and, for the",
        "music, a Music 5000.",
        "",
        "SHIFT-BREAK to start; SPACE to go on.",
        "",
        "  Z X     walk left, right",
        "  K       jump",
        "  L       dig (with K or M: up, down)",
        "  SPACE   put down what's in hand",
        "  TAB     the next thing in hand",
        "  P       open and close the pack",
        "",
        "The manual, the source code and the",
        "latest version are on GitHub:",
        f"  {PROJECT_URL}",
        "",
        "Free software under the MIT licence:",
        "*TYPE LICENSE.",
    ]
    return "\n".join(lines) + "\n"


def license_text() -> str:
    """The project's licence, as in the repository."""
    return (PROJECT_DIRPATH / "LICENSE").read_text()


def acorn_text(text: str) -> bytes:
    """Text as an Acorn machine reads it: the Acorn character set, lines
    ending with CR."""
    import oaknut.codecs  # noqa: F401  (registers the "acorn" codec)

    return text.replace("\n", "\r").encode("acorn")
