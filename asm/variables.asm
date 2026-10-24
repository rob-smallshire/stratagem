\ Variables outside zero page, which is full: the language workspace,
\ &0400-&07FF, is ours, as the game replaces the language. For variables
\ that are never pointers and aren't used in the tightest loops.

ORG &0400
GUARD &0800

\ Digging and placing (modelled by tools/stratagem/actions.py)
.inventory       SKIP KIND_COUNT \ Counts carried, by kind (inventory.asm)
.hand            SKIP 1      \ The kind placing puts down
.chopped         SKIP 1      \ Non-zero if this dig broke a tree's part
.dug_material    SKIP 1      \ The material this dig took from

\ The pack (pack.asm)
.pack_open       SKIP 1      \ Non-zero while the pack is open
.pack_held       SKIP 1      \ The input last frame
.pack_pressed    SKIP 1      \ Keys pressed this frame
.pack_draw       SKIP 1      \ Non-zero if the host must draw the panel...
.pack_moved      SKIP 1      \ ... or the arrowheads, the hand having moved
.pack_closed     SKIP 1      \ Non-zero on the frame it closed
.pack_count      SKIP 1      \ The kinds shown...
.pack_index      SKIP 1      \ ... the hand's place among them...
.pack_kinds      SKIP KIND_COUNT \ ... and them
.pack_i          SKIP 1
.pack_keys_held  SKIP 1      \ The second byte of input last frame...
.pack_keys_pressed SKIP 1    \ ... and its keys pressed this frame
.pack_changed    SKIP 1      \ Non-zero if the counts or the grid changed
.pack_cell       SKIP 1      \ A cell's key pressed this frame (1 on), or 0
.pack_seen       SKIP KIND_COUNT \ Non-zero for each kind shown since opening
.pack_station    SKIP 1      \ Where the miner crafts (crafting.py)
.pack_size       SKIP 1      \ Its grid's size

\ Crafting (crafting.asm)
.craft_grid      SKIP GRID_CELLS \ A kind or CELL_EMPTY each, by rows
.craft_book      SKIP 1      \ A bit for each recipe made
.craft_copied    SKIP 1      \ The recipe COPY laid out last
.craft_repeat    SKIP 1      \ Frames until L, held, makes again
.hand_last       SKIP 1      \ The hand as last seen (items.asm)...
.hand_timer      SKIP 1      \ ... frames left to show it or the tool...
.tool_last       SKIP 1      \ ... the tool as last seen...
.hand_kind       SKIP 1      \ ... and the kind shown

\ The tool belt (pack.py)
.belt            SKIP BELT_SLOTS \ A tool's kind or CELL_EMPTY, by belt key
.belt_slot       SKIP 1      \ The slot in the tool hand (follows belt)
ASSERT belt_slot = belt + BELT_SLOTS
.tools_held      SKIP 1      \ The belt key held last frame (1 on), or 0
.tool_pressed    SKIP 1      \ A belt key pressed this frame (1 on), or 0
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

\ Light (asm/miner_light.asm)
.light_dirty     SKIP 1      \ Non-zero if tiles changed since the last pass
.variables_end
