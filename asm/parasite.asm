\ The Tube game's parasite side (docs/tube-game.md): the game itself, its
\ world and its light, on a 65C02 second processor with 64K of its own.
\ Assembled apart from the host's side (a separate address space), and
\ saved as three files, which the host's loader loads into the parasite:
\
\   PGAME   the game (&4300), run at pgame_start
\   PWORLD  the world: generator and a cache of changed chunks (&8000)
\   PLIGHT  the light's radial table (&C100), daylight, torches and support
\
\ The parasite's memory:
\
\   &0000-&0064  the game's zero page (zeropage.asm; &65-&8A free)
\   &008C-&008F  the mailbox the host writes
\   &0090-&00E5  the light's zero page
\   &00E6-&00ED  the packet's pointers (&EE upwards is the parasite OS's)
\   &0400-&07FF  the game's variables, then more
\                that need no starting value
\   &0800-&1BFF  two packets and two draw lists (tube_layout.asm)
\   &1C00-&27FF  the tile cache
\   &2800-&37FF  the light's plane
\   &3800-&42FF  the light's grid of excess
\   &4300-&7FFF  PGAME, then pieces' slots
\   &8000-&A07A  PWORLD and its cache of the store of changed chunks
\   &A07B-&BCFF  free
\   &BD00-&C0FF  daylight's tables: sky depths and reaches (daylight.asm)
\   &C100-&F7FF  PLIGHT (with support and items), then tables the light
\                sets up each pass

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"
INCLUDE "asm/tube_layout.asm"
INCLUDE "build/generated/light.asm"
INCLUDE "asm/zeropage.asm"
INCLUDE "build/generated/inventory.asm"
INCLUDE "build/generated/pack.asm"
INCLUDE "build/generated/crafting.asm"
INCLUDE "asm/variables.asm"
INCLUDE "build/generated/tiles.asm"
INCLUDE "build/generated/world.asm"
INCLUDE "build/generated/camera.asm"
INCLUDE "build/generated/player.asm"
INCLUDE "build/generated/items.asm"

INCLUDE "asm/miner_light_zp.asm"

sun_depth = &BD00               \ Each column's sky depth (daylight.asm)
sun_reach_1 = &BE00             \ ... and the deepest within 1 to 4 columns
sun_reach_2 = &BF00
sun_reach_3 = &C000

TORCH_QUEUE = 128               \ Tiles awaiting redrawing (a power of 2)

ORG &D1                         \ Daylight's zero page
.sun_ptr            SKIP 2      \ A row of the tile cache's materials
.sun_shape          SKIP 2      \ ... and shapes
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
INCLUDE "asm/pieces.asm"
INCLUDE "build/generated/miner.asm"
INCLUDE "build/generated/smooth.asm"

\ Set a tile (actions.asm calls it), and queue it and its neighbours to be
\ checked for support (support.asm).
.call_set_tile
    JSR set_tile
    JMP support_note

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
.pair_slot              SKIP FRONT_PAIR + PIECE_COUNT * 2   \ Each pair's slot, or PIECE_NO_SLOT

SAVE "PGAME", pgame_start, pgame_end, pgame_start

ASSERT sl_plane = &2800 AND sl_grid = &3800

INCLUDE "asm/world.asm"
SAVE "PWORLD", world_start, world_end, world_start

ASSERT world_tables_end <= sun_depth

ASSERT sun_reach_3 + &100 <= sl_radial

ORG &C100                       \ Clear of world.asm's guard at &C000
.sl_radial
INCBIN "build/generated/radial_packed.bin"
.sl_radial_end
INCLUDE "build/generated/radial_rows.asm"
INCLUDE "asm/daylight.asm"
INCLUDE "asm/torches.asm"
INCLUDE "build/generated/support.asm"
INCLUDE "asm/support.asm"
INCLUDE "asm/items.asm"
INCLUDE "asm/inventory.asm"
INCLUDE "asm/pack.asm"
INCLUDE "asm/crafting.asm"
INCLUDE "asm/place.asm"
.plight_end

