\ RENDER: the render region, &8000-&AFFF. Graphics at the bottom, code from
\ RENDER_CODE. Render code runs with the screen paged in at &3000-&7FFF
\ (on the B+ because it runs in ANDY, on the Integra-B because MEMSEL is
\ set), so everything it reads must be outside &3000-&7FFF. It must not raise
\ errors, which would page the render region out.

CLEAR BANK_START, BANK_END
ORG RENDER_START
GUARD RENDER_CODE

.render_start
    EQUB 0, 0, 0, 0, 0, 0, 0, 0 \ Not a ROM header: &8007 = 0 and &8001 <> "("

\ Each material's graphics, two pages: its four cell variants (full, top
\ half, bottom half, empty) against a cave background, then against the sky.
ALIGN &100
.material_pages
    MATERIAL_PAGES

\ For each cell of a tile (half * 4 + column), the offset in its material's
\ page of that cell in each shape: MAX_SHAPES bytes per cell, so a half's
\ four cells fill a page.
.cell_offsets
    CELL_OFFSETS

\ The dither masks for each light level: see lighting.light_masks.
ALIGN &100
.light_masks
    LIGHT_MASKS

.quarter_offsets                \ Each column's MAX_SHAPES-byte row of a page
    EQUB 0, MAX_SHAPES, 2 * MAX_SHAPES, 3 * MAX_SHAPES

\ Sprite frames, three bytes wide: the player's (SPRITE_BYTES mask bytes
\ then SPRITE_BYTES data bytes each), then the items' (ITEM_FRAME_FIRST
\ on, ITEM_BYTES of each).
.sprite_frames
    SPRITE_FRAMES
.item_frames
    ITEM_FRAMES
ASSERT ITEM_FRAME_FIRST = SPRITE_FRAME_COUNT
.sprite_mask_low
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB LO(sprite_frames + frame * 2 * SPRITE_BYTES)
    NEXT
    FOR frame, 0, ITEM_FRAME_COUNT - 1
        EQUB LO(item_frames + frame * 2 * ITEM_BYTES)
    NEXT
.sprite_mask_high
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB HI(sprite_frames + frame * 2 * SPRITE_BYTES)
    NEXT
    FOR frame, 0, ITEM_FRAME_COUNT - 1
        EQUB HI(item_frames + frame * 2 * ITEM_BYTES)
    NEXT
.sprite_data_low
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB LO(sprite_frames + frame * 2 * SPRITE_BYTES + SPRITE_BYTES)
    NEXT
    FOR frame, 0, ITEM_FRAME_COUNT - 1
        EQUB LO(item_frames + frame * 2 * ITEM_BYTES + ITEM_BYTES)
    NEXT
.sprite_data_high
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB HI(sprite_frames + frame * 2 * SPRITE_BYTES + SPRITE_BYTES)
    NEXT
    FOR frame, 0, ITEM_FRAME_COUNT - 1
        EQUB HI(item_frames + frame * 2 * ITEM_BYTES + ITEM_BYTES)
    NEXT
\ For each screen byte below &C0, the bits a sprite may be drawn over.
.sprite_drawable
    SPRITE_DRAWABLE

.sprite_lines                   \ Each frame's height
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB PLAYER_HEIGHT
    NEXT
    FOR frame, 0, ITEM_FRAME_COUNT - 1
        EQUB ITEM_HEIGHT
    NEXT

\ The screen bytes under the player's sprite, and under each item's, saved
\ when they are drawn.
.sprite_save
    SKIP SPRITE_BYTES
.item_saves
    SKIP ITEMS_DRAWN * ITEM_BYTES
.item_save_low
    FOR item, 0, ITEMS_DRAWN - 1
        EQUB LO(item_saves + item * ITEM_BYTES)
    NEXT
.item_save_high
    FOR item, 0, ITEMS_DRAWN - 1
        EQUB HI(item_saves + item * ITEM_BYTES)
    NEXT

\ The pack's panel (render_pack): the icons of kinds that aren't materials
\ (a tile's 64 bytes each; a material's is its whole tile in
\ material_pages), each kind's icon's address, the digits (two cells each)
\ and the arrowheads (pointing right, then left, then two blank cells).
.pack_icons
    PACK_ICONS
.pack_icon_low
    PACK_ICON_LOW
.pack_icon_high
    PACK_ICON_HIGH
.pack_digits
    PACK_DIGITS
.pack_marks
    PACK_MARKS
.pack_socket                    \ An empty cell of the grid
    PACK_SOCKET
.grid_lefts                     \ The grid's first column, by its size
    GRID_LEFTS

