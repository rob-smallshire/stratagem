"""The loading screen: the cover art as an 8-colour MODE 1 screen.

MODE 1 shows four colours a line. Set its four logical colours to four
flashing physical colours, and toggling the flash bit in the Video ULA's
control register swaps each for its complement: red and cyan, green and
magenta, blue and yellow, black and white. Toggle it every scan line and
even lines show one colour of each pair, odd lines the other, so that
between them all eight show. A logical colour may instead be steady (a
physical colour 0-7), the same on every line.

A scheme is the four physical colours (0-15) the logical colours are set
to. Physical colour 8 + c shows c with the flash bit clear and 7 - c with
it set; even lines are drawn with the flash bit clear.

The art is dithered with error diffusion that knows each line's palette, so
error pushed onto the next line, with the other palette, is made up there.
Colours are mixed in linear light, and the nearest colour is best chosen
there too: chosen in Oklab, flat greys come out lighter than asked.

When all four logical colours flash, no line has both black and white, so
nothing can be darker than a sixth or lighter than five sixths, in linear
light: black outlines become a grey. Keeping black (and white) steady
costs colours but keeps the range.

MODE 1 screen memory is 20K at &3000: 32 character rows of 640 bytes,
each 80 columns of 8 lines; byte (column * 8 + line) of a row holds four
pixels, the leftmost in bits 7 and 3 (its colour's bits 1 and 0).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

ART_FILEPATH = Path(__file__).resolve().parents[2] / "art" / "cover" / "stratagem-4x3.png"

SCREEN_START = 0x3000
WIDTH, HEIGHT = 320, 256             # MODE 1's, to which the art is scaled
MODE2_WIDTH = 160
# The screen shows the middle 256 pixels, 64 character columns, so that the
# horizontal blanking is longer: 64 columns (32us) of 128, rather than 48,
# in which to switch the flash bit (asm/loading_screen.asm).
SCREEN_WIDTH = 256
CROP_LEFT = (WIDTH - SCREEN_WIDTH) // 2
COLUMNS = SCREEN_WIDTH // 4          # 64 bytes, 4 pixels each
ROWS = HEIGHT // 8                   # 32 character rows
ROW_BYTES = COLUMNS * 8              # 512
SCREEN_SIZE = ROW_BYTES * ROWS       # 16K

ULA_CONTROL = 0xFE20
ULA_PALETTE = 0xFE21
MODE1_CONTROL = 0xD8                 # the OS's ULA control value for MODE 1
FLASH = 0x01                         # the control register's flash bit

FLASHING = 8
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
COLOUR_NAMES = "KRGYBMCW"

# The physical colours 0-7, in sRGB: bit 0 red, bit 1 green, bit 2 blue.
PHYSICAL_SRGB = np.array([[255 * (c & 1), 255 * (c >> 1 & 1), 255 * (c >> 2 & 1)] for c in range(8)],
                         dtype=np.uint8)
PHYSICAL_LINEAR = PHYSICAL_SRGB.astype(np.float64) / 255


# Colour spaces

def srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """sRGB, 0-1, to linear light."""
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    """Linear light to sRGB, 0-1."""
    linear = np.clip(linear, 0, 1)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


_LMS = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                 [0.2119034982, 0.6806995451, 0.1073969566],
                 [0.0883024619, 0.2817188376, 0.6299787005]])
_LAB = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                 [1.9779984951, -2.4285922050, 0.4505937099],
                 [0.0259040371, 0.7827717662, -0.8086757660]])


def linear_to_oklab(linear: np.ndarray) -> np.ndarray:
    """Linear light to Oklab (L 0-1)."""
    lms = np.cbrt(np.asarray(linear) @ _LMS.T)
    return lms @ _LAB.T


def to_image(linear: np.ndarray) -> Image.Image:
    return Image.fromarray(np.round(linear_to_srgb(linear) * 255).astype(np.uint8))


def physical_image(physical: np.ndarray) -> Image.Image:
    """Physical colours 0-7, one per pixel, as an image."""
    return Image.fromarray(PHYSICAL_SRGB[physical])


# The art

def load_art(filepath: Path | str, width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """The art scaled to width x height, in linear light, as (height, width, 3).

    Scaling is done in linear light, so that what a pixel shows is the mean
    light of the art it covers.
    """
    image = Image.open(filepath).convert("RGB")
    linear = srgb_to_linear(np.asarray(image, dtype=np.float64) / 255)
    channels = [Image.fromarray(linear[..., c].astype(np.float32), mode="F")
                .resize((width, height), Image.Resampling.LANCZOS) for c in range(3)]
    return np.clip(np.stack([np.asarray(c, dtype=np.float64) for c in channels], axis=-1), 0, 1)


# Schemes

@dataclass(frozen=True)
class Scheme:
    """The physical colours (0-15) the four logical colours are set to."""
    entries: tuple[int, int, int, int]

    def palette(self, flash: int) -> tuple[int, ...]:
        """The physical colours 0-7 the logical colours show with the flash
        bit clear (0) or set (1)."""
        return tuple((e ^ 7 if e & FLASHING and flash else e) & 7 for e in self.entries)

    def line_palettes(self, height: int = HEIGHT) -> np.ndarray:
        """Each line's palette, as (height, 4) physical colours."""
        return np.array([self.palette(line_flash(y)) for y in range(height)])

    @property
    def name(self) -> str:
        """Even lines' colours / odd lines'."""
        return "".join(COLOUR_NAMES[c] for c in self.palette(0)) + "/" + \
            "".join(COLOUR_NAMES[c] for c in self.palette(1))


