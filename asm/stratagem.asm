\ Stratagem: every part of the game, assembled together so that they share
\ one set of labels. Each part SAVEs its own file:
\
\   STRAT   low RAM: paging trampolines, shared buffers and the loader
\   RENDER  the render region (ANDY on the B+, the render bank otherwise)
\   WORLD   the world bank
\   MAIN    user RAM: the game

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"
INCLUDE "asm/zeropage.asm"
INCLUDE "asm/variables.asm"
INCLUDE "build/generated/tiles.asm"
INCLUDE "build/generated/world.asm"
INCLUDE "build/generated/camera.asm"
INCLUDE "build/generated/player.asm"

INCLUDE "asm/low.asm"
INCLUDE "asm/main.asm"

\ The render region and the world bank occupy the same addresses.
INCLUDE "asm/render.asm"
INCLUDE "asm/world.asm"