CLEAR RENDER_CODE, RENDER_END
ORG RENDER_CODE
GUARD RENDER_END

\ Copy the eight bytes of the cell at zp_tile to the screen at pointer.
MACRO COPY_CELL pointer
    LDY #7
    FOR line, 7, 1, -1
        LDA (zp_tile),Y
        STA (pointer),Y
        DEY
    NEXT
    LDA (zp_tile),Y
    STA (pointer),Y
ENDMACRO

\ Copy the cell at zp_tile to the screen at pointer through the dither masks
\ at zp_mask, unless they are the full light's, which keep everything.
MACRO DRAW_CELL pointer
    LDA zp_mask
    CMP #LIGHT_FULL * LIGHT_SCALE
    BCC dim
    COPY_CELL pointer
    JMP done
.dim
    LDY #7
    FOR line, 7, 1, -1
        LDA (zp_tile),Y
        AND (zp_mask),Y
        STA (pointer),Y
        DEY
    NEXT
    LDA (zp_tile),Y
    AND (zp_mask),Y
    STA (pointer),Y
.done
ENDMACRO

\ Point zp_mask at the masks for the light zp_render_light in world cell
\ column zp_render_u: the odd columns' follow the even columns'.
MACRO SET_MASK
    LDA zp_render_u
    LSR A
    LDA zp_render_light
    BCC even
    ORA #8
.even
    STA zp_mask
ENDMACRO

\ Point zp_row_pointer, zp_shape_row_pointer and zp_light_row_pointer at the
\ tile cache rows holding world cell row zp_render_v, and zp_offsets_pointer at the
\ CELL_OFFSETS page for its half of a tile.
.set_row_pointer
{
    LDA zp_render_v
    LSR A
    AND #TILE_CACHE_SIZE - 1    \ Tile row in the cache
    TAY
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA zp_row_pointer + 1
    ADC #HI(tile_cache_shapes - tile_cache)
    STA zp_shape_row_pointer + 1
    ADC #HI(tile_cache_light - tile_cache_shapes)
    STA zp_light_row_pointer + 1
    TYA
    AND #7
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_row_pointer
    STA zp_shape_row_pointer
    STA zp_light_row_pointer
    LDA zp_render_v
    AND #1
    CLC
    ADC #HI(cell_offsets)
    STA zp_offsets_pointer + 1
    RTS
}

\ Set zp_tile to the graphics of the cell in world cell column A of the cache
\ rows at zp_row_pointer and zp_shape_row_pointer: the material's page for
\ the background, at the offset CELL_OFFSETS gives for the shape. Leaves the
\ shape number in zp_render_shape, zp_offsets_pointer at the cell's row, and
\ the tile's light in zp_render_light.
MACRO SET_CELL_GRAPHICS
    TAX
    LSR A
    LSR A
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (zp_light_row_pointer),Y
    STA zp_render_light
    LDA (zp_shape_row_pointer),Y
    STA zp_render_shape
    LDA (zp_row_pointer),Y      \ The material: two pages each
    ASL A
    BIT zp_render_shape         \ Plus one for the sky background
    BVC cave
    ORA #1
.cave
    CLC
    ADC #HI(material_pages)
    STA zp_tile + 1
    TXA
    AND #3
    TAY
    LDA quarter_offsets,Y
    STA zp_offsets_pointer
    LDA zp_render_shape
    AND #SHAPE_BITS
    STA zp_render_shape
    TAY
    LDA (zp_offsets_pointer),Y
    STA zp_tile
ENDMACRO

\ Draw zp_render_count cells along world cell row zp_render_v, from column
\ zp_render_u, at zp_render_base onwards, wrapping at the end of the screen.
\ The tiles come from the tile cache.
.render_row
{
    LDA zp_render_base
    STA zp_screen
    LDA zp_render_base + 1
    STA zp_screen + 1
    LDA #HI(light_masks)
    STA zp_mask + 1
    JSR set_row_pointer
.tile_loop
    LDA zp_render_u
    SET_CELL_GRAPHICS
.cell_loop
    SET_MASK
    DRAW_CELL zp_screen
    CLC
    LDA zp_screen
    ADC #CELL_BYTES
    STA zp_screen
    BCC same_page
    INC zp_screen + 1
    LDA zp_screen + 1
    CMP #HI(SCREEN_END)
    BNE same_page
    LDA #HI(SCREEN_START)
    STA zp_screen + 1
.same_page
    DEC zp_render_count
    BEQ done
    INC zp_render_u
    LDA zp_render_u
    AND #3
    BNE same_tile
    JMP tile_loop               \ Into the next tile
.same_tile
    LDA zp_offsets_pointer      \ The next cell of the same tile: the next
    CLC                         \ CELL_OFFSETS row, in the same page
    ADC #MAX_SHAPES
    STA zp_offsets_pointer
    LDY zp_render_shape
    LDA (zp_offsets_pointer),Y
    STA zp_tile
    JMP cell_loop
.done
    RTS
}