def line_flash(y: int) -> int:
    """The flash bit while line y is drawn."""
    return y & 1


def flashing(*even: int) -> Scheme:
    """The scheme whose logical colours flash, showing `even` on even lines."""
    return Scheme(tuple(FLASHING | c for c in even))


# The loading screen's: black and white steady, cyan/red and yellow/blue
# flashing, so lines alternate KWCY and KWRB.
LOADING_SCHEME = Scheme((BLACK, WHITE, FLASHING | CYAN, FLASHING | YELLOW))

# Each pair split each way between even and odd lines: eight ways, since
# swapping even and odd lines over gives the same picture a line down.
FLASHING_SCHEMES = [flashing(BLACK, *(c ^ 7 * swap for c, swap in zip((RED, GREEN, BLUE), swaps)))
                    for swaps in itertools.product((0, 1), repeat=3)]


def palette_writes(scheme: Scheme) -> list[int]:
    """The 16 bytes to write to the ULA's palette (&FE21) for a scheme.

    Each byte is the palette index in the top nibble and the physical colour
    XOR 7 in the bottom. In MODE 1 a pixel's colour bits 1 and 0 select
    index bits 3 and 1, so each logical colour has four indices.
    """
    writes = []
    for index in range(16):
        logical = (index >> 3 & 1) << 1 | (index >> 1 & 1)
        writes.append(index << 4 | scheme.entries[logical] ^ 7)
    return writes


def control_values() -> tuple[int, int]:
    """The ULA control register (&FE20) values for even and odd lines."""
    return MODE1_CONTROL, MODE1_CONTROL | FLASH


# Dithering

KERNELS = {
    "floyd-steinberg": [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)],
    "atkinson": [(1, 0, 1 / 8), (2, 0, 1 / 8), (-1, 1, 1 / 8), (0, 1, 1 / 8), (1, 1, 1 / 8), (0, 2, 1 / 8)],
    "sierra-lite": [(1, 0, 2 / 4), (-1, 1, 1 / 4), (0, 1, 1 / 4)],
    "jarvis": [(dx, dy, w / 48) for dy, row in enumerate([[0, 0, 0, 7, 5], [3, 5, 7, 5, 3], [1, 3, 5, 3, 1]])
               for dx, w in zip(range(-2, 3), row) if w],
}