\ Variables that need no starting value: after the game's
ORG variables_end
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
.sun_lx             SKIP 1
.sun_rx             SKIP 1
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
.store_head         SKIP 1      \ Changes for the host's copy of the store
.store_tail         SKIP 1      \ (world.asm, store_emit)
.store_room         SKIP 2      \ ... the packet's room left for them
.store_count        SKIP 1      \ ... how many are in this packet
.store_queue_slot   SKIP STORE_QUEUE
.store_queue_offset SKIP STORE_QUEUE
.store_queue_material SKIP STORE_QUEUE
.store_queue_shape  SKIP STORE_QUEUE
.support_head       SKIP 1      \ Support (support.asm): tiles to check...
.support_tail       SKIP 1
.support_queue_x    SKIP SUPPORT_QUEUE
.support_queue_y    SKIP SUPPORT_QUEUE
.support_lost       SKIP 1      \ ... dropped when the queue was full
.support_x          SKIP 1      \ The tile being checked
.support_y          SKIP 1
.support_material   SKIP 1
.support_shape      SKIP 1
.support_held_rule  SKIP 1      \ ... its rule
.support_held       SKIP 1      \ ... how it is held
.support_best       SKIP 1      \ ... the most strength it is given
.support_side       SKIP 1
.support_checks     SKIP 1
.support_wait       SKIP 1      \ Frames until the next piece may fall
.support_drops      SKIP 1      \ The material that fell
.support_tmp        SKIP 1
.item_count         SKIP 1      \ Items thrown out (items.asm)...
.item_x_low         SKIP ITEM_MAX   \ ... in sixteenths of a pixel
.item_x_high        SKIP ITEM_MAX
.item_y_low         SKIP ITEM_MAX   \ ... in sixteenths of a line
.item_y_high        SKIP ITEM_MAX
.item_vx            SKIP ITEM_MAX   \ ... sixteenths a frame (gathering: speed)
.item_vy            SKIP ITEM_MAX
.item_state         SKIP ITEM_MAX   \ ... FLYING, RESTING or GATHERING
.item_timer         SKIP ITEM_MAX   \ ... frames flown, or to rest
.item_kind          SKIP ITEM_MAX
.item_px_low        SKIP ITEM_MAX   \ ... their pixels (x >> 4)
.item_px_high       SKIP ITEM_MAX
.item_top_low       SKIP ITEM_MAX   \ ... and top lines (y >> 4)
.item_top_high      SKIP ITEM_MAX
.item_thrown        SKIP 1      \ Items thrown, picking each one's spray
.item_i             SKIP 1      \ The item moving...
.item_tx            SKIP 1      \ ... the tile thrown from
.item_ty            SKIP 1
.item_new_x         SKIP 2      \ ... where it goes, how fast
.item_new_y         SKIP 2
.item_new_vx        SKIP 1
.item_new_vy        SKIP 1
.item_new_timer     SKIP 1
.item_new_px        SKIP 2      \ ... its pixel and top line then
.item_new_top       SKIP 2
.item_carry         SKIP 1      \ ... bit 7: y + vy didn't pass the world's top
.item_least_x       SKIP 2      \ The tile cache's bounds, in pixels and
.item_most_x        SKIP 2      \ lines (item_bounds)
.item_least_y       SKIP 2
.item_most_y        SKIP 2
.item_bounded       SKIP 1      \ Non-zero once they are worked out this frame
.item_miner_x       SKIP 2      \ The miner last frame, in sixteenths
.item_miner_y       SKIP 2
.item_box_left      SKIP 2      \ The box it covers, this frame or last
.item_box_right     SKIP 2
.item_box_top       SKIP 2
.item_box_bottom    SKIP 2
.item_tmp           SKIP 2
.item_bit           SKIP 1
.item_camera_line   SKIP 2      \ items_emit: the view's top line
.item_sent          SKIP 1

\ And tables the light sets up afresh each pass, above daylight's window
ORG plight_end
GUARD &F800
.sl_pool            SKIP MINER_WINDOW
.sl_pool_clear      SKIP MINER_WINDOW
.sl_pool_outside    SKIP MINER_WINDOW     \ Non-zero outside the tile cache
.sl_tile_excess     SKIP GRID_SPAN * GRID_SPAN  \ Row-major, with the border
.sl_corner          SKIP GRID_SPAN * GRID_SPAN  \ At each tile's top left
.torch_near         SKIP TORCH_MAX      \ (torches.asm)

SAVE "PLIGHT", sl_radial, plight_end, sl_radial
