\ The parasite's zero page, below the mailbox at &8E (the light's follows it:
\ miner_light_zp.asm). Variables are declared with ORG/SKIP rather than as
\ constants so that beebasm exports them as labels, which the tests look up
\ by name. The host has its own (host_zeropage.asm).

ORG &00
GUARD &8E

.zp_ptr             SKIP 2      \ General purpose pointer

\ World workspace (used only by world code)
.zp_world_x         SKIP 1
.zp_world_y         SKIP 1
.zp_world_depth     SKIP 1
.zp_world_fine      SKIP 1
.zp_world_temp      SKIP 1
.zp_fill_x          SKIP 1      \ fill_cache: first tile
.zp_fill_y          SKIP 1
.zp_fill_count      SKIP 1      \ ... how many
.zp_fill_down       SKIP 1      \ ... non-zero for down a column, else along a row
.zp_fill_pointer    SKIP 2
.zp_world_pointer   SKIP 2      \ Directory entry, then slot
.zp_world_shape     SKIP 1      \ tile_at, generate_tile: the shape
.zp_world_tile      SKIP 1      \ set_tile: the new material...
.zp_world_new_shape SKIP 1      \ ... and shape
.zp_generate_x      SKIP 1      \ generate_tile: where
.zp_generate_y      SKIP 1
.zp_generate_material SKIP 1    \ ... the material there
.zp_generate_open   SKIP 1      \ ... which neighbours are open
.zp_world_target_x  SKIP 1      \ set_tile: where
.zp_world_target_y  SKIP 1
.zp_world_index     SKIP 1      \ set_tile: index into a slot being filled

\ Camera (modelled by tools/stratagem/camera.py)
.zp_input           SKIP 1      \ INPUT_* bits for this frame
.zp_focus_x         SKIP 2      \ Focus position, in pixels
.zp_focus_y         SKIP 2      \ ... and lines
.zp_lead            SKIP 1      \ Signed horizontal look-ahead, in columns
.zp_camera_x        SKIP 2      \ World cell at the top left of the view
.zp_camera_y        SKIP 2
.zp_plan_dx         SKIP 1      \ Signed camera movement for the next flip
.zp_plan_dy         SKIP 1
.zp_redraw          SKIP 1      \ Non-zero if the view must be redrawn
.zp_column          SKIP 2      \ Focus column (focus_x >> 1)
.zp_row             SKIP 2      \ Focus row (focus_y >> 3)
.zp_relative_x      SKIP 1      \ Focus column and row within the view
.zp_relative_y      SKIP 1

\ Player (modelled by tools/stratagem/player.py)
.zp_player_x        SKIP 2      \ Sixteenths of a pixel
.zp_player_y        SKIP 2      \ Sixteenths of a line
.zp_player_vx       SKIP 1      \ Signed sixteenths a frame
.zp_player_vy       SKIP 1
.zp_player_on_ground SKIP 1     \ Non-zero when standing on something
.zp_player_facing   SKIP 1      \ 1 right, &FF left
.zp_player_frame    SKIP 1      \ Sprite frame to draw
.zp_player_jump_held SKIP 1     \ Non-zero if UP was held last frame
.zp_player_air_jumps SKIP 1     \ Jumps left before landing
.zp_abilities       SKIP 1      \ ABILITY_* bits earned
.zp_direction       SKIP 1      \ Signed direction held: -1, 0 or 1
.zp_new_x           SKIP 2      \ Position being tried
.zp_new_y           SKIP 2
.zp_box_x           SKIP 2      \ Player box tested by box_free, in pixels
.zp_box_y           SKIP 2      \ ... and lines
.zp_box_right       SKIP 1      \ ... its tile columns and rows
.zp_box_bottom      SKIP 1
.zp_box_column      SKIP 1
.zp_box_row         SKIP 1
.zp_hit_any         SKIP 1      \ find_hits: non-zero if anything was hit
.zp_hit_left        SKIP 2      \ ... the extremes of what was hit
.zp_hit_right       SKIP 2
.zp_hit_top         SKIP 2
.zp_hit_bottom      SKIP 2
.zp_hit_relative_y  SKIP 1      \ ... the box's top relative to a tile row, + 24
.zp_hit_bits        SKIP 2      \ ... the quarter-cells hit in a tile
.zp_rect_left       SKIP 1      \ ... their extremes, within the tile
.zp_rect_right      SKIP 1
.zp_rect_top        SKIP 1
.zp_rect_bottom     SKIP 1
.zp_shape_ptr       SKIP 2      \ ... the tile cache row of shapes
.zp_was_on_ground   SKIP 1      \ On the ground before this frame's move
.zp_stop            SKIP 2      \ Where a blocked horizontal move stops
.zp_lift            SKIP 2      \ Height of a ledge to climb

\ Game
.zp_screen_start    SKIP 2      \ Screen address of the view's top-left cell
.zp_frame           SKIP 1      \ Incremented once per pass of the main loop
.zp_temp            SKIP 2
.zp_temp2           SKIP 2

