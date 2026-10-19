\ The Tube game's host side (docs/tube-game.md): the renderer, and the
\ frame's drawing from the parasite's packets. Assembled apart from the
\ parasite's side (a separate address space). Saves:
\
\   STRAT   low RAM: trampolines, the OSWRCH hook, the loader (run by !BOOT)
\   MAIN    program RAM: each frame's reading and drawing
\   RENDER  the render region: the host-only game's renderer, and the
\           light's draw list

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"
INCLUDE "asm/tube_layout.asm"
INCLUDE "build/generated/light.asm"
INCLUDE "build/generated/tiles.asm"
INCLUDE "build/generated/camera.asm"
INCLUDE "build/generated/player.asm"

WRCHV = &020E
BOOT_READY = &FF
HOST_ADDRESS = &30000           \ A DFS load address of &FFFFxxxx: the host
MACHINE_MODEL_B   = 0           \ Values of zp_machine (as zeropage.asm)
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS    = 2
MACHINE_MASTER    = 3

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

ASSERT material_pages = HOST_MATERIAL_PAGES
ASSERT light_masks = HOST_LIGHT_MASKS
