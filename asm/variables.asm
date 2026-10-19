\ Variables outside zero page, which is full: the language workspace,
\ &0400-&07FF, is ours, as the game replaces the language. For variables
\ that are never pointers and aren't used in the tightest loops.

ORG &0400
GUARD &0800

\ Digging and placing (modelled by tools/stratagem/actions.py)
.inventory       SKIP 1      \ Blocks carried
.cooldown        SKIP 1      \ Frames until the next dig or place
.action          SKIP 1      \ What was done this frame: 0, 1 dig, 2 place
.target_x        SKIP 1      \ The tile aimed at
.target_y        SKIP 1
.want            SKIP 1      \ Aiming for: 0 diggable, otherwise empty
.action_tile     SKIP 1      \ The material a dig leaves
.target_shape    SKIP 1      \ The shape of the tile aimed at
.dig_side        SKIP 1      \ The side a dig removes from
.redraw_tile     SKIP 1      \ Non-zero if a changed tile awaits redrawing...
.redraw_tile_x   SKIP 1      \ ... here
.redraw_tile_y   SKIP 1

\ Tile cache: the tile rectangle it holds, inclusive
.cached_left     SKIP 1
.cached_right    SKIP 1
.cached_top      SKIP 1
.cached_bottom   SKIP 1
.view_left       SKIP 1      \ The tile rectangle the view needs
.view_right      SKIP 1
.view_top        SKIP 1
.view_bottom     SKIP 1

\ Digging diagonally (see diagonal in asm/actions.asm)
.diagonal_dx     SKIP 1      \ Directions held: -1, 0 or 1
.diagonal_dy     SKIP 1
.ramp_shape      SKIP 1      \ The ramp to cut the step to, or 0
.ground          SKIP 2      \ The line just below the player's feet
.left_column     SKIP 1      \ The columns of the player's edges
.right_column    SKIP 1
.part0_left      SKIP 2      \ The parts of the path, in pixels and lines
.part0_right     SKIP 2
.part0_top       SKIP 2
.part0_bottom    SKIP 2
.part1_left      SKIP 2
.part1_right     SKIP 2
.part1_top       SKIP 2
.part1_bottom    SKIP 2
.rect_left       SKIP 2      \ The rectangle being scanned
.rect_right      SKIP 2
.rect_top        SKIP 2
.rect_bottom     SKIP 2
.step_x          SKIP 1      \ The step, if step_valid
.step_y          SKIP 1
.step_valid      SKIP 1
.keep_row        SKIP 1      \ The floor kept: this row, these columns
.keep_first      SKIP 1
.keep_last       SKIP 1
.scan_column     SKIP 1      \ The column being worked
.scan_mode       SKIP 1      \ SCAN_*
.scan_keeps      SKIP 1      \ Non-zero to skip the floor kept
.first_row       SKIP 1
.last_row        SKIP 1
.first_column    SKIP 1
.last_column     SKIP 1
.span_first      SKIP 1      \ region_mask: the first column or row
.best_left       SKIP 1      \ The most solid left of the tiles found so far...
.best_column     SKIP 1      \ ... and where
.best_row        SKIP 1

\ Light (modelled by tools/stratagem/lighting.py: miner_light)
.light_dirty     SKIP 1      \ Non-zero if tiles changed since the last pass
.light_valid     SKIP 1      \ Non-zero once light_x/y hold a pass's centre
.light_x         SKIP 1      \ The miner's tile at the last pass
.light_y         SKIP 1
.miner_x         SKIP 1      \ The miner's tile now
.miner_y         SKIP 1
.window_x        SKIP 1      \ The centre of the window being applied
.window_y        SKIP 1
.pool_index      SKIP 1      \ The window entry being worked
.pool_clear_here SKIP 1      \ Non-zero if its tile lets light through
.pool_best       SKIP 1      \ The brightest light reaching it so far
.light_tile_x    SKIP 1      \ Its tile
.light_tile_y    SKIP 1
.pool            SKIP MINER_WINDOW     \ The miner's light, by window entry
.pool_clear      SKIP MINER_WINDOW     \ Non-zero where light passes
.light_queue_count SKIP 1    \ Tiles whose light changed, to redraw
.light_queue_index SKIP 1
.light_queue_x   SKIP 2 * MINER_WINDOW
.light_queue_y   SKIP 2 * MINER_WINDOW
