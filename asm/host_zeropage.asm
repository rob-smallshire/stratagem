\ The Tube game's host zero page. With the Tube on, the host's Tube code
\ owns &00-&56 (its variables, then its idle loop and error handler) and the
\ OS &90 upwards, leaving &57-&8F: the renderer's pointers, and what it and
\ the view's drawing read most. The rest of the host's variables are in low
\ RAM (host_low.asm), outside &3000-&7FFF, which render code can't see.

ORG &57
GUARD &90
.zp_screen          SKIP 2      \ Renderer workspace (see zeropage.asm)
.zp_screen_lower    SKIP 2
.zp_tile            SKIP 2
.zp_row_pointer     SKIP 2
.zp_shape_row_pointer SKIP 2
.zp_offsets_pointer SKIP 2
.zp_light_row_pointer SKIP 2
.zp_mask            SKIP 2
.zp_ptr             SKIP 2
.zp_temp            SKIP 2
.zp_render_u        SKIP 1      \ Render parameters
.zp_render_v        SKIP 1
.zp_render_count    SKIP 1
.zp_render_width    SKIP 1
.zp_render_base     SKIP 2
.zp_render_shape    SKIP 1
.zp_render_light    SKIP 1
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
