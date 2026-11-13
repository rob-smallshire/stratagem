"""Build the Stratagem disc image.

Generates the table sources into build/generated/, then assembles each
source in SOURCES with beebasm onto one DFS disc image whose !BOOT runs
BOOT_FILE. A source may SAVE several files (asm/parasite.asm saves every
part of the parasite's game, so that they share one set of labels). Each
source's labels are written to build/labels/<NAME>.txt and returned in the
BuildResult.

beebasm writes a disc image only as far as its last file, so the image is
finally expanded to its full 80-track size with oaknut-dfs, as some
emulators and tools do not recognise a truncated image.

The disc is given a file named for the version, a README and the LICENSE
(disc_files.py), and the images are named for the version:
build/stratagem-v<version>.ssd. The same files are then copied onto an ADFS
L (640 KB) image, build/stratagem-v<version>.adl, with oaknut-adfs, for machines whose filing system is
ADFS. (On the B+ and the Integra-B, an ADFS or network filing system ROM
raises PAGE above STRAT's &1900, so the game runs from it only where PAGE
stays low enough: the Master, when it is supported.)

    uv run strat-build
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from stratagem.disc_files import (DFS_TITLE, LICENSE_FILENAME, README_FILENAME, acorn_text, adfs_title, disc_filename,
                                  license_text, readme_text, version_filename, version_text)
from stratagem.gen_tables import generate_all

PROJECT_DIRPATH = Path(__file__).resolve().parents[2]
ASM_DIRPATH = PROJECT_DIRPATH / "asm"
BUILD_DIRPATH = PROJECT_DIRPATH / "build"
LABELS_DIRPATH = BUILD_DIRPATH / "labels"
DISC_FILEPATH = BUILD_DIRPATH / disc_filename(".ssd")
ADFS_DISC_FILEPATH = BUILD_DIRPATH / disc_filename(".adl")


GENERATED_DIRPATH = BUILD_DIRPATH / "generated"

# Source name -> source file. The first creates the disc. The game runs on
# a 6502 second processor (docs/tube-game.md): !BOOT runs the host's loader,
# which loads the parasite's files into the parasite. The rest are
# diagnostics and prototypes.
SOURCES = {
    "HOST": ASM_DIRPATH / "host.asm",             # STRAT, MAIN, RENDER (host)
    "MBANK": ASM_DIRPATH / "mbank.asm",           # MBANK, the game's music (host, after HOST)
    "PARASITE": ASM_DIRPATH / "parasite.asm",     # PGAME, PWORLD, PLIGHT (parasite)
    "PROBE": ASM_DIRPATH / "probe.asm",           # PROBE
    "TUBE": ASM_DIRPATH / "tube_proto.asm",       # TUBEH (host), TUBEP (parasite)
    "SMOOTH": ASM_DIRPATH / "smooth_light.asm",   # SMOOTH (parasite)
    "TUBE_DRAW": ASM_DIRPATH / "tube_draw.asm",   # TDRAWH (host), TDRAWP (parasite)
    "LOADSCR": ASM_DIRPATH / "loadscr.asm",       # LOADSCR, LSCREEN
    "M5PLAY": ASM_DIRPATH / "m5play.asm",         # M5PLAY, M5SCALE, M5LOAD (the Music 5000)
    "M5TITLE": ASM_DIRPATH / "m5title.asm",       # M5TITLE
}
BOOT_FILE = "STRAT"


@dataclass(frozen=True)
class BuildResult:
    disc_filepath: Path
    labels: dict[str, dict[str, int]]   # source name -> label -> address


def find_beebasm() -> str:
    beebasm = shutil.which("beebasm")
    if beebasm is None:
        raise FileNotFoundError("beebasm not found on PATH")
    return beebasm


def parse_labels(text: str) -> dict[str, int]:
    """Parse beebasm's -labels output, a list of dict literals such as
    [{'start':8192L,...}], into a single name-to-address mapping."""
    scopes = ast.literal_eval(re.sub(r"(\d+)L\b", r"\1", text.strip()))
    return {name: address for scope in scopes for name, address in scope.items()}


def _assemble(source_filepath: Path, labels_filepath: Path, disc_args: list[str]) -> None:
    # beebasm resolves INCLUDE paths relative to its working directory, so
    # assemble from the project root.
    result = subprocess.run(
        [
            find_beebasm(),
            "-i", str(source_filepath.relative_to(PROJECT_DIRPATH)),
            *disc_args,
            "-d", "-labels", str(labels_filepath.relative_to(PROJECT_DIRPATH)),
        ],
        cwd=PROJECT_DIRPATH,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"beebasm failed on {source_filepath.name}:\n{result.stdout}\n{result.stderr}")


def _build_disc(disc_filepath: Path, sources: dict[str, Path], boot_file: str) -> dict[str, dict[str, int]]:
    """Assemble the sources onto a fresh disc whose !BOOT runs boot_file;
    return each source's labels."""
    disc = str(disc_filepath.relative_to(PROJECT_DIRPATH))
    staging = str(disc_filepath.with_suffix(".staging.ssd").relative_to(PROJECT_DIRPATH))
    labels = {}
    for index, (name, source_filepath) in enumerate(sources.items()):
        labels_filepath = LABELS_DIRPATH / f"{name}.txt"
        if index == 0:
            # Create a fresh disc with a !BOOT that runs the boot file.
            _assemble(source_filepath, labels_filepath,
                      ["-do", disc, "-boot", boot_file, "-title", DFS_TITLE])
        else:
            # Add to the existing disc via a staging copy.
            _assemble(source_filepath, labels_filepath, ["-di", disc, "-do", staging])
            (PROJECT_DIRPATH / staging).replace(disc_filepath)
        labels[name] = parse_labels(labels_filepath.read_text())
        write_label_symbols(name, labels[name])
    expand_disc(disc_filepath)
    return labels


