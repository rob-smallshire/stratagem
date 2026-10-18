\ Zero page allocation.
\
\ The OS stays resident, so we use only &00-&8F, the language and user
\ area. Variables are declared with ORG/SKIP rather than as constants so
\ that beebasm exports them as labels, which the tests look up by name.

BOOT_READY = &FF                \ zp_boot_status once initialisation is done

ORG &00
GUARD &90

\ Machine and paging
.zp_boot_status     SKIP 1      \ Zero while starting, BOOT_READY when ready
.zp_machine         SKIP 1      \ One of the MACHINE_* constants
.zp_ptr             SKIP 2      \ General purpose pointer
.zp_romsel_game     SKIP 1      \ ROMSEL while game code runs: the game bank
.zp_romsel_render   SKIP 1      \ ROMSEL while render code runs: render bank + bit 7
.zp_bank_world      SKIP 1      \ ROMSEL for the world bank

\ Render parameters, set by the game before calling a render routine
.zp_render_u        SKIP 1      \ World cell column (only the low 7 bits matter)
.zp_render_v        SKIP 1      \ World cell row (only the low 6 bits matter)
.zp_render_count    SKIP 1      \ Cells along a row, or rows down columns
.zp_render_width    SKIP 1      \ Columns side by side (render_columns)
.zp_render_base     SKIP 2      \ Screen address of the first cell

\ Renderer workspace (used only by render code)
.zp_screen          SKIP 2      \ Screen address of the current cell
.zp_screen_lower    SKIP 2      \ A second screen address
.zp_tile            SKIP 2      \ Graphics of the current cell
.zp_row_pointer     SKIP 2      \ The tile cache row being drawn
.zp_render_half     SKIP 1      \ 0 or 32: the half of the tile being drawn
.zp_render_column   SKIP 1      \ World cell column being drawn
.zp_render_across   SKIP 1      \ Columns still to draw across a row

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
.zp_world_tile      SKIP 1      \ set_tile: the new tile
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
.zp_direction       SKIP 1      \ Signed direction held: -1, 0 or 1
.zp_new_x           SKIP 2      \ Position being tried
.zp_new_y           SKIP 2
.zp_box_x           SKIP 2      \ Player box tested by box_free, in pixels
.zp_box_y           SKIP 2      \ ... and lines
.zp_box_right       SKIP 1      \ ... its tile columns and rows
.zp_box_bottom      SKIP 1
.zp_box_column      SKIP 1
.zp_box_row         SKIP 1

\ Digging and placing (modelled by tools/stratagem/actions.py)
.zp_inventory       SKIP 1      \ Blocks carried
.zp_cooldown        SKIP 1      \ Frames until the next dig or place
.zp_action          SKIP 1      \ What was done this frame: 0, 1 dig, 2 place
.zp_target_x        SKIP 1      \ The tile aimed at
.zp_target_y        SKIP 1
.zp_want            SKIP 1      \ Aiming for: 0 diggable, otherwise empty
.zp_action_frames   SKIP 1      \ Cooldown for a dig

\ Tile cache: the tile rectangle it holds, inclusive
.zp_cached_left     SKIP 1
.zp_cached_right    SKIP 1
.zp_cached_top      SKIP 1
.zp_cached_bottom   SKIP 1
.zp_view_left       SKIP 1      \ The tile rectangle the view needs
.zp_view_right      SKIP 1
.zp_view_top        SKIP 1
.zp_view_bottom     SKIP 1

\ Game
.zp_screen_start    SKIP 2      \ Screen address of the view's top-left cell
.zp_frame           SKIP 1      \ Incremented once per pass of the main loop
.zp_sprite_address  SKIP 2      \ Screen address of the sprite's top line
.zp_sprite_frame    SKIP 1      \ The frame drawn there
.zp_sprite_drawn    SKIP 1      \ Non-zero while the sprite is on the screen
.zp_columns_width   SKIP 1      \ New columns to draw at the next flip...
.zp_columns_u       SKIP 1      \ ... from this world column
.zp_columns_base    SKIP 2      \ ... at this screen address
.zp_rows_left       SKIP 1      \ Rows still to draw in a redraw
.zp_temp            SKIP 2

\ Values of zp_machine
MACHINE_MODEL_B   = 0
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS    = 2
MACHINE_MASTER    = 3
