"""The README's in-game screenshot, taken in Beebium: the game built and
booted on a B+ 128K with a 65C02 second processor, a little digging done,
and the screen captured as the emulator shows it.

    uv run --group test strat-screenshot [--time HOURS] [OUTPUT_FILEPATH]

Writes docs/images/in-game.png by default.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from stratagem.build import build

PROJECT_DIRPATH = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_FILEPATH = PROJECT_DIRPATH / "docs" / "images" / "in-game.png"

VARIANT, PRESET = "model-b-plus-128k", "model-b-plus-128k"
TUBE_EXTENSION = "--tube-65c02"
TIMEOUT_EMULATED_SECONDS = 20.0
SETTLE_EMULATED_SECONDS = 0.06
BOOT_TITLE, BOOT_LOADED = 0x01, 0x03        # zp_boot_status (asm/machine.asm, STRAT)
DAY_FRAMES = 0x10000

# Keys held, for so many frames: to the hill, a sloping tunnel dug down
# into it, and a torch put down in it.
SCRIPT = [("X", 30), ("XML", 500), ("", 10), (" ", 4), ("Z", 12), ("", 30)]


# A MODE 2 pixel is four times as wide as a line is high, on the display.
PIXEL_WIDTH, LINE_HEIGHT = 4, 2


def capture(bbc) -> Image.Image:
    """The screen, a pixel to each of the game's (MODE 2) pixels and lines,
    scaled to the display's shape."""
    frame = bbc.video.capture_frame()
    pixels = np.frombuffer(frame.pixels, np.uint8).reshape(frame.height, frame.width, 4)[..., [2, 1, 0]]
    image = Image.fromarray(np.ascontiguousarray(pixels), "RGB")
    return image.resize((frame.width * PIXEL_WIDTH, frame.height * LINE_HEIGHT), Image.Resampling.NEAREST)


def take(output_filepath: Path, hours: float) -> None:
    from beebium.client import Beebium

    result = build()
    host, parasite_labels = result.labels["HOST"], result.labels["PARASITE"]
    with Beebium.launch(variant=VARIANT, preset=PRESET, extra_args=[TUBE_EXTENSION]) as bbc:
        bbc.system.set_speed_multiplier(0.0)
        peek = bbc.memory.address.peek

        def run_until(condition, what: str) -> None:
            if not bbc.run_until_or_timeout(condition, TIMEOUT_EMULATED_SECONDS):
                raise RuntimeError(f"{what} timed out")

        def press_space() -> None:
            bbc.keyboard.key_down(" ")
            bbc.run_for_emulated_seconds(SETTLE_EMULATED_SECONDS)
            bbc.keyboard.key_up(" ")

        run_until(lambda: bbc.video.screen_text().text.rstrip().endswith(">"), "the prompt")
        bbc.disc.set_spin_up_delay(False)
        bbc.boot_disc(str(result.disc_filepath))
        status = host["zp_boot_status"]
        run_until(lambda: peek[status] == BOOT_TITLE, "the title")
        press_space()
        run_until(lambda: peek[status] == BOOT_LOADED, "loading")
        time = round(hours * DAY_FRAMES / 24) % DAY_FRAMES
        parasite = bbc.connect_coprocessor().memory.address
        start = parasite_labels["world_start_time"]
        parasite.bus[start], parasite.bus[start + 1] = time & 0xFF, time >> 8
        press_space()
        run_until(lambda: peek[host["host_frame_count"]] >= 2, "the game")

        for keys, frames in SCRIPT:
            for key in keys:
                bbc.keyboard.key_down(key)
            for _ in range(frames):
                bbc.debugger.run_to(host["host_frame_shown"], skip_current=True)
            for key in keys:
                bbc.keyboard.key_up(key)
        bbc.run_for_emulated_seconds(SETTLE_EMULATED_SECONDS)
        image = capture(bbc)
    output_filepath.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_filepath, optimize=True)
    print(f"wrote {output_filepath} ({image.width} x {image.height})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output_filepath", nargs="?", type=Path, default=DEFAULT_OUTPUT_FILEPATH)
    parser.add_argument("--time", type=float, default=17.1, help="the hour of the world's day (default 17.1: dusk's glow)")
    args = parser.parse_args()
    take(args.output_filepath, args.time)


if __name__ == "__main__":
    main()
