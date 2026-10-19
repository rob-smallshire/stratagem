\ The miner's light's zero page, on the parasite (asm/miner_light.asm).

ORG &90
.sl_mx              SKIP 2      \ The middle of the miner's box
.sl_my              SKIP 2
.sl_cx              SKIP 1      \ The miner's tile
.sl_cy              SKIP 1
.sl_pcx             SKIP 1      \ The miner's tile at the last pass
.sl_pcy             SKIP 1
.sl_pmx             SKIP 2      \ The middle of the miner's box at the last pass
.sl_pmy             SKIP 2
.sl_mxr             SKIP 1      \ Both, relative to the miner's tile (signed)
.sl_myr             SKIP 1
.sl_pmxr            SKIP 1
.sl_pmyr            SKIP 1
.sl_lo_x            SKIP 1      \ Their span across (signed)
.sl_hi_x            SKIP 1
.sl_lo_y            SKIP 1      \ And down (signed, biased by &80)
.sl_hi_y            SKIP 1
.sl_tlo             SKIP 1      \ The row's first tile, relative (signed)
.sl_tx              SKIP 1      \ The tile being worked
.sl_ty              SKIP 1
.sl_j               SKIP 1      \ The cell row within the tile row
.sl_v               SKIP 2      \ The cell row
.sl_oy              SKIP 1      \ The tile row's offset from the miner (signed)
.sl_grid_offset     SKIP 2      \ From a grid row to the first block's excess, less Y
.sl_plane_ptr       SKIP 2
.sl_map_ptr         SKIP 2      \ The tile cache row: materials
.sl_shape_ptr       SKIP 2      \ ... shapes
.sl_light_ptr       SKIP 2      \ ... daylight
.sl_ptr             SKIP 2
.sl_ptr2            SKIP 2
.sl_list_ptr        SKIP 2      \ The draw list's next entry
.sl_diff            SKIP 1
.sl_old             SKIP 1
.sl_new             SKIP 1
.sl_day             SKIP 1
.sl_pair            SKIP 1      \ old * 16 + new, as shown
.sl_page            SKIP 1      \ The tile's graphics page: material * 2 + sky
.sl_shape           SKIP 1
.sl_offset          SKIP 1      \ The cell's graphic in its page
.sl_bits            SKIP 1
.sl_c               SKIP 1
.sl_save_x          SKIP 1
.sl_save_y          SKIP 1
.sl_tmp             SKIP 2
.sl_best            SKIP 1
.sl_tiles           SKIP 1      \ Tiles across, in a tile row
.sl_count           SKIP 1
.sl_list_count      SKIP 1      \ Cells on the draw list
.sl_col_lo          SKIP 1      \ The view columns the list may draw in
.sl_col_hi          SKIP 1
.sl_valid           SKIP 1      \ Non-zero once a pass has run
.sl_force           SKIP 1      \ Non-zero if blocks were reset: pass anyway
ASSERT P% <= &E6                \ Then the packet's pointers (parasite.asm)
