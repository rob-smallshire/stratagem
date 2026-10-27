\ The Tube game's host side (docs/tube-game.md): the renderer, and the
\ frame's drawing from the parasite's packets. Assembled apart from the
\ parasite's side (a separate address space). Saves:
\
\   STRAT   low RAM: trampolines, the OSWRCH hook, the loader (run by !BOOT)
\   MAIN    program RAM: each frame's reading and drawing
\   RENDER  the render region: the renderer, and the light's draw list
\   LSCREEN the title screen (tools/stratagem/loading_screen.py)

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"
INCLUDE "asm/tube_layout.asm"
INCLUDE "build/generated/light.asm"
INCLUDE "build/generated/tiles.asm"
INCLUDE "build/generated/camera.asm"
INCLUDE "build/generated/player.asm"
INCLUDE "build/generated/items.asm"
INCLUDE "build/generated/inventory.asm"
INCLUDE "build/generated/pack.asm"
INCLUDE "build/generated/crafting.asm"

WRCHV = &020E
HOST_ADDRESS = &30000           \ A DFS load address of &FFFFxxxx: the host

\ The next byte from the parasite, in a transfer to the host.
MACRO READ_BYTE
.wait
    BIT TUBE_R3_STATUS
    BPL wait
    LDA TUBE_R3
ENDMACRO

INCLUDE "asm/host_zeropage.asm"
INCLUDE "asm/host_low.asm"
INCLUDE "asm/host_main.asm"
INCLUDE "asm/render.asm"
INCLUDE "asm/render_light.asm"
.host_render_end
SAVE "RENDER", render_start, host_render_end
PUTFILE "build/generated/loading_screen.bin", "LSCREEN", &3000

ASSERT material_pages = HOST_MATERIAL_PAGES
ASSERT light_masks = HOST_LIGHT_MASKS