\ Draw zp_render_width (1 or 2) columns of zp_render_count cells, from world
\ cell (zp_render_u, zp_render_v), at zp_render_base onwards. They are drawn
\ a row at a time, so that the top of every column is drawn first, ahead of
\ the beam.
.render_columns
{
    \ Each column's tile column in the cache, and its CELL_OFFSETS row.
    LDX #0
    LDA zp_render_u
.setup_loop
    PHA
    LSR A
    LSR A
    AND #TILE_CACHE_SIZE - 1
    STA column_tile,X
    PLA
    PHA
    AND #3
    TAY
    LDA quarter_offsets,Y
    STA column_offset,X
    AND #MAX_SHAPES             \ Odd columns' masks follow the even's
    ASSERT MAX_SHAPES = 64
    LSR A
    LSR A
    LSR A
    STA column_parity,X
    PLA
    CLC
    ADC #1
    INX
    CPX zp_render_width
    BNE setup_loop
    LDA zp_render_base
    STA zp_screen
    LDA zp_render_base + 1
    STA zp_screen + 1
    LDA #HI(light_masks)
    STA zp_mask + 1
.row_loop
    JSR set_row_pointer
    LDX #0
    LDA zp_screen
    STA zp_screen_lower
    LDA zp_screen + 1
    STA zp_screen_lower + 1
.column_loop
    LDY column_tile,X
    LDA (zp_light_row_pointer),Y
    ORA column_parity,X
    STA zp_mask
    LDA (zp_shape_row_pointer),Y
    STA zp_render_shape
    LDA (zp_row_pointer),Y      \ The material: two pages each
    ASL A
    BIT zp_render_shape         \ Plus one for the sky background
    BVC cave
    ORA #1
.cave
    CLC
    ADC #HI(material_pages)
    STA zp_tile + 1
    LDA column_offset,X
    STA zp_offsets_pointer
    LDA zp_render_shape
    AND #SHAPE_BITS
    TAY
    LDA (zp_offsets_pointer),Y
    STA zp_tile
    DRAW_CELL zp_screen_lower
    INX
    CPX zp_render_width
    BEQ row_done
    CLC                         \ The next column: a cell on, wrapping
    LDA zp_screen_lower
    ADC #CELL_BYTES
    STA zp_screen_lower
    BCC next_column
    INC zp_screen_lower + 1
    LDA zp_screen_lower + 1
    CMP #HI(SCREEN_END)
    BNE next_column
    LDA #HI(SCREEN_START)
    STA zp_screen_lower + 1
.next_column
    JMP column_loop
.row_done
    CLC                         \ The next row
    LDA zp_screen + 1
    ADC #HI(ROW_BYTES)
    CMP #HI(SCREEN_END)
    BCC no_wrap
    SBC #HI(SCREEN_END - SCREEN_START)
.no_wrap
    STA zp_screen + 1
    INC zp_render_v
    DEC zp_render_count
    BEQ done
    JMP row_loop
.done
    RTS
}

.column_tile        SKIP 2
.column_offset      SKIP 2
.column_parity      SKIP 2      \ 8 for odd world cell columns

\ The sprite is SPRITE_COLUMNS bytes wide. Point zp_screen, zp_screen_lower
\ and zp_tile at the cells of its three columns on the character row of its
\ top line, zp_sprite_address, and set Y to the line within the row.
.sprite_pointers
{
    LDA zp_sprite_address
    AND #&F8
    STA zp_screen
    LDA zp_sprite_address + 1
    STA zp_screen + 1
    CLC
    LDA zp_screen
    ADC #CELL_BYTES
    STA zp_screen_lower
    LDA zp_screen + 1
    ADC #0
    JSR wrap_screen_high
    STA zp_screen_lower + 1
    CLC
    LDA zp_screen_lower
    ADC #CELL_BYTES
    STA zp_tile
    LDA zp_screen_lower + 1
    ADC #0
    JSR wrap_screen_high
    STA zp_tile + 1
    LDA zp_sprite_address
    AND #7
    TAY
    RTS
}

