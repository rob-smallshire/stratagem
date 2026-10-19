\ Tube prototype 2: the smooth miner's light, for the parasite (modelled by
\ lighting.smooth_miner_light; timed by tests/test_smooth_light.py in a
\ 65C02 emulation).
\
\ Light is a level per character cell, from the middle of the miner's box:
\ a radial table gives the level on open ground, and each tile's cells lose
\ the excess cost of the path the tile flood (as lighting.asm) found. A
\ plane holds each cell's level; a pass updates the cells around the miner
\ now and at the last pass, and queues each cell whose change shows (a
\ coloured pixel's threshold lies between the old and new mask classes).
\
\ The parasite holds the world, so here a 32 x 32 tile map (wrapping) stands
\ in for it, holding a kind per tile; kind_clear and kind_visibility say
\ whether a kind lets light through and which thresholds each of its cells
\ shows. The miner may move at most a tile each way between passes.

INCLUDE "build/generated/light.asm"
INCLUDE "build/generated/player.asm"

PLANE_COLUMNS = 128             \ cells, wrapping: 32 tiles
PLANE_ROWS = 64
MAP_SIZE = 32                   \ tiles, wrapping
RADIAL_CENTRE = 64              \ the radial table's column for dx = 0
FAR = &FF                       \ excess for a tile beyond the pool: dark
QUEUE_SIZE = 255
GRID_RADIUS = MINER_RADIUS + 1  \ The pool's tiles, and a dark border
GRID_SPAN = 2 * GRID_RADIUS + 1
CELL_LINES = 8

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
.sl_oy              SKIP 1      \ The tile row's offset from the miner, + MINER_RADIUS
.sl_ex              SKIP 1      \ The tile's excess
.sl_plane_ptr       SKIP 2
.sl_map_ptr         SKIP 2
.sl_ptr             SKIP 2
.sl_diff            SKIP 1
.sl_c               SKIP 1
.sl_save_x          SKIP 1
.sl_save_y          SKIP 1
.sl_tmp             SKIP 2
.sl_index           SKIP 1      \ Flood: the window entry
.sl_best            SKIP 1
.sl_clear_here      SKIP 1
.sl_tiles           SKIP 1      \ Tiles across the tiles to cover
.sl_count           SKIP 1
.sl_vis_row         SKIP 1
.sl_vis_ptr         SKIP 2      \ Low byte always 0

CLEAR &1000, &C000
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
    LDA sl_mx                   \ Its tile
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

    LDA sl_valid                \ The tiles to cover: around the miner now,
    BEQ alone                   \ and at the last pass
    LDA sl_cx
    CMP sl_pcx
    BNE flood
    LDA sl_cy
    CMP sl_pcy
    BNE flood
    LDA sl_dirty
    BEQ bounds
.flood
    JSR sl_flood
    JMP bounds
.alone
    JSR sl_flood
    LDA sl_cx
    STA sl_pcx
    LDA sl_cy
    STA sl_pcy
.bounds
    LDA #0
    STA sl_dirty
    STA sl_vis_ptr
    LDA sl_valid                \ The centre at the last pass, or now
    BNE relative
    LDA sl_mx
    STA sl_pmx
    LDA sl_mx + 1
    STA sl_pmx + 1
    LDA sl_my
    STA sl_pmy
    LDA sl_my + 1
    STA sl_pmy + 1
.relative
    LDA sl_mx                   \ Both, relative to the miner's tile (signed)
    AND #7
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
\ (beyond, cells are dark and were dark), and each tile across within reach.
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
    ADC #4
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

\ One cell row, v = 2 * sl_ty + sl_j, across the tiles to cover.
.sl_row
{
    LDA sl_ty                   \ v
    ASL A
    ORA sl_j
    STA sl_v
    LDA sl_ty                   \ dy = 16 ty + 8 j + 4 - my, then |dy|
    STA sl_tmp
    LDA #0
    STA sl_tmp + 1
    ASL sl_tmp
    ROL sl_tmp + 1
    ASL sl_tmp
    ROL sl_tmp + 1
    ASL sl_tmp
    ROL sl_tmp + 1
    ASL sl_tmp
    ROL sl_tmp + 1
    LDA sl_j
    ASL A
    ASL A
    ASL A
    ORA #4
    ORA sl_tmp
    SEC
    SBC sl_my
    TAX
    LDA sl_tmp + 1
    SBC sl_my + 1
    BPL positive
    TXA
    EOR #&FF
    CLC
    ADC #1
    TAX
.positive
    TXA                         \ The radial row: |dy| * RADIAL_COLUMNS
    LSR A
    CLC
    ADC #HI(sl_radial)
    STA sl_radial0 + 2
    STA sl_radial1 + 2
    STA sl_radial2 + 2
    STA sl_radial3 + 2
    TXA
    AND #1
    LSR A
    ROR A
    STA sl_radial0 + 1
    ORA #2
    STA sl_radial1 + 1
    EOR #2 OR 4
    STA sl_radial2 + 1
    ORA #2
    STA sl_radial3 + 1

    LDA sl_v                    \ The plane row: (v MOD PLANE_ROWS) * PLANE_COLUMNS
    AND #PLANE_ROWS - 1
    LSR A
    CLC
    ADC #HI(sl_plane)
    STA sl_plane0 + 2
    STA sl_plane1 + 2
    STA sl_plane2 + 2
    STA sl_plane3 + 2
    STA sl_old0 + 2
    STA sl_old1 + 2
    STA sl_old2 + 2
    STA sl_old3 + 2
    STA sl_new0 + 2
    STA sl_new1 + 2
    STA sl_new2 + 2
    STA sl_new3 + 2
    STA sl_plane_ptr + 1
    LDA sl_j
    LSR A
    ROR A
    STA sl_plane0 + 1
    STA sl_old0 + 1
    STA sl_new0 + 1
    STA sl_plane_ptr
    ORA #1
    STA sl_plane1 + 1
    STA sl_old1 + 1
    STA sl_new1 + 1
    EOR #1 OR 2
    STA sl_plane2 + 1
    STA sl_old2 + 1
    STA sl_new2 + 1
    ORA #1
    STA sl_plane3 + 1
    STA sl_old3 + 1
    STA sl_new3 + 1

    LDA sl_j                    \ The visibility pages for this cell row
    ASL A
    ASL A
    CLC
    ADC #HI(sl_kind_visibility)
    STA sl_vis_row
    LDA sl_oy                   \ The first tile's excess, in the grid
    CLC
    ADC #GRID_RADIUS
    TAX
    LDA sl_times_grid,X
    CLC
    ADC #LO(sl_grid) + GRID_RADIUS
    CLC
    ADC sl_tlo
    STA sl_excess_load + 1
    LDA sl_tiles
    STA sl_count

    LDA sl_cx                   \ Its plane column
    CLC
    ADC sl_tlo
    ASL A
    ASL A
    AND #PLANE_COLUMNS - 1
    TAX
    LDA sl_tlo                  \ And its radial column:
    ASL A                       \ 8 tlo + 1 - mxr + RADIAL_CENTRE
    ASL A
    ASL A
    SEC
    ADC #RADIAL_CENTRE          \ With the carry: + 1
    SEC
    SBC sl_mxr
    TAY

.tile
.*sl_excess_load
    LDA sl_grid
    STA sl_ex
    INC sl_excess_load + 1
    SEC

.*sl_radial0
    LDA sl_radial,Y
    SBC sl_ex
    BCS lit0
    LDA #0
    SEC
.lit0
.*sl_plane0
    EOR sl_plane,X
    BNE changed0
.back0
.*sl_radial1
    LDA sl_radial + 2,Y
    SBC sl_ex
    BCS lit1
    LDA #0
    SEC
.lit1
.*sl_plane1
    EOR sl_plane + 1,X
    BNE changed1
.back1
.*sl_radial2
    LDA sl_radial + 4,Y
    SBC sl_ex
    BCS lit2
    LDA #0
    SEC
.lit2
.*sl_plane2
    EOR sl_plane + 2,X
    BNE changed2
.back2
.*sl_radial3
    LDA sl_radial + 6,Y
    SBC sl_ex
    BCS lit3
    LDA #0
    SEC
.lit3
.*sl_plane3
    EOR sl_plane + 3,X
    BNE changed3
.back3

    TYA                         \ The next tile
    ADC #8 - 1                  \ Carry set
    TAY
    TXA
    ADC #4                      \ Carry clear
    AND #PLANE_COLUMNS - 1
    TAX
    DEC sl_count
    BNE tile
    RTS

.changed0
    STY sl_save_y
    STA sl_diff
.*sl_old0
    LDA sl_plane + 0,X
    TAY
    EOR sl_diff
.*sl_new0
    STA sl_plane + 0,X
    ORA sl_times16,Y            \ old * 16 + new
    TAY
    LDA smooth_between_even,Y
    BEQ quiet0
    LDY #0
    JSR sl_visible
.quiet0
    LDY sl_save_y
    SEC
    JMP back0
.changed1
    STY sl_save_y
    STA sl_diff
.*sl_old1
    LDA sl_plane + 1,X
    TAY
    EOR sl_diff
.*sl_new1
    STA sl_plane + 1,X
    ORA sl_times16,Y            \ old * 16 + new
    TAY
    LDA smooth_between_odd,Y
    BEQ quiet1
    LDY #1
    JSR sl_visible
.quiet1
    LDY sl_save_y
    SEC
    JMP back1
.changed2
    STY sl_save_y
    STA sl_diff
.*sl_old2
    LDA sl_plane + 2,X
    TAY
    EOR sl_diff
.*sl_new2
    STA sl_plane + 2,X
    ORA sl_times16,Y            \ old * 16 + new
    TAY
    LDA smooth_between_even,Y
    BEQ quiet2
    LDY #2
    JSR sl_visible
.quiet2
    LDY sl_save_y
    SEC
    JMP back2
.changed3
    STY sl_save_y
    STA sl_diff
.*sl_old3
    LDA sl_plane + 3,X
    TAY
    EOR sl_diff
.*sl_new3
    STA sl_plane + 3,X
    ORA sl_times16,Y            \ old * 16 + new
    TAY
    LDA smooth_between_odd,Y
    BEQ quiet3
    LDY #3
    JSR sl_visible
.quiet3
    LDY sl_save_y
    SEC
    JMP back3
}

\ Cell Y of the tile whose plane column is X has a new level, whose change
\ moves the mask past the thresholds in A: queue the cell if any of them
\ falls on colour. Preserves X.
.sl_visible
{
    STA sl_tmp
    STY sl_c
    STX sl_save_x
    TXA                         \ The tile's kind, from the map
    LSR A
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
    LDA sl_save_x
    ORA sl_c
    STA sl_queue_u,X
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

\ The tile flood around the miner's tile, as lighting.asm's compute_pool but
\ from the map, then each tile's excess: the open-ground level less the
\ pool's (at least 0), or FAR where the pool doesn't reach.
.sl_flood
{
    LDX #0
.loop
    STX sl_index
    CPX #0
    BNE not_centre
    LDA #MINER_LEVEL
    STA sl_pool
    LDA #&FF
    STA sl_pool_clear
    JMP next
.not_centre
    CLC                         \ The tile's kind, from the map
    LDA sl_cy
    ADC miner_dy,X
    AND #MAP_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(sl_map)
    STA sl_ptr + 1
    CLC
    LDA sl_cy
    ADC miner_dy,X
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA sl_ptr
    CLC
    LDA sl_cx
    ADC miner_dx,X
    AND #MAP_SIZE - 1
    TAY
    LDA (sl_ptr),Y
    TAY
    LDA sl_kind_clear,Y
    STA sl_clear_here
    LDA #0
    STA sl_best
    LDA miner_across,X
    JSR sl_from_orthogonal
    LDX sl_index
    LDA miner_vertical,X
    JSR sl_from_orthogonal
    LDA sl_clear_here           \ Diagonally only into an open tile, from an
    BEQ store                   \ open one, past an open corner
    LDX sl_index
    LDY miner_diagonal,X
    CPY #LIGHT_NO_TILE
    BEQ store
    LDA sl_pool_clear,Y
    BEQ store
    LDY miner_across,X
    LDA sl_pool_clear,Y
    BNE corner_open
    LDY miner_vertical,X
    LDA sl_pool_clear,Y
    BEQ store
.corner_open
    LDY miner_diagonal,X
    LDA sl_pool,Y
    SEC
    SBC #LIGHT_OPEN_DIAGONAL_STEP
    JSR sl_consider
.store
    LDX sl_index
    LDA sl_best
    STA sl_pool,X
    LDA sl_clear_here
    STA sl_pool_clear,X
.next
    LDX sl_index
    INX
    CPX #MINER_WINDOW
    BEQ pooled
    JMP loop

.pooled
    LDX #MINER_WINDOW - 1       \ The excess of each tile
.excess
    LDA sl_pool,X
    BEQ far
    LDA smooth_open_pool,X
    SEC
    SBC sl_pool,X
    BCS store_excess
    LDA #0
    BEQ store_excess
.far
    LDA #FAR
.store_excess
    STA sl_excess,X
    DEX
    BPL excess

    LDA #FAR                    \ The grid, dark beyond the pool
    LDX #GRID_SPAN * GRID_SPAN - 1
.clear_grid
    STA sl_grid,X
    DEX
    BPL clear_grid
    LDY #MINER_WINDOW - 1
.grid
    CLC
    LDA miner_dy,Y
    ADC #GRID_RADIUS
    TAX
    LDA sl_times_grid,X
    CLC
    ADC #GRID_RADIUS
    CLC
    ADC miner_dx,Y
    TAX
    LDA sl_excess,Y
    STA sl_grid,X
    DEY
    BPL grid
    RTS
}

.sl_times_grid
FOR n, 0, GRID_SPAN - 1
    EQUB n * GRID_SPAN
NEXT

\ As from_orthogonal in lighting.asm.
.sl_from_orthogonal
{
    CMP #LIGHT_NO_TILE
    BEQ done
    TAY
    LDA sl_pool_clear,Y
    BEQ from_wall
    LDA sl_pool,Y
    LDX sl_clear_here
    BEQ into_wall
    SEC
    SBC #LIGHT_OPEN_STEP
    JMP sl_consider
.into_wall
    SEC
    JMP sl_consider
.from_wall
    LDA sl_clear_here
    BNE done
    LDA sl_pool,Y
    SEC
    SBC #LIGHT_WALL_STEP
    JMP sl_consider
.done
    RTS
}

.sl_consider
{
    BCC done
    CMP sl_best
    BCC done
    STA sl_best
.done
    RTS
}

INCLUDE "build/generated/miner.asm"
INCLUDE "build/generated/smooth.asm"

.sl_pool            SKIP MINER_WINDOW
.sl_pool_clear      SKIP MINER_WINDOW
.sl_excess          SKIP MINER_WINDOW
IF HI(P%) <> HI(P% + GRID_SPAN * GRID_SPAN - 1)
    ALIGN &100
ENDIF
.sl_grid            SKIP GRID_SPAN * GRID_SPAN
ASSERT HI(sl_grid) = HI(P% - 1)     \ Stepped through by its low byte

ALIGN &100
.sl_radial
INCBIN "build/generated/radial.bin"
.sl_end

ORG &8000
.sl_plane           SKIP PLANE_COLUMNS * PLANE_ROWS
.sl_map             SKIP MAP_SIZE * MAP_SIZE
.sl_kind_visibility SKIP 256 * 8  \ Page j * 4 + c: cell (c, j) of each kind
.sl_kind_clear      SKIP 256
.sl_queue_u         SKIP 256
.sl_queue_v         SKIP 256
.sl_queue_level     SKIP 256

SAVE "SMOOTH", sl_begin, sl_end, sl_update, sl_begin
