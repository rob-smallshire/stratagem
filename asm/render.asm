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

ALIGN TILE_BYTES                \ So a cell's offset in a tile never carries
.tile_graphics
    TILE_GRAPHICS

\ The graphics address of each tile.
.tile_address_low
    FOR tile, 0, KIND_COUNT - 1
        EQUB LO(tile_graphics + tile * TILE_BYTES)
    NEXT
.tile_address_high
    FOR tile, 0, KIND_COUNT - 1
        EQUB HI(tile_graphics + tile * TILE_BYTES)
    NEXT

\ Sprite frames: SPRITE_BYTES mask bytes then SPRITE_BYTES data bytes each.
.sprite_frames
    SPRITE_FRAMES
.sprite_mask_low
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB LO(sprite_frames + frame * 2 * SPRITE_BYTES)
    NEXT
.sprite_mask_high
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB HI(sprite_frames + frame * 2 * SPRITE_BYTES)
    NEXT
.sprite_data_low
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB LO(sprite_frames + frame * 2 * SPRITE_BYTES + SPRITE_BYTES)
    NEXT
.sprite_data_high
    FOR frame, 0, SPRITE_FRAME_COUNT - 1
        EQUB HI(sprite_frames + frame * 2 * SPRITE_BYTES + SPRITE_BYTES)
    NEXT

\ The screen bytes under the sprite, saved when it is drawn.
.sprite_save
    SKIP SPRITE_BYTES

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

\ Point zp_row_pointer at the tile cache row holding world cell row
\ zp_render_v, and set zp_render_half to the offset of its half of a tile.
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
    TYA
    AND #7
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_row_pointer
    LDA zp_render_v
    AND #1
    LSR A                       \ 1 -> 32
    ROR A
    ROR A
    ROR A
    STA zp_render_half
    RTS
}

\ Set zp_tile to the graphics of the cell in column A of the cache row at
\ zp_row_pointer.
MACRO SET_CELL_GRAPHICS
    TAX
    LSR A
    LSR A
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (zp_row_pointer),Y      \ The tile
    TAY
    TXA
    AND #3
    ASL A
    ASL A
    ASL A
    ORA zp_render_half
    ORA tile_address_low,Y
    STA zp_tile
    LDA tile_address_high,Y
    STA zp_tile + 1
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
    JSR set_row_pointer
.tile_loop
    LDA zp_render_u
    SET_CELL_GRAPHICS
.cell_loop
    COPY_CELL zp_screen
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
    BEQ tile_loop               \ Into the next tile
    CLC                         \ The next cell of the same tile: no carry,
    LDA zp_tile                 \ as tiles are aligned
    ADC #CELL_BYTES
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
    \ Each column's tile column in the cache and cell offset in its tiles.
    LDX #0
    LDA zp_render_u
.setup_loop
    TAY
    LSR A
    LSR A
    AND #TILE_CACHE_SIZE - 1
    STA column_tile,X
    TYA
    AND #3
    ASL A
    ASL A
    ASL A
    STA column_offset,X
    INY
    TYA
    INX
    CPX zp_render_width
    BNE setup_loop
    LDA zp_render_base
    STA zp_screen
    LDA zp_render_base + 1
    STA zp_screen + 1
.row_loop
    JSR set_row_pointer
    LDX #0
    LDA zp_screen
    STA zp_screen_lower
    LDA zp_screen + 1
    STA zp_screen_lower + 1
.column_loop
    LDY column_tile,X
    LDA (zp_row_pointer),Y      \ The tile
    TAY
    LDA tile_address_low,Y
    ORA zp_render_half
    ORA column_offset,X
    STA zp_tile
    LDA tile_address_high,Y
    STA zp_tile + 1
    COPY_CELL zp_screen_lower
    INX
    CPX zp_render_width
    BEQ row_done
    CLC                         \ The next column: a cell on, wrapping
    LDA zp_screen_lower
    ADC #CELL_BYTES
    STA zp_screen_lower
    BCC column_loop
    INC zp_screen_lower + 1
    LDA zp_screen_lower + 1
    CMP #HI(SCREEN_END)
    BNE column_loop
    LDA #HI(SCREEN_START)
    STA zp_screen_lower + 1
    BNE column_loop
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
    BNE row_loop
    RTS
}

.column_tile        SKIP 2
.column_offset      SKIP 2

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

\ Draw sprite frame zp_sprite_frame with its top line at zp_sprite_address,
\ saving the screen under it, each byte as (screen AND mask) OR data.
.render_sprite
{
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
    JSR sprite_pointers
    LDA #PLAYER_HEIGHT
    STA zp_render_count
    LDX #0
.line_loop
    LDA (zp_screen),Y
    STA sprite_save,X
.mask0
    AND &FFFF,X
.data0
    ORA &FFFF,X
    STA (zp_screen),Y
    INX
    LDA (zp_screen_lower),Y
    STA sprite_save,X
.mask1
    AND &FFFF,X
.data1
    ORA &FFFF,X
    STA (zp_screen_lower),Y
    INX
    LDA (zp_tile),Y
    STA sprite_save,X
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

\ Remove the sprite drawn at zp_sprite_address, restoring the screen under
\ it.
.render_restore
{
    JSR sprite_pointers
    LDA #PLAYER_HEIGHT
    STA zp_render_count
    LDX #0
.line_loop
    LDA sprite_save,X
    STA (zp_screen),Y
    INX
    LDA sprite_save,X
    STA (zp_screen_lower),Y
    INX
    LDA sprite_save,X
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

SAVE "RENDER", render_start, render_end
