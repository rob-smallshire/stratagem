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
.ramp_shape      SKIP 1      \ The ramp to shape the step into, or 0
.ground          SKIP 2      \ The line just below the player's feet
.left_column     SKIP 1      \ The columns of the player's edges
.right_column    SKIP 1
.rect_left       SKIP 2      \ A rectangle of the path, in pixels and lines
.rect_right      SKIP 2
.rect_top        SKIP 2
.rect_bottom     SKIP 2
.keep_row        SKIP 1      \ Tiles never cleared: this row, these columns
.keep_first      SKIP 1
.keep_last       SKIP 1
.scan_row        SKIP 1      \ first_obstruction: the row being scanned
.first_row       SKIP 1
.first_column    SKIP 1
.last_column     SKIP 1
.span_first      SKIP 1      \ region_mask: the first column or row