def dither(linear: np.ndarray, line_palettes: np.ndarray, kernel: str = "floyd-steinberg",
           metric: str = "linear", serpentine: bool = True, clamp: float = 0.0) -> np.ndarray:
    """Error diffusion, each line choosing from its own palette.

    `line_palettes` is (height, n) physical colours, a line's palette; the
    result is (height, width) indexes into each line's palette. The colour
    chosen is the nearest, in `metric` ("linear" or "oklab"), to the pixel
    plus the error diffused onto it; that colour is first clamped to the RGB
    cube widened by `clamp` on each side, which stops error running away
    where the palette can't make the colour.
    """
    height, width, _ = linear.shape
    weights = KERNELS[kernel]
    reach = max(dy for _, dy, _ in weights)
    error = np.zeros((reach + 1, width + 4, 3))     # a ring of lines, padded two each side
    result = np.zeros((height, width), dtype=np.uint8)
    for y in range(height):
        palette = PHYSICAL_LINEAR[line_palettes[y]]
        targets = linear_to_oklab(palette) if metric == "oklab" else palette
        backwards = serpentine and y & 1
        xs = range(width - 1, -1, -1) if backwards else range(width)
        here = error[y % (reach + 1)]
        row = linear[y]
        wanted = np.empty((width, 3))
        for x in xs:
            colour = np.clip(row[x] + here[x + 2], -clamp, 1 + clamp)
            point = linear_to_oklab(np.clip(colour, 0, None)) if metric == "oklab" else colour
            choice = int(np.argmin(((targets - point) ** 2).sum(axis=1)))
            result[y, x] = choice
            wanted[x] = colour
            residual = colour - palette[choice]
            for dx, dy, w in weights:
                error[(y + dy) % (reach + 1), x + 2 + (-dx if backwards else dx)] += residual * w
        here[:] = 0
    return result


def nearest(linear: np.ndarray, line_palettes: np.ndarray) -> np.ndarray:
    """No dithering: each pixel the nearest of its line's colours, in Oklab."""
    lab = linear_to_oklab(linear)
    result = np.zeros(linear.shape[:2], dtype=np.uint8)
    for y in range(linear.shape[0]):
        targets = linear_to_oklab(PHYSICAL_LINEAR[line_palettes[y]])
        result[y] = np.argmin(((lab[y][:, None, :] - targets[None]) ** 2).sum(axis=2), axis=1)
    return result


def physical(logical: np.ndarray, line_palettes: np.ndarray) -> np.ndarray:
    """Logical colours to the physical colours 0-7 they show."""
    return np.take_along_axis(line_palettes, logical.astype(np.intp), axis=1)


# Screen memory

def encode_mode1(logical: np.ndarray) -> bytes:
    """Logical colours 0-3, (256, 256), as the 16K of screen memory; given
    MODE 1's full width, (256, 320), its middle."""
    if logical.shape == (HEIGHT, WIDTH):
        logical = logical[:, CROP_LEFT:CROP_LEFT + SCREEN_WIDTH]
    assert logical.shape == (HEIGHT, SCREEN_WIDTH)
    screen = bytearray(SCREEN_SIZE)
    for y in range(HEIGHT):
        for column in range(COLUMNS):
            byte = 0
            for i in range(4):
                c = int(logical[y, column * 4 + i])
                byte |= (c >> 1 & 1) << (7 - i) | (c & 1) << (3 - i)
            screen[address(column * 4, y) - SCREEN_START] = byte
    return bytes(screen)


def decode_mode1(screen: bytes) -> np.ndarray:
    """Screen memory as its logical colours, (256, 256)."""
    logical = np.zeros((HEIGHT, SCREEN_WIDTH), dtype=np.uint8)
    for y in range(HEIGHT):
        for column in range(COLUMNS):
            byte = screen[address(column * 4, y) - SCREEN_START]
            for i in range(4):
                logical[y, column * 4 + i] = (byte >> (7 - i) & 1) << 1 | byte >> (3 - i) & 1
    return logical


def address(x: int, y: int) -> int:
    """The address of the byte holding pixel (x, y)."""
    return SCREEN_START + (y >> 3) * ROW_BYTES + (x >> 2) * 8 + (y & 7)


