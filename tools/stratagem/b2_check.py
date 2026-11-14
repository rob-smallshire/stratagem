"""Run the game in the b2 emulator, which emulates the Master 128 and the
Master Turbo that Beebium doesn't yet: boot the disc, follow the loader,
play a few seconds, and save the view.

    uv run strat-b2 [--config "Master Turbo (MOS 3.20)"] [OUTPUT_FILEPATH]

b2 must be running with its HTTP server listening (Tools > Options, HTTP
Server; port 48075), built with its debugger, for peek and poke. The API
has no key presses, so the two waits for SPACE (wait_for_space and
wait_to_start) are patched out in memory as the loader reaches them, and
the miner's keys are held by patching read_input to load a fixed input.
The view is decoded from the shadow screen memory (b2's "s" override), in
the eight colours, with the game's palette approximated: logical colour n
shown as physical n AND 7.

b2's paste can't type a Return, and MOS 3.20's keyboard buffer isn't laid
out as MOS 1.20's, so this boots the DFS disc (Shift-Break) only.
"""

from __future__ import annotations

import argparse
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

from stratagem.build import DISC_FILEPATH, LABELS_DIRPATH, PROJECT_DIRPATH, build, parse_labels
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT

B2_URL = "http://127.0.0.1:48075"
WINDOW = "b2"
DEFAULT_CONFIG = "Master Turbo (MOS 3.20)"
DEFAULT_OUTPUT_FILEPATH = PROJECT_DIRPATH / "build" / "b2" / "view.png"
BOOT_TITLE, BOOT_LOADED, BOOT_READY = 0x01, 0x03, 0xFF     # zp_boot_status (asm/machine.asm)
TIMEOUT_SECONDS = 120

# Inputs held, for so many seconds: right, a sloping tunnel down, and back.
SCRIPT = [(INPUT_RIGHT, 2), (INPUT_RIGHT | INPUT_DOWN | INPUT_ACTION, 10), (INPUT_LEFT, 2), (0, 2)]

# The game's view: 64 cells of 8 bytes a row, VIEW_ROWS rows, hardware
# scrolled within the 16K screen at &4000-&7FFF.
SCREEN_START, SCREEN_END = 0x4000, 0x8000
ROW_BYTES, COLUMNS, VIEW_ROWS = 512, 64, 31
PIXEL_WIDTH, LINE_HEIGHT = 4, 2
RGB = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255),
       (255, 255, 255)]


class B2:
    """b2's HTTP API, for one window."""

    def __init__(self, url: str = B2_URL, window: str = WINDOW):
        self.url, self.window = url, window

    def request(self, method: str, *parts: str, query: dict | None = None, data: bytes | None = None) -> bytes:
        path = "/".join([method, self.window, *parts])
        url = f"{self.url}/{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as response:
            return response.read()

    def peek(self, address: int, count: int = 1, paging: str = "") -> bytes:
        """Bytes as the CPU sees them, or with b2's paging override: "m" main
        RAM, "s" the shadow."""
        return self.request("peek", f"{address:x}", f"{address + count:x}", query={"s": paging} if paging else None)

    def poke(self, address: int, data: bytes, paging: str = "") -> None:
        self.request("poke", f"{address:x}", query={"s": paging} if paging else None, data=bytes(data))

    def boot(self, config: str, disc_filepath: Path) -> None:
        self.request("reset", query={"config": config})
        time.sleep(1)
        self.request("load-disk", query={"path": str(disc_filepath), "in_memory": "true"})
        self.request("reset", query={"boot": "true"})


