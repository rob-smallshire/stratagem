\ The Tube game's parasite side (docs/tube-game.md): the game itself, its
\ world and its light, on a 65C02 second processor with 64K of its own.
\ Assembled apart from the host's side (a separate address space), and
\ saved as three files, which the host's loader loads into the parasite:
\
\   PGAME   the game (&4300), run at pgame_start
\   PWORLD  the world: generator and changed-chunk store (&8000)
\   PLIGHT  the light's radial table (&C100)
\
\ The parasite's memory:
\
\   &0000-&0089  the game's zero page (as the host-only game's)
\   &008E-&008F  the mailbox the host writes
\   &0090-&00E5  the light's zero page
\   &00E6-&00ED  the packet's pointers (&EE upwards is the parasite OS's)
\   &0400-&07FF  the game's variables (as the host-only game's)
\   &0800-&1BFF  two packets and two draw lists (tube_layout.asm)
\   &1C00-&27FF  the tile cache (as the host-only game's)
\   &2800-&37FF  the light's plane
\   &3800-&42FF  the light's grid of excess
\   &4300-&7FFF  PGAME
\   &8000-&BCFF  PWORLD and its store
\   &C100-&F0FF  PLIGHT

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"
INCLUDE "asm/tube_layout.asm"
INCLUDE "build/generated/light.asm"
INCLUDE "asm/zeropage.asm"
INCLUDE "asm/variables.asm"
INCLUDE "build/generated/tiles.asm"
INCLUDE "build/generated/world.asm"
INCLUDE "build/generated/camera.asm"
INCLUDE "build/generated/player.asm"

INCLUDE "asm/miner_light_zp.asm"

ORG &E6
GUARD &EE                       \ The parasite's OS has &EE upwards
.para_packet        SKIP 2      \ This frame's packet
.para_list          SKIP 2      \ ... and draw list
.para_write         SKIP 2      \ Where the packet is being written
.para_cache         SKIP 2      \ A tile in the tile cache

ORG &1C00
.tile_cache         SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
.tile_cache_shapes  SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
.tile_cache_light   SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
ASSERT P% = &2800
.sl_plane           SKIP 64 * 64
.sl_grid            SKIP 11 * 256

CLEAR &4300, &8000
ORG &4300
GUARD &8000

INCLUDE "asm/parasite_main.asm"
INCLUDE "asm/pixels.asm"
INCLUDE "asm/scroll.asm"
INCLUDE "asm/camera.asm"
INCLUDE "asm/cache.asm"
INCLUDE "asm/player.asm"
INCLUDE "asm/actions.asm"
INCLUDE "asm/miner_light.asm"
INCLUDE "build/generated/miner.asm"
INCLUDE "build/generated/smooth.asm"

\ The host-only game pages its world in; here it is simply there.
.call_set_tile
    JMP set_tile

\ The renderer's table of each cell's graphic in its material's page, which
\ the light reads to find the graphics it lists.
ALIGN &100
.cell_offsets
    CELL_OFFSETS

\ The parasite's variables, not saved with the code
.para_sent          EQUB 0      \ Packets sent
.para_strips        EQUB 0      \ Strips of new tiles in this packet
.para_count         EQUB 0
.para_column        EQUB 0
.para_strip_x       EQUB 0
.para_strip_y       EQUB 0
.para_strip_down    EQUB 0
.para_y             EQUB 0
.para_inside        EQUB 0      \ The pool's window was inside the cache
.para_tmp           EQUW 0
.sl_pool            SKIP MINER_WINDOW
.sl_pool_clear      SKIP MINER_WINDOW
.sl_pool_outside    SKIP MINER_WINDOW     \ Non-zero outside the tile cache
.sl_tile_excess     SKIP GRID_SPAN * GRID_SPAN  \ Row-major, with the border
.sl_corner          SKIP GRID_SPAN * GRID_SPAN  \ At each tile's top left
.pgame_end

SAVE "PGAME", pgame_start, pgame_end, pgame_start

ASSERT sl_plane = &2800 AND sl_grid = &3800

INCLUDE "asm/world.asm"
SAVE "PWORLD", world_start, world_end, world_start

ORG &C100                       \ Clear of world.asm's guard at &C000
.sl_radial
INCBIN "build/generated/radial.bin"
.sl_radial_end
ASSERT sl_radial_end <= &F800
SAVE "PLIGHT", sl_radial, sl_radial_end, sl_radial