\ Move the sprite's column pointers down a character row.
.sprite_next_row
{
    CLC
    LDA zp_screen + 1
    ADC #HI(ROW_BYTES)
    JSR wrap_screen_high
    STA zp_screen + 1
    CLC
    LDA zp_screen_lower + 1
    ADC #HI(ROW_BYTES)
    JSR wrap_screen_high
    STA zp_screen_lower + 1
    CLC
    LDA zp_tile + 1
    ADC #HI(ROW_BYTES)
    JSR wrap_screen_high
    STA zp_tile + 1
    LDY #0
    RTS
}

\ Draw the player's sprite, frame zp_sprite_frame, with its top line at
\ zp_sprite_address, saving the screen under it.
.render_sprite
{
    LDA #LO(sprite_save)
    LDX #HI(sprite_save)
    JMP sprite_draw
}

\ Remove the player's sprite drawn at zp_sprite_address, restoring the
\ screen under it.
.render_restore
{
    LDA #LO(sprite_save)
    LDX #HI(sprite_save)
    LDY #PLAYER_HEIGHT
    JMP sprite_undo
}

\ Remove the items drawn, last first, restoring the screen under them;
\ but leave as they are those at the start of the list drawn where and as
\ they are to be drawn again, if nothing is redrawn under them this frame
\ (host_items_untouched), so that items lying still cost nothing. Work out
\ where each item the packet carried goes on the screen first. Preserves
\ zp_sprite_address, the player's sprite's.
.restore_items
{
    JSR keep_sprite_address
    LDX #0                      \ Where each goes
.address
    CPX host_items
    BEQ addressed
    LDA #0                      \ Address = screen_start + (line >> 3) *
    STA zp_ptr + 1              \ ROW_BYTES + column * 8 + (line AND 7)
    LDA host_item_column,X
    ASL A
    ASL A
    ASL A
    ROL zp_ptr + 1
    STA zp_ptr
    LDA host_item_line,X
    LSR A
    LSR A
    AND #&FE                    \ (line >> 3) * 2 pages
    CLC
    ADC zp_ptr + 1
    STA zp_ptr + 1
    LDA host_item_line,X
    AND #7
    ORA zp_ptr                  \ Column * 8 has its low three bits clear
    CLC
    ADC zp_screen_start
    STA host_item_new_low,X
    LDA zp_ptr + 1
    ADC zp_screen_start + 1
    JSR wrap_screen_high
    STA host_item_new_high,X
    INX
    BNE address
.addressed
    LDX #0                      \ Those left as they are
    LDA host_items_untouched
    BEQ kept
.keep
    CPX host_items
    BEQ kept
    CPX host_items_drawn
    BEQ kept
    LDA host_item_new_low,X
    CMP host_item_address_low,X
    BNE kept
    LDA host_item_new_high,X
    CMP host_item_address_high,X
    BNE kept
    LDA host_item_frame,X       \ (Never one by the miner, drawn each frame)
    CMP host_item_drawn_frame,X
    BNE kept
    INX
    BNE keep
.kept
    STX host_items_kept
    LDX host_items_drawn        \ The rest, last first
.loop
    CPX host_items_kept
    BEQ done
    DEX
    STX host_item_index
    LDA host_item_address_low,X
    STA zp_sprite_address
    LDA host_item_address_high,X
    STA zp_sprite_address + 1
    LDY item_save_low,X         \ Its save buffer, in XA
    LDA item_save_high,X
    TAX
    TYA
    LDY #ITEM_HEIGHT
    JSR sprite_undo
    LDX host_item_index
    JMP loop
.done
    STX host_items_drawn
    JMP put_sprite_address
}

\ Draw the items the packet carried, but those left as they are, saving
\ the screen under each. Preserves zp_sprite_address.
.render_items
{
    JSR keep_sprite_address
    LDX host_items_kept
.loop
    CPX host_items
    BEQ done
    STX host_item_index
    LDA host_item_new_low,X
    STA zp_sprite_address
    STA host_item_address_low,X
    LDA host_item_new_high,X
    STA zp_sprite_address + 1
    STA host_item_address_high,X
    LDA host_item_frame,X
    AND #&FF - ITEM_BY_MINER
    STA zp_sprite_frame
    STA host_item_drawn_frame,X
    LDY item_save_low,X         \ Its save buffer, in XA
    LDA item_save_high,X
    TAX
    TYA
    JSR sprite_draw
    LDX host_item_index
    INX
    BNE loop
.done
    STX host_items_drawn
    JMP put_sprite_address
}