def follow_loader(b2: B2, host: dict[str, int]) -> None:
    """Run the loader to the game, patching out its two waits for SPACE: the
    loop's branch of each becomes two NOPs."""
    patches = {
        BOOT_TITLE: [(host["wait_for_space"] + 31, 0x10)],                # BPL wait
        BOOT_LOADED: [(host["wait_to_start"] + 3, 0xF0), (host["wait_to_start"] + 8, 0xD0)],    # BEQ up, BNE down
    }
    deadline = time.time() + TIMEOUT_SECONDS
    seen = None
    while time.time() < deadline:
        status = b2.peek(host["zp_boot_status"], paging="m")[0]
        if status != seen:
            print(f"loader status &{status:02X}", flush=True)
            seen = status
        for address, opcode in patches.pop(status, []):
            found = b2.peek(address, paging="m")[0]
            if found != opcode:
                raise RuntimeError(f"expected &{opcode:02X} at &{address:04X}, found &{found:02X}")
            b2.poke(address, b"\xEA\xEA", paging="m")
        if status == BOOT_READY:
            return
        time.sleep(0.2)
    raise TimeoutError(f"the loader stopped at status &{seen:02X}")


def hold(b2: B2, host: dict[str, int], inputs: int) -> None:
    """Make read_input load `inputs`, with no other keys."""
    def address(name):
        return [host[name] & 0xFF, host[name] >> 8]
    code = [0xA9, inputs, 0x8D, *address("zp_input"),
            0xA9, 0, 0x8D, *address("zp_keys"), 0x8D, *address("zp_tools"), 0x60]
    b2.poke(host["read_input"], bytes(code), paging="m")


def frames(b2: B2, host: dict[str, int]) -> int:
    return b2.peek(host["host_frame_count"], paging="m")[0]


def view(b2: B2, host: dict[str, int]) -> Image.Image:
    """The view, decoded from the shadow screen memory."""
    screen = np.frombuffer(b2.peek(SCREEN_START, SCREEN_END - SCREEN_START, paging="s"), np.uint8)
    low, high = b2.peek(host["zp_screen_start"], 2, paging="m")
    start = low | high << 8
    pixels = np.zeros((VIEW_ROWS * 8, COLUMNS * 2, 3), np.uint8)
    for row in range(VIEW_ROWS):
        for column in range(COLUMNS):
            for line in range(8):
                address = start + row * ROW_BYTES + column * 8 + line
                if address >= SCREEN_END:
                    address -= SCREEN_END - SCREEN_START
                byte = int(screen[address - SCREEN_START])
                for pixel, bits in enumerate(((7, 5, 3, 1), (6, 4, 2, 0))):
                    logical = sum(((byte >> bit) & 1) << (3 - i) for i, bit in enumerate(bits))
                    pixels[row * 8 + line, column * 2 + pixel] = RGB[logical & 7]
    image = Image.fromarray(pixels)
    return image.resize((image.width * PIXEL_WIDTH, image.height * LINE_HEIGHT), Image.Resampling.NEAREST)


def check(config: str, output_filepath: Path) -> None:
    build()
    host = parse_labels((LABELS_DIRPATH / "HOST.txt").read_text())
    b2 = B2()
    b2.boot(config, DISC_FILEPATH)
    follow_loader(b2, host)
    machine, screen_bit = b2.peek(host["zp_machine"], paging="m")[0], b2.peek(host["screen_bit"], paging="m")[0]
    banks = b2.peek(host["ram_banks"], b2.peek(host["ram_bank_count"], paging="m")[0], paging="m")
    print(f"machine {machine}, screen bit &{screen_bit:02X}, render ROMSEL "
          f"&{b2.peek(host['zp_romsel_render'], paging='m')[0]:02X}, sideways RAM banks {list(banks)}")
    for inputs, seconds in SCRIPT:
        hold(b2, host, inputs)
        before = frames(b2, host)
        time.sleep(seconds)
        after = frames(b2, host)
        print(f"inputs &{inputs:02X} for {seconds}s: {(after - before) % 256} frames (mod 256)", flush=True)
        if after == before:
            raise RuntimeError("the game stopped drawing frames")
    output_filepath.parent.mkdir(parents=True, exist_ok=True)
    view(b2, host).save(output_filepath)
    print(f"wrote {output_filepath}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output_filepath", nargs="?", type=Path, default=DEFAULT_OUTPUT_FILEPATH)
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"a b2 configuration (default {DEFAULT_CONFIG!r})")
    args = parser.parse_args()
    check(args.config, args.output_filepath)


if __name__ == "__main__":
    main()