def write_label_symbols(name: str, labels: dict[str, int]) -> None:
    """Write a source's labels as beebasm symbols, <NAME>_<label>, for the
    sources after it (MBANK, in its own bank, calls into HOST's STRAT)."""
    lines = [f"\\ Generated by stratagem.build from {name}'s labels: do not edit."]
    lines += [f"{name}_{label} = &{address:04X}" for label, address in sorted(labels.items())]
    (GENERATED_DIRPATH / f"labels_{name.lower()}.asm").write_text("\n".join(lines) + "\n")


def build() -> BuildResult:
    generate_all(GENERATED_DIRPATH)
    LABELS_DIRPATH.mkdir(parents=True, exist_ok=True)
    labels = _build_disc(DISC_FILEPATH, SOURCES, BOOT_FILE)
    add_text_files(DISC_FILEPATH)
    make_adfs_disc(DISC_FILEPATH, ADFS_DISC_FILEPATH)
    return BuildResult(DISC_FILEPATH, labels)


def read_disc_file(disc_filepath: Path, name: str) -> tuple[int, bytes]:
    """Return the load address and contents of a file on the disc image."""
    from oaknut.dfs.dfs import DFS

    with DFS.from_file(disc_filepath, read_only=True) as dfs:
        path = dfs.path(f"$.{name}")
        return path.stat().load_address & 0xFFFF, path.read_bytes()


def expand_disc(disc_filepath: Path) -> None:
    """Pad the disc image with empty sectors to its full 80-track size."""
    from oaknut.dfs.dfs import expand
    from oaknut.dfs.formats import ACORN_DFS_80T_SINGLE_SIDED

    expand(disc_filepath, ACORN_DFS_80T_SINGLE_SIDED)


def add_text_files(disc_filepath: Path) -> None:
    """Add the version file, the README and the LICENSE (disc_files.py), as
    Acorn text, to the DFS disc."""
    from oaknut.dfs.dfs import DFS

    with DFS.from_file(disc_filepath) as dfs:
        for name, text in ((version_filename(), version_text()), (README_FILENAME, readme_text()),
                           (LICENSE_FILENAME, license_text())):
            (dfs.root / "$" / name).write_bytes(acorn_text(text))


def make_adfs_disc(dfs_disc_filepath: Path, adfs_disc_filepath: Path) -> None:
    """Copy every file of the DFS disc, with its load and execution
    addresses, onto a new ADFS L disc (640 KB) with the same boot option."""
    from oaknut.adfs import ADFS, ADFS_L
    from oaknut.dfs.dfs import DFS

    adfs_disc_filepath.unlink(missing_ok=True)
    with DFS.from_file(dfs_disc_filepath, read_only=True) as dfs:
        with ADFS.create_file(adfs_disc_filepath, ADFS_L, title=adfs_title(),
                              boot_option=dfs.boot_option) as adfs:
            for source in (dfs.root / "$").iterdir():
                stat = source.stat()
                (adfs.root / source.path.split(".", 1)[1]).write_bytes(
                    source.read_bytes(), load_address=stat.load_address, exec_address=stat.exec_address)


def main() -> None:
    try:
        result = build()
    except (RuntimeError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print(f"Built {result.disc_filepath.relative_to(PROJECT_DIRPATH)} and "
          f"{ADFS_DISC_FILEPATH.relative_to(PROJECT_DIRPATH)} with {', '.join(result.labels)}")


if __name__ == "__main__":
    main()
