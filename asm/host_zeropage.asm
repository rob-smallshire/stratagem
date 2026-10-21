\ The Tube game's host zero page. With the Tube on, the host's Tube code
\ owns &00-&56 (its variables, then its idle loop and error handler) and the
\ OS &90 upwards, leaving &57-&8F: the renderer's pointers, and what it and
\ the view's drawing read most. The rest of the host's variables are in low
\ RAM (host_low.asm), outside &3000-&7FFF, which render code can't see.

ORG &57
GUARD &90
.zp_screen          SKIP 2      \ Renderer workspace: the current cell's screen address
.zp_screen_lower    SKIP 2      \ ... a second screen address
.zp_tile            SKIP 2      \ ... the current cell's graphics
.zp_row_pointer     SKIP 2      \ ... the tile cache row being drawn: materials
.zp_shape_row_pointer SKIP 2    \ ... shapes
.zp_offsets_pointer SKIP 2      \ ... the CELL_OFFSETS row for a cell
.zp_light_row_pointer SKIP 2    \ ... light
.zp_mask            SKIP 2      \ ... the dither masks for the cell
.zp_ptr             SKIP 2
.zp_temp            SKIP 2
.zp_render_u        SKIP 1      \ Render parameters: world cell column (low 7 bits)
.zp_render_v        SKIP 1      \ ... world cell row (low 6 bits)
.zp_render_count    SKIP 1      \ ... cells along a row, or rows down columns
.zp_render_width    SKIP 1      \ ... columns side by side (render_columns)
.zp_render_base     SKIP 2      \ ... the first cell's screen address
.zp_render_shape    SKIP 1      \ ... the shape of the tile being drawn
.zp_render_light    SKIP 1      \ ... and its light, scaled
.zp_sprite_address  SKIP 2
.zp_sprite_frame    SKIP 1
.zp_screen_start    SKIP 2      \ The view (from the parasite's packets)
.zp_camera_x        SKIP 2
.zp_camera_y        SKIP 2
.zp_plan_dx         SKIP 1
.zp_plan_dy         SKIP 1
.zp_columns_width   SKIP 1
.zp_columns_u       SKIP 1
.zp_columns_base    SKIP 2
.zp_split_row       SKIP 1
.zp_sprite_drawn    SKIP 1
.zp_rows_left       SKIP 1
.zp_box_x           SKIP 2      \ The player
.zp_box_y           SKIP 2
.zp_player_x        SKIP 2
.zp_player_y        SKIP 2
.zp_player_frame    SKIP 1
.zp_romsel_render   SKIP 1      \ Paging
.zp_romsel_game     SKIP 1
