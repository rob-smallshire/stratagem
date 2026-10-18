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
.zp_screen          SKIP 2      \ Screen address of the current tile's top half
.zp_screen_lower    SKIP 2      \ ... and of its bottom half
.zp_tile            SKIP 2      \ Graphics of the current tile's top half
.zp_tile_lower      SKIP 2      \ ... and of its bottom half
.zp_render_index    SKIP 1      \ Index into the strip

\ World generator workspace (used only by world code)
.zp_world_x         SKIP 1
.zp_world_y         SKIP 1
.zp_world_depth     SKIP 1
.zp_world_fine      SKIP 1
.zp_world_temp      SKIP 1

\ Game
.zp_view_x          SKIP 1      \ World tile at the top left of the view
.zp_view_y          SKIP 1
.zp_screen_start    SKIP 2      \ Screen address of the view's top-left tile
.zp_frame           SKIP 1      \ Incremented once per pass of the main loop
.zp_scroll_timer    SKIP 1      \ Frames until the view may scroll again
.zp_strip_x         SKIP 1      \ World position of the strip being filled
.zp_strip_y         SKIP 1
.zp_strip_index     SKIP 1

\ Values of zp_machine
MACHINE_MODEL_B   = 0
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS    = 2
MACHINE_MASTER    = 3
