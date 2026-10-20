\ The miner's light, on the parasite: lighting.smooth_miner_light (soft
\ shadows), brightened by daylight, drawn by the host from a draw list.
\
\ Light is a level per block of two character cells (4 pixels by 8 lines),
\ from the middle of the miner's box: a radial table gives the level on open
\ ground, and each block loses its excess (sl_grid), filled by the tile flood
\ when the miner enters a tile or tiles change, interpolated between tiles.
\ A plane holds each block's miner's level; 0 also means "drawn as daylight
\ alone", which is how the host draws new rows and columns and changed tiles
\ (see sl_reset_*). A pass updates the blocks within reach of the miner now
\ or at the last pass; where a block's level changes, each of its cells
\ whose look changes (the brighter of the tile's daylight and the miner's
\ level, through the cell's graphic) goes on the draw list, with its screen
\ address, if it is in the view and not in a column drawn after the list.
\
\ Tiles outside the tile cache are unlit and opaque (as miner_light's
\ `inside`): the cache holds the view's tiles, and beyond the view light
\ isn't seen.

PLANE_COLUMNS = 64              \ Blocks, wrapping: 32 tiles
PLANE_ROWS = 64                 \ Cell rows, wrapping: 32 tiles
RADIAL_CENTRE = 64              \ The radial table's column for dx = 0
FAR = &FF                       \ The excess of a block beyond the pool: dark
GRID_RADIUS = MINER_RADIUS + 1  \ The pool's tiles, and a dark border
GRID_SPAN = 2 * GRID_RADIUS + 1
CELL_LINES = 8
BLOCK_PIXELS = 4
\ The grid: a page per tile row (oy + GRID_RADIUS), its cell rows
\ GRID_ROW_BYTES apart; a block's excess at column 8 (ox + GRID_RADIUS) +
\ 4 b, so that its offset from a block's radial column is fixed in a pass.
GRID_ROW_BYTES = 128
GRID_COLUMN = 8 * GRID_RADIUS - (BLOCK_PIXELS DIV 2 + RADIAL_CENTRE)


\ ---------------------------------------------------------------------------

\ Start: no pass yet, every block dark.
.sl_init
{
    LDA #0
    STA sl_valid
    STA sl_force
    TAY
    LDX #HI(PLANE_COLUMNS * PLANE_ROWS)
    STA sl_ptr
    LDA #HI(sl_plane)
    STA sl_ptr + 1
    TYA
.loop
    STA (sl_ptr),Y
    INY
    BNE loop
    INC sl_ptr + 1
    DEX
    BNE loop
    RTS
}

\ A pass: bring the plane up to date with the miner and the tiles, and list
\ the cells to redraw (at sl_list_ptr, counting sl_list_count).
.sl_update
{
    JSR player_pixels
    CLC                         \ The middle of the miner's box
    LDA zp_box_x
    ADC #PLAYER_WIDTH DIV 2
    STA sl_mx
    LDA zp_box_x + 1
    ADC #0
    STA sl_mx + 1
    CLC
    LDA zp_box_y
    ADC #PLAYER_HEIGHT DIV 2
    STA sl_my
    LDA zp_box_y + 1
    ADC #0
    STA sl_my + 1

    LDA sl_valid                \ Nothing to do if nothing has changed
    BEQ first
    LDA light_dirty
    ORA sl_force
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
    LDA #0
    STA sl_force
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
    LDA light_dirty
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
    STA light_dirty

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

\ Point sl_map_ptr, sl_shape_ptr and sl_light_ptr at the tile cache row of
\ tile row A.
.sl_cache_row
{
    PHA
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA sl_map_ptr + 1
    ADC #HI(tile_cache_shapes - tile_cache)
    STA sl_shape_ptr + 1
    ADC #HI(tile_cache_light - tile_cache_shapes)
    STA sl_light_ptr + 1
    PLA
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA sl_map_ptr
    STA sl_shape_ptr
    STA sl_light_ptr
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
    JSR sl_cache_row
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
    LDA #0
    ROL A
    STA sl_v + 1
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

    LDA sl_tiles
    STA sl_count
    LDA sl_cx                   \ The first tile
    CLC
    ADC sl_tlo
    STA sl_tx
    ASL A                       \ Its plane column
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
    INC sl_tx
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

\ Block Y of tile sl_tx, whose first block is in plane column X, has a new
\ miner's level: its old one EOR A. Record it; if what the block shows (the
\ brighter of the tile's daylight and the miner's level) changes, test each
\ of its cells. Preserves X.
.sl_block_change
{
    STA sl_diff
    STX sl_save_x
    STY sl_c
    TXA
    ORA sl_c
    TAY
    LDA (sl_plane_ptr),Y        \ old
    STA sl_old
    EOR sl_diff
    STA (sl_plane_ptr),Y        \ new
    STA sl_new
    LDA sl_tx                   \ The tile's daylight
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (sl_light_ptr),Y
    LSR A
    LSR A
    LSR A
    LSR A
    STA sl_day
    CMP sl_old                  \ What each shows
    BCC old_shown
    STA sl_old
.old_shown
    CMP sl_new
    BCC new_shown
    STA sl_new
.new_shown
    LDA sl_new
    CMP sl_old
    BEQ done
    LDA (sl_shape_ptr),Y        \ The tile's graphics page
    STA sl_shape
    LDA (sl_map_ptr),Y
    CMP #FIRST_PIECE            \ A piece: its slot's (pieces.asm)
    BCC material
    CMP #FIRST_PIECE + PIECE_COUNT
    BCS material
    LDX sl_shape
    JSR piece_shown
    STX sl_shape
.material
    ASL A
    BIT sl_shape
    BVC cave
    ORA #1
.cave
    STA sl_page
    LDX sl_old                  \ old * 16 + new
    LDA sl_times16,X
    ORA sl_new
    STA sl_pair
    ASL sl_c                    \ The block's two cells
    JSR sl_cell
    INC sl_c
    JSR sl_cell
.done
    LDX sl_save_x
    RTS
}

\ Cell sl_c (0-3) of tile sl_tx in cell row sl_v: if its change of look
\ (sl_pair) shows through its graphic, and it is in the view, list it.
.sl_cell
{
    LDY sl_pair                 \ The thresholds the mask moves past
    LDA sl_c
    LSR A
    BCS odd
    LDA smooth_between_even,Y
    BEQ out
    STA sl_bits
    LDA #LO(smooth_graphics_even)
    LDX #HI(smooth_graphics_even)
    BNE graphic
.odd
    LDA smooth_between_odd,Y
    BEQ out
    STA sl_bits
    LDA #LO(smooth_graphics_odd)
    LDX #HI(smooth_graphics_odd)
.graphic
    LDY sl_page                 \ A slot's are in its own tables, slot * 8
    CPY #2 * SLOT_MATERIAL      \ on (pieces.asm)
    BCC material_graphics
    LDA sl_c
    LSR A
    LDA #LO(slot_visibility_even - 64 * SLOT_MATERIAL)
    LDX #HI(slot_visibility_even - 64 * SLOT_MATERIAL)
    BCC material_graphics
    LDA #LO(slot_visibility_odd - 64 * SLOT_MATERIAL)
    LDX #HI(slot_visibility_odd - 64 * SLOT_MATERIAL)
.material_graphics
    STA sl_ptr2                 \ This parity's graphics: + page * 32
    STX sl_ptr2 + 1
    LDA sl_page
    LSR A
    LSR A
    LSR A
    CLC
    ADC sl_ptr2 + 1
    STA sl_ptr2 + 1
    LDA sl_page
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    CLC
    ADC sl_ptr2
    STA sl_ptr2
    BCC page_added
    INC sl_ptr2 + 1
.page_added
    LDA sl_j                    \ The cell's graphic: CELL_OFFSETS row
    ASL A                       \ (j * 4 + c) * MAX_SHAPES
    ASL A
    ORA sl_c
    LSR A
    LSR A
    CLC
    ADC #HI(cell_offsets)
    STA sl_ptr + 1
    LDA sl_c                    \ (c AND 3) * 64
    LSR A
    ROR A
    ROR A
    STA sl_ptr
    LDA sl_shape
    AND #SHAPE_BITS
    TAY
    LDA (sl_ptr),Y
    STA sl_offset
    LSR A
    LSR A
    LSR A
    TAY
    LDA (sl_ptr2),Y             \ Which thresholds fall on colour
    AND sl_bits
    BEQ out
    JMP sl_list
.out
    RTS
}
ASSERT LO(cell_offsets) = 0 AND MAX_SHAPES = 64

\ List cell sl_c of tile sl_tx in cell row sl_v, shown at level sl_new, if it
\ is in the view (and not in a column drawn after the list).
.sl_list
{
    LDA sl_v                    \ View row: v - camera_y
    SEC
    SBC zp_camera_y
    STA sl_tmp
    LDA sl_v + 1
    SBC zp_camera_y + 1
    BNE out
    LDA sl_tmp
    CMP #VIEW_ROWS
    BCS out
    LDA #0                      \ View column: 4 tx + c - camera_x
    STA sl_tmp + 1
    LDA sl_tx
    ASL A
    ROL sl_tmp + 1
    ASL A
    ROL sl_tmp + 1
    ORA sl_c
    SEC
    SBC zp_camera_x
    TAX
    LDA sl_tmp + 1
    SBC zp_camera_x + 1
    BNE out
    CPX sl_col_lo
    BCC out
    CPX sl_col_hi
    BEQ in_view
    BCS out
.in_view
    LDA sl_list_count
    CMP #LIST_MAX
    BEQ out
    INC sl_list_count
    LDY #0
    LDA sl_new                  \ The masks: level * 16 + parity * 8
    ASL A
    ASL A
    ASL A
    ASL A
    STA sl_ptr
    LDA sl_c
    AND #1
    ASL A
    ASL A
    ASL A
    ORA sl_ptr
    STA (sl_list_ptr),Y
    INY
    LDA sl_offset               \ The graphics
    STA (sl_list_ptr),Y
    INY
    LDA sl_page
    CLC
    ADC #HI(HOST_MATERIAL_PAGES)
    STA (sl_list_ptr),Y
    INY
    TXA                         \ The screen: screen_start + row * ROW_BYTES
    ASL A                       \ + column * CELL_BYTES
    ASL A
    ASL A                       \ Carry: column * 8's high byte
    STA sl_ptr
    LDA sl_tmp                  \ Row * 2 pages, plus it
    ROL A
    STA sl_ptr + 1
    LDA sl_ptr
    CLC
    ADC zp_screen_start
    STA (sl_list_ptr),Y
    INY
    LDA sl_ptr + 1
    ADC zp_screen_start + 1
    CMP #HI(SCREEN_END)
    BCC wrapped
    SBC #HI(SCREEN_END - SCREEN_START)
.wrapped
    STA (sl_list_ptr),Y
    LDA sl_list_ptr
    CLC
    ADC #LIST_ENTRY_BYTES
    STA sl_list_ptr
    BCC out
    INC sl_list_ptr + 1
.out
    RTS
}

.sl_times16
FOR n, 0, 15
    EQUB n * 16
NEXT

\ ---------------------------------------------------------------------------
\ The flood

\ The tile flood around tile (sl_cx, sl_cy), as lighting.miner_light, into
\ sl_pool (window order). First each window tile's clear flag (passable or
\ partly dug), and whether it is outside the tile cache.
.sl_flood_pool
{
    LDX #0                      \ The window, row by row: X its index
    LDA #&100 - MINER_RADIUS
    STA sl_oy
.row
    CLC
    LDA sl_cy
    ADC sl_oy
    STA sl_ty
    JSR sl_cache_row
    LDA sl_cx
    SEC
    SBC #MINER_RADIUS
    STA sl_tx
    LDA #MINER_SPAN
    STA sl_count
.column
    LDY miner_index,X           \ Outside the cache: unlit, and opaque
    LDA #&FF
    STA sl_pool_outside,Y
    LDA #0
    LDY sl_ty
    CPY cached_top
    BCC clear_set
    CPY cached_bottom
    BEQ down_inside
    BCS clear_set
.down_inside
    LDY sl_tx
    CPY cached_left
    BCC clear_set
    CPY cached_right
    BEQ across_inside
    BCS clear_set
.across_inside
    LDY miner_index,X
    LDA #0
    STA sl_pool_outside,Y
    LDY sl_tx
    TYA
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (sl_map_ptr),Y
    STY sl_tmp
    TAY
    LDA material_passable,Y
    BNE clear_set
    LDY sl_tmp
    LDA (sl_shape_ptr),Y
    AND #SHAPE_BITS             \ Non-zero if partly dug
.clear_set
    LDY miner_index,X           \ In the flood's order
    STA sl_pool_clear,Y
    INX
    INC sl_tx
    DEC sl_count
    BNE column
    INC sl_oy
    LDA sl_oy
    CMP #MINER_RADIUS + 1
    BNE row
    LDA #&FF                    \ The miner's own tile lets light out
    STA sl_pool_clear
    LDA #MINER_LEVEL
    STA sl_pool
.*sl_flood_entries              \ (Labels like this are for timing)

    LDX #1                      \ Each entry from its neighbours one step
.entry                          \ nearer the miner (miner_light)
    LDA #0
    STA sl_best
    LDA sl_pool_outside,X
    BNE store
    LDA sl_pool_clear,X
    BNE open
    JMP wall
.open
    LDY miner_across,X          \ Into open ground: from open ground, less
    CPY #LIGHT_NO_TILE          \ LIGHT_OPEN_STEP
    BEQ open_vertical
    LDA sl_pool_clear,Y
    BEQ open_vertical
    LDA sl_pool,Y
    SEC
    SBC #LIGHT_OPEN_STEP
    BCC open_vertical
    STA sl_best
.open_vertical
    LDY miner_vertical,X
    CPY #LIGHT_NO_TILE
    BEQ open_diagonal
    LDA sl_pool_clear,Y
    BEQ open_diagonal
    LDA sl_pool,Y
    SEC
    SBC #LIGHT_OPEN_STEP
    BCC open_diagonal
    CMP sl_best
    BCC open_diagonal
    STA sl_best
.open_diagonal
    LDY miner_diagonal,X        \ Diagonally from open ground, past an open
    CPY #LIGHT_NO_TILE          \ corner (there are both corners)
    BEQ store
    LDA sl_pool_clear,Y
    BEQ store
    LDY miner_across,X
    LDA sl_pool_clear,Y
    LDY miner_vertical,X
    ORA sl_pool_clear,Y
    BEQ store
    LDY miner_diagonal,X
    LDA sl_pool,Y
    SEC
    SBC #LIGHT_OPEN_DIAGONAL_STEP
    BCC store
    CMP sl_best
    BCC store
    STA sl_best
.store
    LDA sl_best
    STA sl_pool,X
    INX
    CPX #MINER_WINDOW
    BNE entry
    RTS
.wall
    LDY miner_across,X          \ Into a wall: its face from open ground,
    JSR wall_from               \ undimmed; soaked in from a wall, less
    LDY miner_vertical,X        \ LIGHT_WALL_STEP
    JSR wall_from
    JMP store
.wall_from
    CPY #LIGHT_NO_TILE
    BEQ wall_done
    LDA sl_pool_clear,Y
    BEQ from_wall
    LDA sl_pool,Y
    JMP consider
.from_wall
    LDA sl_pool,Y
    SEC
    SBC #LIGHT_WALL_STEP
    BCC wall_done
.consider
    CMP sl_best
    BCC wall_done
    STA sl_best
.wall_done
    RTS

}

\ The flood around the miner's tile, then each tile's excess, then each
\ block's soft excess in the grid.
.sl_flood
{
    JSR sl_flood_pool
.*sl_flood_excess
    LDX #MINER_WINDOW - 1       \ Each tile's excess: MINER_LEVEL where the
.tile_excess                    \ pool doesn't reach
    LDA sl_pool,X
    BEQ dark
    LDA smooth_open_pool,X
    SEC
    SBC sl_pool,X
    BCS excess_set
    LDA #0
    BEQ excess_set
.dark
    LDA #MINER_LEVEL
.excess_set
    LDY smooth_tile_index,X
    STA sl_tile_excess,Y
    DEX
    BPL tile_excess

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
    RTS
}

\ ---------------------------------------------------------------------------
\ Resets: the host has drawn these cells as daylight alone

\ Reset the blocks of cell row A (low byte; the view's blocks across).
.sl_reset_row
{
    AND #PLANE_ROWS - 1         \ The plane row
    STA sl_tmp
    LSR A
    LSR A
    CLC
    ADC #HI(sl_plane)
    STA sl_ptr + 1
    LDA sl_tmp
    AND #3
    LSR A
    ROR A
    ROR A
    STA sl_ptr
    LDA zp_camera_x + 1         \ From the view's first block
    LSR A
    LDA zp_camera_x
    ROR A
    TAY
    LDX #VIEW_COLUMNS DIV 2 + 1
    LDA #0
.loop
    PHA
    TYA
    AND #PLANE_COLUMNS - 1
    TAY
    PLA
    STA (sl_ptr),Y
    INY
    DEX
    BNE loop
    LDA #&FF
    STA sl_force
    RTS
}

\ Reset the blocks of the view's cell column A (0-63), down the view.
.sl_reset_column
{
    CLC                         \ The block: (camera_x + A) / 2
    ADC zp_camera_x
    STA sl_tmp
    LDA zp_camera_x + 1
    ADC #0
    LSR A
    LDA sl_tmp
    ROR A
    AND #PLANE_COLUMNS - 1
    STA sl_tmp
    LDA zp_camera_y
    STA sl_tmp + 1
    LDX #VIEW_ROWS
.loop
    LDA sl_tmp + 1              \ The plane row
    AND #PLANE_ROWS - 1
    LSR A
    LSR A
    CLC
    ADC #HI(sl_plane)
    STA sl_ptr + 1
    LDA sl_tmp + 1
    AND #3
    LSR A
    ROR A
    ROR A
    STA sl_ptr
    LDY sl_tmp
    LDA #0
    STA (sl_ptr),Y
    INC sl_tmp + 1
    DEX
    BNE loop
    LDA #&FF
    STA sl_force
    RTS
}

\ Reset the blocks of tile (X, Y).
.sl_reset_tile
{
    TXA                         \ Its first block
    ASL A
    AND #PLANE_COLUMNS - 1
    STA sl_tmp
    TYA                         \ Its first cell row
    ASL A
    STA sl_tmp + 1
    LDX #2
.loop
    LDA sl_tmp + 1
    AND #PLANE_ROWS - 1
    LSR A
    LSR A
    CLC
    ADC #HI(sl_plane)
    STA sl_ptr + 1
    LDA sl_tmp + 1
    AND #3
    LSR A
    ROR A
    ROR A
    STA sl_ptr
    LDY sl_tmp
    LDA #0
    STA (sl_ptr),Y
    INY
    STA (sl_ptr),Y
    INC sl_tmp + 1
    DEX
    BNE loop
    LDA #&FF
    STA sl_force
    RTS
}

\ Reset every block in the view.
.sl_reset_view
{
    LDA zp_camera_y
    STA sl_tmp + 1
    LDA #VIEW_ROWS
    STA sl_count
.loop
    LDA sl_tmp + 1
    JSR sl_reset_row
    INC sl_tmp + 1
    DEC sl_count
    BNE loop
    RTS
}
