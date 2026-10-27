"""The loading screen lab: the cover art as an 8-colour MODE 1 screen, set
beside plain MODE 1 and MODE 2 (stratagem.loading_screen).

    uv run strat-loading-lab [OUTPUT_DIRPATH]

Writes, into build/features/:

    loading-compare.png     the art and each screen, as the eye might see
                            them on a CRT
    loading-screens.png     the same screens' pixels, unblended
    loading-detail.png      a part of each, enlarged: pixels and blended
    loading-kernels.png     the 8-colour screen dithered each way
    loading-schemes.png     each way of splitting the pairs between lines
    loading-screen.bin      the 6-colour screen's 16K (its middle 256 pixels),
                            the loading screen, for &3000

and prints each screen's error (the mean Oklab distance, x100, from the art,
both slightly blurred) and the palette and control register values.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

from stratagem.lighting_lab import sheet
from stratagem.loading_screen import (ART_FILEPATH, BLACK, CROP_LEFT, CYAN, FLASHING, FLASHING_SCHEMES, KERNELS,
                                      LOADING_SCHEME, MAGENTA, MODE2_WIDTH, RED, SCREEN_WIDTH, YELLOW, Scheme, control_values, crt, display,
                                      dither, encode_mode1, error, flashing, load_art, nearest, palette_writes,
                                      physical, render, to_image)

EIGHT = flashing(BLACK, CYAN, MAGENTA, YELLOW)                          # KCMY / WRGB
SEVEN = Scheme((BLACK, FLASHING | CYAN, FLASHING | MAGENTA, FLASHING | YELLOW))   # KCMY / KRGB
SIX = LOADING_SCHEME                                                    # KWCY / KWRB
FOUR = Scheme((BLACK, RED, YELLOW, CYAN))                               # the best 4 of 8
ALL_EIGHT = np.arange(8)

KERNEL = "floyd-steinberg"
METRIC = "linear"
DETAIL = (slice(60, 140), slice(40, 160))      # the miner, in MODE 1 pixels
DETAIL_SCALE = 6


def screens(art: np.ndarray, art2: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Each screen, as the physical colours (256, width) it shows."""
    out = []
    lp = np.tile(ALL_EIGHT, (art2.shape[0], 1))
    out.append(("MODE 2, 160 x 256, 8 colours", physical(dither(art2, lp, KERNEL, METRIC), lp)))
    for label, scheme in [("MODE 1, 4 colours", FOUR),
                          ("MODE 1, flashing every line: 8 colours", EIGHT),
                          ("MODE 1, steady black: 7 colours", SEVEN),
                          ("MODE 1, steady black and white: 6 colours", SIX)]:
        lp = scheme.line_palettes()
        out.append((f"{label} ({scheme.name})", physical(dither(art, lp, KERNEL, METRIC), lp)))
    return out


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/features")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    art = load_art(ART_FILEPATH)
    art2 = load_art(ART_FILEPATH, MODE2_WIDTH)
    source = art.repeat(3, axis=0).repeat(3, axis=1)

    shown = screens(art, art2)
    for label, colours in shown:
        print(f"{error(colours, art if colours.shape[1] != MODE2_WIDTH else art2):6.2f}  {label}")

    sheet([("the art", to_image(source))] + [(label, to_image(crt(c))) for label, c in shown], 2) \
        .save(output_dirpath / "loading-compare.png")
    sheet([("the art", to_image(source))] + [(label, to_image(display(c))) for label, c in shown], 3) \
        .save(output_dirpath / "loading-screens.png")

    def detail(image: np.ndarray, scale: int = DETAIL_SCALE) -> Image.Image:
        rows, columns = DETAIL
        rows = slice(rows.start * scale, rows.stop * scale)
        columns = slice(columns.start * scale, columns.stop * scale)
        return to_image(image[rows, columns])

    panels = [("the art", detail(art.repeat(DETAIL_SCALE, axis=0).repeat(DETAIL_SCALE, axis=1)))]
    for label, colours in shown:
        short = label.split(" (")[0]
        panels.append((short, detail(display(colours, DETAIL_SCALE))))
        panels.append((short + ", blended", detail(crt(colours, DETAIL_SCALE))))
    sheet(panels, 3).save(output_dirpath / "loading-detail.png")

    lp = EIGHT.line_palettes()
    panels = []
    for kernel in KERNELS:
        for metric in ("linear", "oklab"):
            colours = physical(dither(art, lp, kernel, metric), lp)
            label = f"{kernel}, nearest in {metric}"
            print(f"{error(colours, art):6.2f}  8 colours, {label}")
            panels.append((label, detail(crt(colours, DETAIL_SCALE))))
    colours = physical(nearest(art, lp), lp)
    print(f"{error(colours, art):6.2f}  8 colours, undithered")
    panels.append(("undithered", detail(crt(colours, DETAIL_SCALE))))
    sheet(panels, 3).save(output_dirpath / "loading-kernels.png")

    panels = []
    for scheme in FLASHING_SCHEMES:
        lp = scheme.line_palettes()
        colours = physical(dither(art, lp, KERNEL, METRIC), lp)
        print(f"{error(colours, art):6.2f}  {scheme.name}")
        panels.append((f"even {scheme.name.replace('/', ', odd ')}", to_image(crt(colours, 2))))
    sheet(panels, 4).save(output_dirpath / "loading-schemes.png")

    lp = SIX.line_palettes()
    screen = encode_mode1(dither(art, lp, KERNEL, METRIC))
    assert (render(screen, SIX) == shown[-1][1][:, CROP_LEFT:CROP_LEFT + SCREEN_WIDTH]).all()
    (output_dirpath / "loading-screen.bin").write_bytes(screen)
    print(f"{SIX.name}: palette (&FE21)", " ".join(f"{b:02X}" for b in palette_writes(SIX)))
    print("control (&FE20), even and odd lines:", " ".join(f"{b:02X}" for b in control_values()))


if __name__ == "__main__":
    main()
