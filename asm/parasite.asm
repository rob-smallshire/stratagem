\ The Tube game's parasite side (docs/tube-game.md): the game itself, its
\ world and its light, on a 65C02 second processor with 64K of its own.
\ Assembled apart from the host's side (a separate address space), and
\ saved as three files, which the host's loader loads into the parasite:
\
\   PGAME   the game (&4300), run at pgame_start
\   PWORLD  the world: generator and changed-chunk store (&8000)
\   PLIGHT  the light's radial table (&C100), and daylight
\
\ The parasite's memory:
\
\   &0000-&0089  the game's zero page (as the host-only game's)
\   &008E-&008F  the mailbox the host writes
\   &0090-&00E5  the light's zero page
\   &00E6-&00ED  the packet's pointers (&EE upwards is the parasite OS's)
\   &0400-&07FF  the game's variables (as the host-only game's), then more
\                that need no starting value
\   &0800-&1BFF  two packets and two draw lists (tube_layout.asm)
\   &1C00-&27FF  the tile cache (as the host-only game's)
\   &2800-&37FF  the light's plane
\   &3800-&42FF  the light's grid of excess
\   &4300-&7FFF  PGAME, then pieces' slots
\   &8000-&BCFF  PWORLD and its store
\   &BD00-&C0FF  daylight's tables: sky depths and reaches (daylight.asm)
\   &C100-&F7FF  PLIGHT, then tables the light sets up each pass

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

sun_depth = &BD00               \ Each column's sky depth (daylight.asm)
sun_reach_1 = &BE00             \ ... and the deepest within 1 to 4 columns
sun_reach_2 = &BF00
sun_reach_3 = &C000

ORG &D1
.piece_ptr          SKIP 2      \ A slot's visibility (pieces.asm)
ASSERT P% <= &E6

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
INCLUDE "asm/torches.asm"
INCLUDE "asm/pieces.asm"
INCLUDE "build/generated/miner.asm"
INCLUDE "build/generated/smooth.asm"

\ The host-only game pages its world in; here it is simply there.
.call_set_tile                  \ (Noting for daylight whether the tile let
    PHA                         \ light through)
    JSR sun_clear_at
    STA sun_was_clear
    PLA
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
.para_changes       EQUB 0      \ Changed tiles in this packet
.para_change_y      EQUB 0      \ ... and where the next goes
.torch_count        EQUB 0      \ Torches (torches.asm)
.torch_held         EQUB 0      \ T was down last frame
.torch_index        EQUB 0
.torch_change_x     EQUB 0
.torch_change_y     EQUB 0
.torch_near_count   EQUB 0
.torch_best         EQUB 0
.torch_dx           EQUB 0
.torch_save_y       EQUB 0
.torch_new          EQUB 0
.torch_row          EQUB 0
.torch_rows         EQUB 0
.torch_column       EQUB 0
.torch_columns      EQUB 0
.torch_queue_head   EQUB 0
.torch_queue_tail   EQUB 0
.gather_left        EQUB 0
.gather_right       EQUB 0
.gather_top         EQUB 0
.gather_bottom      EQUB 0
.torch_x            SKIP TORCH_MAX
.torch_y            SKIP TORCH_MAX
.para_new_light     EQUB 0
.torch_pools        SKIP TORCH_MAX * MINER_WINDOW
.para_tmp           EQUW 0
ALIGN &100
.sun_reach_4        SKIP &100   \ Daylight (daylight.asm)
.pgame_end

\ Pieces' slots (pieces.asm), not saved with the code
.slot_visibility_even   SKIP SLOT_COUNT * 8 \ Each slot's, as the light finds it
.slot_pair              SKIP SLOT_COUNT     \ Each slot's pair, or PIECE_NO_SLOT
ORG slot_visibility_even + &200
.slot_visibility_odd    SKIP SLOT_COUNT * 8
.slot_mark              SKIP SLOT_COUNT
.pair_slot              SKIP PIECE_COUNT * 2    \ Each pair's slot, or PIECE_NO_SLOT

SAVE "PGAME", pgame_start, pgame_end, pgame_start

ASSERT sl_plane = &2800 AND sl_grid = &3800

INCLUDE "asm/world.asm"
SAVE "PWORLD", world_start, world_end, world_start

ASSERT world_slots + WORLD_SLOT_COUNT * SLOT_BYTES <= sun_depth

ASSERT sun_reach_3 + &100 <= sl_radial

ORG &C100                       \ Clear of world.asm's guard at &C000
.sl_radial
INCBIN "build/generated/radial.bin"
.sl_radial_end
INCLUDE "asm/daylight.asm"
.plight_end

\ Variables that need no starting value: after the game's (the host-only
\ game's light queue is unused here)
ORG light_queue_y + 2 * MINER_WINDOW
GUARD &0800
.torch_queue_x      SKIP TORCH_QUEUE    \ Torches (torches.asm)
.torch_queue_y      SKIP TORCH_QUEUE
.torch_queue_light  SKIP TORCH_QUEUE
.sun_busy           SKIP 1      \ Daylight (daylight.asm): tiles to relight
.sun_l              SKIP 1      \ ... a rectangle, inclusive
.sun_r              SKIP 1
.sun_b              SKIP 1
.sun_row            SKIP 1      \ ... from this row down
.sun_req_l          SKIP 1      \ Tiles to add to it
.sun_req_r          SKIP 1
.sun_req_t          SKIP 1
.sun_req_b          SKIP 1
.sun_rows_left      SKIP 1
.sun_to             SKIP 1
.sun_near_to        SKIP 1
.sun_x              SKIP 1      \ The tile being lit
.sun_y              SKIP 1
.sun_wall           SKIP 1      \ Walking along its row (sun_walk)
.sun_most           SKIP 1
.sun_dist           SKIP 1
.sun_side           SKIP 1
.sun_column         SKIP 1
.sun_in_wall        SKIP 1
.sun_target         SKIP 2      \ ... the nearest column open to the sky each way
.sun_best           SKIP 1
.sun_level          SKIP 1
.sun_new            SKIP 1
.sun_tmp            SKIP 1
.sun_count          SKIP 1
.sun_old_depth      SKIP 1
.sun_save_x         SKIP 1
.sun_save_y         SKIP 1
.sun_taper          SKIP 1
.para_material      SKIP 1      \ The tile being sent
.para_shape         SKIP 1
.piece_shape        SKIP 1      \ Pieces (pieces.asm)
.piece_pair         SKIP 1
.piece_slot_found   SKIP 1
.torch_near         SKIP TORCH_MAX      \ Torches (torches.asm)
.sun_was_clear      SKIP 1      \ Daylight: the changed tile, before
.sun_safe_l         SKIP 1      \ ... the tiles held in the tile cache
.sun_safe_r         SKIP 1
.sun_safe_t         SKIP 1
.sun_safe_b         SKIP 1

\ And tables the light sets up afresh each pass, above daylight's window
ORG plight_end
GUARD &F800
.sl_pool            SKIP MINER_WINDOW
.sl_pool_clear      SKIP MINER_WINDOW
.sl_pool_outside    SKIP MINER_WINDOW     \ Non-zero outside the tile cache
.sl_tile_excess     SKIP GRID_SPAN * GRID_SPAN  \ Row-major, with the border
.sl_corner          SKIP GRID_SPAN * GRID_SPAN  \ At each tile's top left

SAVE "PLIGHT", sl_radial, plight_end, sl_radial