\ Keep zp_sprite_address while items are drawn or restored, and put it back.
.keep_sprite_address
{
    LDA zp_sprite_address
    STA host_sprite_address
    LDA zp_sprite_address + 1
    STA host_sprite_address + 1
    RTS
}
.put_sprite_address
{
    LDA host_sprite_address
    STA zp_sprite_address
    LDA host_sprite_address + 1
    STA zp_sprite_address + 1
    RTS
}

\ A sprite's byte A drawn over a screen byte at (pointer),Y with a pixel in
\ the sprite colour group: keep the screen's pixels there, those of a piece
\ in front or of a sprite drawn before (sprites.drawn_byte). Preserves X
\ and Y.
MACRO SPRITE_BEHIND pointer, put
    STA sprite_byte
    STX sprite_index
    LDA (pointer),Y
    TAX
    EOR sprite_byte
    AND sprite_drawable,X
    EOR (pointer),Y
    LDX sprite_index
    JMP put
ENDMACRO

\ Draw sprite frame zp_sprite_frame with its top line at zp_sprite_address,
\ saving the screen under it at XA, each byte as (screen AND mask) OR
\ data, but behind pixels in the sprite colour group (SPRITE_BEHIND).
.sprite_draw
{
    STA save0 + 1               \ Point the saves at the buffer
    STA save1 + 1
    STA save2 + 1
    STX save0 + 2
    STX save1 + 2
    STX save2 + 2
    LDX zp_sprite_frame         \ Point the AND and ORA operands at the frame
    LDA sprite_mask_low,X
    STA mask0 + 1
    STA mask1 + 1
    STA mask2 + 1
    LDA sprite_mask_high,X
    STA mask0 + 2
    STA mask1 + 2
    STA mask2 + 2
    LDA sprite_data_low,X
    STA data0 + 1
    STA data1 + 1
    STA data2 + 1
    LDA sprite_data_high,X
    STA data0 + 2
    STA data1 + 2
    STA data2 + 2
    LDA sprite_lines,X
    STA zp_render_count
    JSR sprite_pointers
    LDX #0
.line_loop
    LDA (zp_screen),Y
.save0
    STA &FFFF,X
    CMP #&C0                    \ Carry clear: over the sprite colour group
.mask0
    AND &FFFF,X
.data0
    ORA &FFFF,X
    BCC behind0
.put0
    STA (zp_screen),Y
    INX
    LDA (zp_screen_lower),Y
.save1
    STA &FFFF,X
    CMP #&C0
.mask1
    AND &FFFF,X
.data1
    ORA &FFFF,X
    BCC behind1
.put1
    STA (zp_screen_lower),Y
    INX
    LDA (zp_tile),Y
.save2
    STA &FFFF,X
    CMP #&C0
.mask2
    AND &FFFF,X
.data2
    ORA &FFFF,X
    BCC behind2
.put2
    STA (zp_tile),Y
    INX
    INY
    CPY #8
    BNE next_line
    JSR sprite_next_row
.next_line
    DEC zp_render_count
    BNE line_loop
    RTS
.behind0
    SPRITE_BEHIND zp_screen, put0
.behind1
    SPRITE_BEHIND zp_screen_lower, put1
.behind2
    SPRITE_BEHIND zp_tile, put2
}

.sprite_byte        SKIP 1      \ sprite_draw: the byte drawn, before priority
.sprite_index       SKIP 1      \ ... and X

\ Remove the sprite Y lines high drawn at zp_sprite_address, restoring the
\ screen under it from XA.
.sprite_undo
{
    STA load0 + 1
    STA load1 + 1
    STA load2 + 1
    STX load0 + 2
    STX load1 + 2
    STX load2 + 2
    STY zp_render_count
    JSR sprite_pointers
    LDX #0
.line_loop
.load0
    LDA &FFFF,X
    STA (zp_screen),Y
    INX
.load1
    LDA &FFFF,X
    STA (zp_screen_lower),Y
    INX
.load2
    LDA &FFFF,X
    STA (zp_tile),Y
    INX
    INY
    CPY #8
    BNE next_line
    JSR sprite_next_row
.next_line
    DEC zp_render_count
    BNE line_loop
    RTS
}

\ Wrap the high byte of a screen address in A back into the screen, after
\ adding to it.
.wrap_screen_high
{
    CMP #HI(SCREEN_END)
    BCC done
    SBC #HI(SCREEN_END - SCREEN_START)
.done
    RTS
}

