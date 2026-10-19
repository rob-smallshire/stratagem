\ Tube prototype 2: the smooth miner's light, for the parasite (modelled by
\ lighting.smooth_miner_light; timed by tests/test_smooth_light.py in a
\ 65C02 emulation).
\
\ Light is a level per block of two character cells (4 pixels by 8 lines),
\ from the middle of the miner's box: a radial table gives the level on open
\ ground, and each block loses its excess, from a grid filled by the tile
\ flood (as lighting.asm's), interpolated between tiles: soft shadows. A plane holds each block's level; a pass updates
\ the blocks within reach of the miner now or at the last pass, and queues
\ each cell whose change shows (a coloured pixel's threshold lies between
\ the old and new mask classes). A pass does nothing if neither the miner
\ nor the tiles have changed.
\
\ The parasite holds the world, so here a 32 x 32 tile map (wrapping) stands
\ in for it, holding a kind per tile; kind_clear and kind_visibility say
\ whether a kind lets light through and which thresholds each of its cells
\ shows. The miner may move at most a tile each way between passes.

INCLUDE "build/generated/light.asm"
INCLUDE "build/generated/player.asm"

PLANE_COLUMNS = 64              \ Blocks, wrapping: 32 tiles
PLANE_ROWS = 64                 \ Cell rows, wrapping: 32 tiles
MAP_SIZE = 32                   \ Tiles, wrapping
RADIAL_CENTRE = 64              \ The radial table's column for dx = 0
FAR = &FF                       \ The excess of a block beyond the pool: dark
QUEUE_SIZE = 255
GRID_RADIUS = MINER_RADIUS + 1  \ The pool's tiles, and a dark border
GRID_SPAN = 2 * GRID_RADIUS + 1
CELL_LINES = 8
BLOCK_PIXELS = 4
DATA_START = &B000              \ The plane, grid, map and queues: above the code
\ The grid: a page per tile row (oy + GRID_RADIUS), its cell rows
\ GRID_ROW_BYTES apart; a block's excess at column 8 (ox + GRID_RADIUS) +
\ 4 b, so that its offset from a block's radial column is fixed in a pass.
GRID_ROW_BYTES = 128
GRID_COLUMN = 8 * GRID_RADIUS - (BLOCK_PIXELS DIV 2 + RADIAL_CENTRE)

ORG &70
.sl_px              SKIP 2      \ In: the player's box, left pixel
.sl_py              SKIP 2      \ In: the top line
.sl_dirty           SKIP 1      \ In: non-zero if tiles changed
.sl_valid           SKIP 1      \ Non-zero once a pass has run
.sl_queue_count     SKIP 1      \ Out: cells queued (reset by the reader)
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
.sl_ty              SKIP 1
.sl_j               SKIP 1      \ The cell row within the tile row
.sl_v               SKIP 1      \ The cell row (low byte)
.sl_oy              SKIP 1      \ The tile row's offset from the miner (signed)
.sl_grid_offset     SKIP 2      \ From a grid row to the first block's excess, less Y
.sl_plane_ptr       SKIP 2
.sl_map_ptr         SKIP 2
.sl_ptr             SKIP 2
.sl_ptr2            SKIP 2
.sl_diff            SKIP 1
.sl_pair            SKIP 1      \ old * 16 + new
.sl_c               SKIP 1
.sl_save_x          SKIP 1
.sl_save_y          SKIP 1
.sl_tmp             SKIP 2
.sl_best            SKIP 1
.sl_clear_here      SKIP 1
.sl_tiles           SKIP 1      \ Tiles across, in a tile row
.sl_count           SKIP 1
.sl_vis_row         SKIP 1
.sl_vis_ptr         SKIP 2      \ Low byte always 0

CLEAR &1000, &F800
ORG &1000
.sl_begin

\ A pass: bring the plane up to date with the miner and the tiles.
.sl_update
{
    CLC                         \ The middle of the miner's box
    LDA sl_px
    ADC #PLAYER_WIDTH DIV 2
    STA sl_mx
    LDA sl_px + 1
    ADC #0
    STA sl_mx + 1
    CLC
    LDA sl_py
    ADC #PLAYER_HEIGHT DIV 2
    STA sl_my
    LDA sl_py + 1
    ADC #0
    STA sl_my + 1

    LDA sl_valid                \ Nothing to do if nothing has changed
    BEQ first
    LDA sl_dirty
    BNE changed
    LDA sl_mx
    CMP sl_pmx
    BNE changed
    LDA sl_mx + 1
    CMP sl_pmx + 1
    BNE changed
    LDA sl_my
    CMP sl_pmy
    BNE changed
    LDA sl_my + 1
    CMP sl_pmy + 1
    BNE changed
    RTS
.first
    JSR sl_clear_grid
    LDA sl_mx                   \ As if the miner had been here already
    STA sl_pmx
    LDA sl_mx + 1
    STA sl_pmx + 1
    LDA sl_my
    STA sl_pmy
    LDA sl_my + 1
    STA sl_pmy + 1
.changed
    LDA sl_mx                   \ The miner's tile
    STA sl_tmp
    LDA sl_mx + 1
    LSR A
    ROR sl_tmp
    LSR A
    ROR sl_tmp
    LSR A
    ROR sl_tmp
    LDA sl_tmp
    STA sl_cx
    LDA sl_my
    STA sl_tmp
    LDA sl_my + 1
    LSR A
    ROR sl_tmp
    LSR A
    ROR sl_tmp
    LSR A
    ROR sl_tmp
    LSR A
    ROR sl_tmp
    LDA sl_tmp
    STA sl_cy

    LDA sl_valid                \ The flood, if the miner has changed tile
    BEQ flood                   \ or the tiles have changed
    LDA sl_dirty
    BNE flood
    LDA sl_cx
    CMP sl_pcx
    BNE flood
    LDA sl_cy
    CMP sl_pcy
    BEQ flooded
.flood
    JSR sl_flood
.flooded
    LDA #0
    STA sl_dirty
    STA sl_vis_ptr

    LDA sl_mx                   \ The centres now and at the last pass,
    AND #7                      \ relative to the miner's tile (signed)
    STA sl_mxr
    LDA sl_pmx
    SEC
    SBC sl_mx
    CLC
    ADC sl_mxr
    STA sl_pmxr
    LDA sl_my
    AND #15
    STA sl_myr
    LDA sl_pmy
    SEC
    SBC sl_my
    CLC
    ADC sl_myr
    STA sl_pmyr
    LDA sl_mxr                  \ The span of each, across and down
    LDX sl_pmxr
    JSR sl_order
    STA sl_lo_x
    STX sl_hi_x
    LDA sl_myr
    LDX sl_pmyr
    JSR sl_order
    EOR #&80                    \ Down, biased to compare unsigned
    STA sl_lo_y
    TXA
    EOR #&80
    STA sl_hi_y

    LDA sl_myr                  \ |dy|'s parity is my's, for every row: so
    LSR A                       \ the radial table's low byte is fixed
    LDA #0
    ROR A
    STA sl_radial0 + 1
    ORA #BLOCK_PIXELS
    STA sl_radial1 + 1
    LDA sl_mxr                  \ The grid column of a block is its radial
    CLC                         \ column plus this
    ADC #LO(GRID_COLUMN)
    STA sl_grid_offset
    LDA #0
    ADC #HI(GRID_COLUMN)
    STA sl_grid_offset + 1

    JSR sl_rows
    LDA #&FF
    STA sl_valid
    LDA sl_cx
    STA sl_pcx
    LDA sl_cy
    STA sl_pcy
    LDA sl_mx
    STA sl_pmx
    LDA sl_mx + 1
    STA sl_pmx + 1
    LDA sl_my
    STA sl_pmy
    LDA sl_my + 1
    STA sl_pmy + 1
    RTS
}

\ Fill the grid with FAR, and the tiles' excess with MINER_LEVEL: the
\ border, beyond the pool, is never written.
.sl_clear_grid
{
    LDA #HI(sl_grid)
    STA sl_ptr + 1
    LDA #0
    STA sl_ptr
    LDX #GRID_SPAN
    LDA #FAR
    LDY #0
.loop
    STA (sl_ptr),Y
    INY
    BNE loop
    INC sl_ptr + 1
    DEX
    BNE loop
    LDA #MINER_LEVEL            \ And every tile beyond the pool dark
    LDX #GRID_SPAN * GRID_SPAN - 1
.tiles
    STA sl_tile_excess,X
    DEX
    BPL tiles
    RTS
}

\ The lesser of signed A and X in A, the greater in X.
.sl_order
{
    STA sl_tmp
    STX sl_tmp + 1
    SEC
    SBC sl_tmp + 1
    BVC no_overflow
    EOR #&80
.no_overflow
    BMI ordered                 \ A < X
    LDA sl_tmp + 1
    LDX sl_tmp
    RTS
.ordered
    LDA sl_tmp
    RTS
}

\ Each tile row within reach of the miner's centre now or at the last pass
\ (beyond, blocks are dark and were dark), and each tile across within reach.
.sl_rows
{
    LDA #&100 - GRID_RADIUS     \ The row's offset from the miner's tile
    STA sl_oy
.tile_row
    LDA sl_oy                   \ Its cell centres, down from the tile: a to a + 8
    ASL A
    ASL A
    ASL A
    ASL A
    CLC
    ADC #CELL_LINES DIV 2
    EOR #&80                    \ Biased
    STA sl_tmp
    CLC                         \ The distance down to the nearer centre
    ADC #CELL_LINES
    CMP sl_lo_y
    BCS not_above
    LDA sl_lo_y                 \ Above both
    SEC
    SBC sl_tmp
    SBC #CELL_LINES             \ Carry set
    JMP distance
.not_above
    LDA sl_tmp
    CMP sl_hi_y
    BCC overlaps
    BEQ overlaps
    SBC sl_hi_y                 \ Below both
    JMP distance
.overlaps
    LDA #0
.distance
    CMP #SMOOTH_REACH_ROWS
    BCS next_row
    TAX
    LDA smooth_reach,X          \ Tiles across: from (lo - reach) DIV 8
    STA sl_tmp
    LDA sl_lo_x
    SEC
    SBC sl_tmp
    JSR sl_divide8
    STA sl_tlo
    LDA sl_hi_x                 \ to (hi + reach - 1) DIV 8
    CLC
    ADC sl_tmp
    SEC
    SBC #1
    JSR sl_divide8
    SEC
    SBC sl_tlo
    CLC
    ADC #1
    STA sl_tiles
    CLC                         \ The tile row
    LDA sl_cy
    ADC sl_oy
    STA sl_ty
    AND #MAP_SIZE - 1           \ The map row
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(sl_map)
    STA sl_map_ptr + 1
    LDA sl_ty
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA sl_map_ptr
    LDA #0
    STA sl_j
.cell_row
    JSR sl_row
    INC sl_j
    LDA sl_j
    CMP #2
    BNE cell_row
.next_row
    INC sl_oy
    LDA sl_oy
    CMP #GRID_RADIUS + 1
    BEQ done
    JMP tile_row
.done
    RTS
}

\ Signed A DIV 8, rounding down.
.sl_divide8
{
    CMP #&80
    ROR A
    CMP #&80
    ROR A
    CMP #&80
    ROR A
    RTS
}

\ One cell row, v = 2 * sl_ty + sl_j, across the tiles within reach.
.sl_row
{
    LDA sl_ty                   \ v
    ASL A
    ORA sl_j
    STA sl_v
    LDA sl_oy                   \ dy = 16 oy + 8 j + 4 - myr, then |dy|
    ASL A
    ASL A
    ASL A
    ASL A
    ORA #CELL_LINES DIV 2
    LDX sl_j
    BEQ upper
    ORA #CELL_LINES
.upper
    SEC
    SBC sl_myr
    BPL positive
    EOR #&FF
    CLC
    ADC #1
.positive
    LSR A                       \ The radial row (its low byte is fixed)
    CLC
    ADC #HI(sl_radial)
    STA sl_radial0 + 2
    STA sl_radial1 + 2

    LDA sl_oy                   \ The grid row: page oy + GRID_RADIUS, then
    CLC                         \ the cell row's half
    ADC #HI(sl_grid) + GRID_RADIUS
    TAX
    LDA sl_j
    LSR A
    ROR A
    CLC
    ADC sl_grid_offset
    STA sl_excess0 + 1
    TXA
    ADC sl_grid_offset + 1
    STA sl_excess0 + 2
    LDA sl_excess0 + 1
    CLC
    ADC #BLOCK_PIXELS
    STA sl_excess1 + 1
    LDA sl_excess0 + 2
    ADC #0
    STA sl_excess1 + 2

    LDA sl_v                    \ The plane row: (v MOD PLANE_ROWS) * PLANE_COLUMNS
    AND #PLANE_ROWS - 1
    LSR A
    LSR A
    CLC
    ADC #HI(sl_plane)
    STA sl_plane0 + 2
    STA sl_plane1 + 2
    STA sl_plane_ptr + 1
    LDA sl_v
    AND #3
    LSR A
    ROR A
    ROR A
    STA sl_plane0 + 1
    STA sl_plane_ptr
    ORA #1
    STA sl_plane1 + 1

    LDA sl_j                    \ The visibility pages for this cell row
    ASL A
    ASL A
    CLC
    ADC #HI(sl_kind_visibility)
    STA sl_vis_row
    LDA sl_tiles
    STA sl_count

    LDA sl_cx                   \ The first tile's plane column
    CLC
    ADC sl_tlo
    ASL A
    AND #PLANE_COLUMNS - 1
    TAX
    LDA sl_tlo                  \ And its first block's radial column:
    ASL A                       \ 8 tlo + 2 - mxr + RADIAL_CENTRE
    ASL A
    ASL A
    CLC
    ADC #BLOCK_PIXELS DIV 2 + RADIAL_CENTRE
    SEC
    SBC sl_mxr
    TAY
    SEC

.tile
.*sl_radial0
    LDA sl_radial,Y
.*sl_excess0
    SBC sl_grid,Y
    BCS lit0
    LDA #0
    SEC
.lit0
.*sl_plane0
    EOR sl_plane,X
    BNE changed0
.back0
.*sl_radial1
    LDA sl_radial + BLOCK_PIXELS,Y
.*sl_excess1
    SBC sl_grid + BLOCK_PIXELS,Y
    BCS lit1
    LDA #0
    SEC
.lit1
.*sl_plane1
    EOR sl_plane + 1,X
    BNE changed1
.back1

    TYA                         \ The next tile
    ADC #8 - 1                  \ Carry set
    TAY
    TXA
    ADC #2                      \ Carry clear
    AND #PLANE_COLUMNS - 1
    TAX
    SEC
    DEC sl_count
    BNE tile
    RTS

.changed0
    STY sl_save_y
    LDY #0
    JSR sl_block_change
    LDY sl_save_y
    SEC
    JMP back0
.changed1
    STY sl_save_y
    LDY #1
    JSR sl_block_change
    LDY sl_save_y
    SEC
    JMP back1
}

\ Block Y of the tile whose first block is in plane column X has a new
\ level: its old level EOR A. Record it, and test each of its cells.
\ Preserves X.
.sl_block_change
{
    STA sl_diff
    TXA
    STY sl_c
    ORA sl_c
    TAY
    LDA (sl_plane_ptr),Y        \ old
    STA sl_tmp
    EOR sl_diff
    STA (sl_plane_ptr),Y        \ new
    LDY sl_tmp
    ORA sl_times16,Y            \ old * 16 + new
    STA sl_pair
    ASL sl_c                    \ The block's first cell
    TAY
    LDA smooth_between_even,Y
    BEQ second
    JSR sl_visible
.second
    INC sl_c
    LDY sl_pair
    LDA smooth_between_odd,Y
    BEQ done
    JMP sl_visible
.done
    RTS
}

\ Cell sl_c of the tile whose first block is in plane column X has a new
\ level, whose change moves its mask past the thresholds in A: queue the
\ cell if any of them falls on colour. Preserves X.
.sl_visible
{
    STA sl_tmp
    STX sl_save_x
    TXA                         \ The tile's kind, from the map
    LSR A
    TAY
    LDA (sl_map_ptr),Y
    TAY
    LDA sl_vis_row              \ Which of the thresholds fall on colour
    CLC
    ADC sl_c
    STA sl_vis_ptr + 1
    LDA (sl_vis_ptr),Y
    AND sl_tmp
    BEQ done
    LDX sl_queue_count
    CPX #QUEUE_SIZE
    BEQ done
    LDA sl_save_x               \ u: 4 tx + c
    ASL A
    ORA sl_c
    STA sl_queue_u,X
    LDA sl_c                    \ The block's level
    LSR A
    ORA sl_save_x
    TAY
    LDA (sl_plane_ptr),Y
    STA sl_queue_level,X
    LDA sl_v
    STA sl_queue_v,X
    INC sl_queue_count
.done
    LDX sl_save_x
    RTS
}

.sl_times16
FOR n, 0, 15
    EQUB n * 16
NEXT

\ The tile flood around the miner's tile, as lighting.miner_light, then each
\ tile's excess and each block's soft excess in the grid: unrolled, by
\ stratagem.gen_tables. First each window tile's clear flag, from the map.
.sl_flood
{
    LDX #0                      \ The window, row by row: X its index
    LDA #&100 - MINER_RADIUS
    STA sl_oy
.row
    CLC                         \ The map row
    LDA sl_cy
    ADC sl_oy
    STA sl_ty
    AND #MAP_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(sl_map)
    STA sl_map_ptr + 1
    LDA sl_ty
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA sl_map_ptr
    LDA sl_cx
    SEC
    SBC #MINER_RADIUS
    STA sl_tmp
    LDA #MINER_SPAN
    STA sl_count
.column
    LDA sl_tmp
    AND #MAP_SIZE - 1
    TAY
    LDA (sl_map_ptr),Y
    TAY
    LDA sl_kind_clear,Y
    LDY miner_index,X           \ In the flood's order
    STA sl_pool_clear,Y
    INX
    INC sl_tmp
    DEC sl_count
    BNE column
    INC sl_oy
    LDA sl_oy
    CMP #MINER_RADIUS + 1
    BNE row
    LDA #&FF                    \ The miner's own tile lets light out
    STA sl_pool_clear
}                               \ On into the generated flood
.sl_flood_entries
INCLUDE "build/generated/smooth_flood.asm"
.sl_flood_excess
{                               \ And on into each tile's excess (by row)
    LDX #MINER_WINDOW - 1
.excess
    LDA sl_pool,X
    BEQ dark
    LDA smooth_open_pool,X
    SEC
    SBC sl_pool,X
    BCS store
    LDA #0
    BEQ store
.dark
    LDA #MINER_LEVEL
.store
    LDY smooth_tile_index,X
    STA sl_tile_excess,Y
    DEX
    BPL excess

.*sl_flood_corners
    LDX #GRID_SPAN * GRID_SPAN - 1      \ Each tile's top left corner: the
.corner                                 \ four tiles' average (only those of
    LDA sl_tile_excess - GRID_SPAN - 1,X    \ the window's tiles are used)
    CLC
    ADC sl_tile_excess - GRID_SPAN,X
    ADC sl_tile_excess - 1,X
    ADC sl_tile_excess,X
    ADC #2
    LSR A
    LSR A
    STA sl_corner,X
    DEX
    CPX #GRID_SPAN + 1
    BCS corner

.*sl_flood_blocks
    LDA #&100 - MINER_RADIUS    \ Each block's soft excess: lighting.soft_blend,
    STA sl_oy                   \ half its tile's, half its nearest corner's
    LDX #GRID_SPAN + 1          \ The window's first tile
.block_row
    CLC                         \ The grid row: a page per tile row
    LDA sl_oy
    ADC #HI(sl_grid) + GRID_RADIUS
    STA up_left + 2
    STA up_right + 2
    STA down_left + 2
    STA down_right + 2
    LDY #8 * (GRID_RADIUS - MINER_RADIUS)
    LDA #MINER_SPAN
    STA sl_count
.block
    LDA sl_tile_excess,X
    SEC
    ADC sl_corner,X
    LSR A
.up_left
    STA sl_grid,Y
    LDA sl_tile_excess,X
    SEC
    ADC sl_corner + 1,X
    LSR A
.up_right
    STA sl_grid + BLOCK_PIXELS,Y
    LDA sl_tile_excess,X
    SEC
    ADC sl_corner + GRID_SPAN,X
    LSR A
.down_left
    STA sl_grid + GRID_ROW_BYTES,Y
    LDA sl_tile_excess,X
    SEC
    ADC sl_corner + GRID_SPAN + 1,X
    LSR A
.down_right
    STA sl_grid + GRID_ROW_BYTES + BLOCK_PIXELS,Y
    TYA                         \ The next tile
    CLC
    ADC #8
    TAY
    INX
    DEC sl_count
    BNE block
    INX                         \ Past the border, to the next row
    INX
    INC sl_oy
    LDA sl_oy
    CMP #MINER_RADIUS + 1
    BNE block_row
.done
    RTS
}

INCLUDE "build/generated/miner.asm"
INCLUDE "build/generated/smooth.asm"

.sl_pool            SKIP MINER_WINDOW
.sl_pool_clear      SKIP MINER_WINDOW
.sl_tile_excess     SKIP GRID_SPAN * GRID_SPAN  \ Row-major, with the border
.sl_corner          SKIP GRID_SPAN * GRID_SPAN  \ At each tile's top left

ALIGN &100
.sl_radial
INCBIN "build/generated/radial.bin"
.sl_end

ASSERT P% <= DATA_START
ORG DATA_START
.sl_plane           SKIP PLANE_COLUMNS * PLANE_ROWS
.sl_grid            SKIP GRID_SPAN * 256    \ Page per tile row: see GRID_ROW_BYTES
.sl_map             SKIP MAP_SIZE * MAP_SIZE
.sl_kind_visibility SKIP 256 * 8  \ Page j * 4 + c: cell (c, j) of each kind
.sl_kind_clear      SKIP 256
.sl_queue_u         SKIP 256
.sl_queue_v         SKIP 256
.sl_queue_level     SKIP 256

ASSERT P% <= &F800             \ Below the parasite's OS
SAVE "SMOOTH", sl_begin, sl_end, sl_update, sl_begin
