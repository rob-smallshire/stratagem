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

\ Renderer workspace (used only by render code)
.zp_screen          SKIP 2      \ Screen address of the current cell
.zp_screen_lower    SKIP 2      \ A second screen address
.zp_tile            SKIP 2      \ Graphics of the current cell

\ World generator workspace (used only by world code)
.zp_world_x         SKIP 1
.zp_world_y         SKIP 1
.zp_world_depth     SKIP 1
.zp_world_fine      SKIP 1
.zp_world_temp      SKIP 1

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

\ Game
.zp_screen_start    SKIP 2      \ Screen address of the view's top-left cell
.zp_frame           SKIP 1      \ Incremented once per pass of the main loop
.zp_marker_address  SKIP 2      \ Screen address of the marker's top line
.zp_marker_drawn    SKIP 1      \ Non-zero while the marker is on the screen
.zp_columns_planned SKIP 1      \ New columns to draw at the next flip
.zp_cell_u          SKIP 2      \ World cell being prepared
.zp_cell_v          SKIP 2
.zp_cell_count      SKIP 1      \ Cells still to prepare
.zp_cell_down       SKIP 1      \ Non-zero to prepare down a column
.zp_cell_tile       SKIP 1      \ The tile the cell is in
.zp_cell_index      SKIP 1      \ Index into the cell list
.zp_rows_left       SKIP 1      \ Rows still to draw in a redraw
.zp_view_column     SKIP 1      \ View column of a new column being prepared
.zp_new_column      SKIP 1      \ Which of the new columns
.zp_temp            SKIP 2

\ Values of zp_machine
MACHINE_MODEL_B   = 0
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS    = 2
MACHINE_MASTER    = 3