\ Draw the pack's panel (tools/stratagem/pack.py) from host_pack_count,
\ host_pack_kinds, host_pack_counts and host_pack_index: across the top of
\ the view, a blank row, then for each row of kinds their icons, two rows,
\ and their counts below, with arrowheads either side of the hand's count,
\ and a blank row; then the grid (pack_grid).
ASSERT PACK_COLUMNS = 8 AND SLOT_CELLS = 8 AND ROWS_PER_SLOT_ROW = 4
.render_pack
{
    JSR pack_grid_top_row       \ The panel's rows, cleared
    LDA pack_grid_top
    CLC
    ADC pack_grid_rows
    STA pack_row_end
    LDA #PANEL_TOP
    STA pack_row
.clear_row
    LDA #PANEL_LEFT             \ Along the row, cell by cell
    LDY pack_row
    JSR pack_cell_address
    LDX #PANEL_COLUMNS
.clear_cell
    LDA #0
    FOR line, 0, 7
        LDY #line
        STA (zp_screen),Y
    NEXT
    CLC
    LDA zp_screen
    ADC #CELL_BYTES
    STA zp_screen
    BCC same_page
    INC zp_screen + 1
    LDA zp_screen + 1
    CMP #HI(SCREEN_END)
    BCC same_page
    LDA #HI(SCREEN_START)
    STA zp_screen + 1
.same_page
    DEX
    BNE clear_cell
    INC pack_row
    LDA pack_row
    CMP pack_row_end
    BNE clear_row
    LDA #0
    STA pack_slot
.slot
    LDA pack_slot
    CMP host_pack_count
    BEQ grid
    JSR pack_place
    LDX pack_slot               \ The icon, its cells four across, two
    LDY host_pack_kinds,X       \ down
    JSR pack_kind_icon
    LDX pack_slot
    LDA host_pack_counts,X
    STA pack_drawn_counts,X
    JSR pack_count
    JSR pack_slot_marks
    INC pack_slot
    BNE slot                    \ Always branches
.grid
    LDA #&FE                    \ None of the grid as drawn: draw it all
    STA pack_drawn_made
    LDX #GRID_CELLS - 1
.undrawn
    STA pack_drawn_grid,X
    DEX
    BPL undrawn
    JMP pack_grid
}
ASSERT KIND_COUNT < &FE
ASSERT ROWS_PER_GRID_ROW = 3

\ Redraw the counts of the pack's panel that have changed since drawn, and
\ its grid, the counts or the grid having changed.
.render_pack_changed
{
    LDA #0
    STA pack_slot
.loop
    LDA pack_slot
    CMP host_pack_count
    BEQ done
    TAX
    LDA host_pack_counts,X
    CMP pack_drawn_counts,X
    BEQ next
    STA pack_drawn_counts,X
    JSR pack_place
    LDX pack_slot
    LDA host_pack_counts,X
    JSR pack_count
.next
    INC pack_slot
    BNE loop                    \ Always branches
.done
    \ Fall through
}

\ Draw the grid, below the kinds, host_pack_size cells square, each its
\ kind's icon or a socket, GRID_PITCH cells apart and ROWS_PER_GRID_ROW
\ rows; and after it what it makes, as a slot with an arrowhead pointing
\ at its count, or blank cells. Only what differs from pack_drawn_grid and
\ pack_drawn_made is drawn.
.pack_grid
{
    JSR pack_grid_top_row
    LDX host_pack_size
    LDA grid_lefts,X
    STA pack_grid_left
    LDA pack_grid_top
    STA pack_top
    LDA #0
    STA pack_grid_cell
.row
    LDA pack_grid_left
    STA pack_icon_left
    LDA host_pack_size
    STA pack_grid_column
.cell
    LDX pack_grid_cell          \ Unless as drawn already
    LDA host_pack_grid,X
    CMP pack_drawn_grid,X
    BEQ next
    STA pack_drawn_grid,X
    TAY
    CPY #CELL_EMPTY
    BNE kind
    LDA #LO(pack_socket)
    STA zp_tile
    LDA #HI(pack_socket)
    STA zp_tile + 1
    JSR pack_icon
    JMP next
.kind
    JSR pack_kind_icon
.next
    LDA pack_icon_left
    CLC
    ADC #GRID_PITCH
    STA pack_icon_left
    INC pack_grid_cell
    DEC pack_grid_column
    BNE cell
    LDA pack_grid_cell          \ The next row's first cell
    SEC
    SBC host_pack_size
    CLC
    ADC #GRID_MAX
    STA pack_grid_cell
    LDA pack_top
    CLC
    ADC #ROWS_PER_GRID_ROW
    STA pack_top
    SEC
    SBC pack_grid_top
    CMP pack_grid_rows
    BNE row
    LDA pack_icon_left          \ What it makes: past the last column
    STA pack_left
    STA pack_icon_left
    INC pack_icon_left
    LDA pack_grid_top
    STA pack_top
    CLC
    ADC #2
    STA pack_count_row
    LDA host_pack_made          \ Unless as drawn already
    CMP pack_drawn_made
    BNE made
    LDA host_pack_made_count
    CMP pack_drawn_made_count
    BNE made
    RTS
.made
    LDA host_pack_made
    STA pack_drawn_made
    LDA host_pack_made_count
    STA pack_drawn_made_count
    LDY host_pack_made
    CPY #CELL_EMPTY
    BEQ nothing
    JSR pack_kind_icon
    LDA host_pack_made_count
    JSR pack_count
    LDA #LO(pack_marks)         \ An arrowhead pointing at the count, and a
    STA zp_tile                 \ blank cell after it
    LDA #HI(pack_marks)
    STA zp_tile + 1
    LDA pack_left
    JSR pack_put_count
    JSR pack_blank_tile
    LDA pack_left
    CLC
    ADC #5
    JMP pack_put_count
.nothing
    LDA #&FF                    \ Blank cells, the icon's and the count row's
    STA pack_blanking
    JSR pack_icon
    LDA #0
    STA pack_blanking
    LDA #SLOT_CELLS - 2
    STA pack_grid_column
.blank
    JSR pack_blank_tile
    LDA pack_left
    CLC
    ADC pack_grid_column
    SEC
    SBC #1
    JSR pack_put_count
    DEC pack_grid_column
    BNE blank
    RTS
}
ASSERT GRID_PITCH = 5