def render(screen: bytes, scheme: Scheme) -> np.ndarray:
    """What MODE 1 screen memory shows with a scheme and the flash bit
    toggled each line, as physical colours, (256, 256)."""
    return physical(decode_mode1(screen), scheme.line_palettes())


# The display

def display(physical_colours: np.ndarray, scale: int = 3) -> np.ndarray:
    """Physical colours at the display's proportions, in linear light: a
    MODE 1 pixel is `scale` square, a MODE 2 pixel twice as wide."""
    height, width = physical_colours.shape
    linear = PHYSICAL_LINEAR[physical_colours]
    return linear.repeat(scale, axis=0).repeat(scale * WIDTH // width, axis=1)


def blur(linear: np.ndarray, sigma_y: float, sigma_x: float) -> np.ndarray:
    """A Gaussian blur, in linear light, edges reflected."""
    out = linear
    for axis, sigma in ((0, sigma_y), (1, sigma_x)):
        if sigma <= 0:
            continue
        radius = max(1, math.ceil(3 * sigma))
        taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
        taps /= taps.sum()
        pad = [(0, 0)] * out.ndim
        pad[axis] = (radius, radius)
        padded = np.pad(out, pad, mode="reflect")
        n = out.shape[axis]
        out = sum(w * np.take(padded, np.arange(i, i + n), axis=axis) for i, w in enumerate(taps))
    return out


def crt(physical_colours: np.ndarray, scale: int = 3) -> np.ndarray:
    """What the eye makes of the display, roughly: each line spread over its
    neighbours, as a CRT's beam and the eye at a distance spread it."""
    return blur(display(physical_colours, scale), 0.8 * scale, 0.6 * scale)


def error(physical_colours: np.ndarray, linear: np.ndarray, sigma: float = 1.0) -> float:
    """How far the picture is from the art, both seen a little blurred: the
    mean Oklab distance, x100, at MODE 1's resolution."""
    shown = PHYSICAL_LINEAR[physical_colours]
    if shown.shape[1] != WIDTH:
        shown = shown.repeat(WIDTH // shown.shape[1], axis=1)
    if linear.shape[1] != WIDTH:
        linear = linear.repeat(WIDTH // linear.shape[1], axis=1)
    a = linear_to_oklab(np.clip(blur(shown, sigma, sigma), 0, 1))
    b = linear_to_oklab(np.clip(blur(linear, sigma, sigma), 0, 1))
    return float(np.sqrt(((a - b) ** 2).sum(axis=-1)).mean() * 100)


# The build

def loading_screen_source(scheme: Scheme = LOADING_SCHEME) -> str:
    """The palette and control values, for asm/loadscr.asm."""
    even, odd = control_values()
    return "\n".join([
        f"\\ Generated by stratagem.loading_screen for {scheme.name}: do not edit.",
        f"LOADING_CONTROL = &{even:02X}           \\ even lines; odd lines &{odd:02X}",
        f"LOADING_COLUMNS = {COLUMNS}            \\ character columns shown",
        f"LOADING_SCREEN_SIZE = &{SCREEN_SIZE:04X}     \\ from &{SCREEN_START:04X}",
        ".loading_palette               \\ to &FE21",
        "    EQUB " + ", ".join(f"&{b:02X}" for b in palette_writes(scheme)),
        "",
    ])


def generate(generated_dirpath: Path) -> None:
    """Write loading_screen.bin, the screen, and loading_screen.asm. The
    screen takes a few seconds to dither, so it is remade only when the art
    or this module is newer."""
    screen_filepath = generated_dirpath / "loading_screen.bin"
    (generated_dirpath / "loading_screen.asm").write_text(loading_screen_source())
    newest = max(ART_FILEPATH.stat().st_mtime, Path(__file__).stat().st_mtime)
    if screen_filepath.exists() and screen_filepath.stat().st_mtime > newest:
        return
    lines = LOADING_SCHEME.line_palettes()
    screen_filepath.write_bytes(encode_mode1(dither(load_art(ART_FILEPATH), lines)))
