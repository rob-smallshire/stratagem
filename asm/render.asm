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
    SKIP ITEM_MAX * ITEM_BYTES
.item_save_low
    FOR item, 0, ITEM_MAX - 1
        EQUB LO(item_saves + item * ITEM_BYTES)
    NEXT
.item_save_high
    FOR item, 0, ITEM_MAX - 1
        EQUB HI(item_saves + item * ITEM_BYTES)
    NEXT

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
\ where each item the packet carried goes on the screen first.
.restore_items
{
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
    LDA host_item_frame,X
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
    RTS
}

\ Draw the items the packet carried, but those left as they are, saving
\ the screen under each.
.render_items
{
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
    RTS
}

\ Draw sprite frame zp_sprite_frame with its top line at zp_sprite_address,
\ saving the screen under it at XA, each byte as (screen AND mask) OR
\ data.
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
.mask0
    AND &FFFF,X
.data0
    ORA &FFFF,X
    STA (zp_screen),Y
    INX
    LDA (zp_screen_lower),Y
.save1
    STA &FFFF,X
.mask1
    AND &FFFF,X
.data1
    ORA &FFFF,X
    STA (zp_screen_lower),Y
    INX
    LDA (zp_tile),Y
.save2
    STA &FFFF,X
.mask2
    AND &FFFF,X
.data2
    ORA &FFFF,X
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