\ Set pack_grid_top to the grid's first row, below the kinds, and
\ pack_grid_rows to its rows.
.pack_grid_top_row
{
    LDA host_pack_count
    CLC
    ADC #PACK_COLUMNS - 1
    LSR A
    LSR A
    LSR A
    ASL A
    ASL A
    SEC
    ADC #PANEL_TOP
    STA pack_grid_top
    LDA host_pack_size          \ ROWS_PER_GRID_ROW = 3
    ASL A
    ADC host_pack_size          \ (Carry clear)
    STA pack_grid_rows
    RTS
}

\ Draw kind Y's icon, from column pack_icon_left (pack_left + 1 if from
\ pack_place) and row pack_top.
.pack_kind_icon
{
    LDA pack_icon_low,Y
    STA zp_tile
    LDA pack_icon_high,Y
    STA zp_tile + 1
    \ Fall through
}

\ Draw the icon at zp_tile, its cells four across, two down, from column
\ pack_icon_left and row pack_top; or blank cells, if pack_blanking.
.pack_icon
{
    LDA #0
    STA pack_cell
.loop
    LDA pack_blanking
    BEQ put
    JSR pack_blank_tile
.put
    LDA pack_cell
    LSR A
    LSR A
    CLC
    ADC pack_top
    TAY
    LDA pack_cell
    AND #3
    CLC
    ADC pack_icon_left
    JSR pack_put
    INC pack_cell
    LDA pack_cell
    CMP #8
    BNE loop
    RTS
}

\ Draw count A in the slot at pack_left: its tens, or blank cells if
\ none, and its units.
.pack_count
{
    LDX #0
.tens
    CMP #10
    BCC units
    SBC #10
    INX
    BNE tens                    \ Always branches
.units
    STA pack_units
    TXA
    BEQ no_tens
    JSR pack_digit
    JMP tens_cells
.no_tens
    JSR pack_blank_tile         \ (Two blank cells there)
.tens_cells
    LDA pack_left
    CLC
    ADC #1
    JSR pack_put_count
    LDA pack_left
    CLC
    ADC #2
    JSR pack_put_count
    LDA pack_units
    JSR pack_digit
    LDA pack_left
    CLC
    ADC #3
    JSR pack_put_count
    LDA pack_left
    CLC
    ADC #4
    JMP pack_put_count
}

\ Point zp_tile at the blank cells, two of them.
.pack_blank_tile
{
    LDA #LO(pack_marks + 2 * CELL_BYTES)
    STA zp_tile
    LDA #HI(pack_marks + 2 * CELL_BYTES)
    STA zp_tile + 1
    RTS
}

\ Redraw the arrowheads of the pack's panel, the hand having moved.
.render_pack_marks
{
    LDA #0
    STA pack_slot
.loop
    LDA pack_slot
    CMP host_pack_count
    BEQ done
    JSR pack_place
    JSR pack_slot_marks
    INC pack_slot
    BNE loop                    \ Always branches
.done
    RTS
}

\ Set pack_left, pack_icon_left, pack_top and pack_count_row for slot
\ pack_slot: its arrowhead's column, its icon's, its icon's top row and its
\ count's row.
.pack_place
{
    LDA pack_slot
    AND #PACK_COLUMNS - 1
    ASL A
    ASL A
    ASL A
    CLC
    ADC #PANEL_LEFT + 1
    STA pack_left
    STA pack_icon_left
    INC pack_icon_left
    LDA pack_slot
    LSR A
    LSR A
    LSR A
    ASL A
    ASL A
    SEC
    ADC #PANEL_TOP
    STA pack_top
    CLC
    ADC #2
    STA pack_count_row
    RTS
}

\ Draw slot pack_slot's arrowheads, if it is the hand's, or blank cells.
.pack_slot_marks
{
    LDX #LO(pack_marks)
    LDY #HI(pack_marks)
    LDA pack_slot
    CMP host_pack_index
    BEQ hand
    LDX #LO(pack_marks + 2 * CELL_BYTES)
    LDY #HI(pack_marks + 2 * CELL_BYTES)
.hand
    STX zp_tile
    STY zp_tile + 1
    LDA pack_left
    JSR pack_put_count
    LDA pack_left
    CLC
    ADC #5
    JMP pack_put_count
}

\ Point zp_tile at digit A's graphics.
.pack_digit
{
    ASL A
    ASL A
    ASL A
    ASL A
    CLC
    ADC #LO(pack_digits)
    STA zp_tile
    LDA #HI(pack_digits)
    ADC #0
    STA zp_tile + 1
    RTS
}

\ Copy the cell at zp_tile to view cell A in the count's row, and move
\ zp_tile on to the next cell.
.pack_put_count
    LDY pack_count_row
    \ Fall through

\ Copy the cell at zp_tile to view cell (A, Y), and move zp_tile on to the
\ next cell.
.pack_put
{
    JSR pack_cell_address
    LDY #7
.loop
    LDA (zp_tile),Y
    STA (zp_screen),Y
    DEY
    BPL loop
    LDA zp_tile
    CLC
    ADC #8
    STA zp_tile
    BCC done
    INC zp_tile + 1
.done
    RTS
}

\ Point zp_screen at view cell (A, Y): zp_screen_start + Y * ROW_BYTES + A *
\ CELL_BYTES, wrapped.
.pack_cell_address
{
    STA zp_screen
    LDA #0
    ASL zp_screen
    ROL A
    ASL zp_screen
    ROL A
    ASL zp_screen
    ROL A
    STA zp_screen + 1
    TYA
    ASL A                       \ ROW_BYTES = 2 pages
    ADC zp_screen + 1           \ (Carry clear: Y < 128)
    STA zp_screen + 1
    CLC
    LDA zp_screen
    ADC zp_screen_start
    STA zp_screen
    LDA zp_screen + 1
    ADC zp_screen_start + 1
    CMP #HI(SCREEN_END)
    BCC wrapped
    SBC #HI(SCREEN_END - SCREEN_START)
.wrapped
    STA zp_screen + 1
    RTS
}

.pack_row           SKIP 1      \ render_pack's workspace
.pack_row_end       SKIP 1
.pack_slot          SKIP 1
.pack_left          SKIP 1
.pack_top           SKIP 1
.pack_count_row     SKIP 1
.pack_cell          SKIP 1
.pack_units         SKIP 1
.pack_icon_left     SKIP 1
.pack_blanking      SKIP 1      \ Non-zero: pack_icon draws blank cells
.pack_grid_top      SKIP 1
.pack_grid_rows     SKIP 1
.pack_grid_left     SKIP 1
.pack_grid_cell     SKIP 1
.pack_grid_column   SKIP 1
.pack_drawn_counts  SKIP KIND_COUNT \ The counts as drawn, by slot...
.pack_drawn_grid    SKIP GRID_CELLS \ ... the grid...
.pack_drawn_made    SKIP 1      \ ... and what it makes, and how many
.pack_drawn_made_count SKIP 1

\ Clear the whole screen to colour 0.
.render_clear
{
    LDA #HI(SCREEN_START)
    STA zp_screen + 1
    LDA #0
    STA zp_screen
    TAY
.loop
    STA (zp_screen),Y
    INY
    BNE loop
    INC zp_screen + 1
    LDX zp_screen + 1
    CPX #HI(SCREEN_END)
    BNE loop
    RTS
}

.render_end
