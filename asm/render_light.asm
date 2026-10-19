\ The light's draw list, drawn as it is read from the Tube (as prototype 3,
\ asm/tube_draw.asm): render code, appended to the render region by the Tube
\ game's host. Each cell's entry is read while the cell before is drawn, a
\ byte every two lines or so, long enough for the parasite's NMI to put the
\ next byte in R3, so only the first entry's reads wait for it.

\ The first set of pointers is the renderer's own; the second borrows
\ renderer workspace that is free while the list is drawn.
list_screen_b = zp_screen_lower
list_tile_b = zp_offsets_pointer
list_mask_b = zp_row_pointer

MACRO LIST_READ_BYTE            \ The next byte from the parasite
.wait
    BIT TUBE_R3_STATUS
    BPL wait
    LDA TUBE_R3
ENDMACRO

\ Draw the cell at screen from tile through the masks at mask (or copy it, at
\ full light), reading the next entry's first four bytes into the other set
\ as it goes: after lines 7, 5, 3 and 1.
MACRO LIST_DRAW screen, tile, mask, next_screen, next_tile, next_mask
    LDA mask
    CMP #LIGHT_FULL * LIGHT_SCALE
    BCS full
    JMP dim
.full
    LDY #7
    FOR line, 7, 0, -1
        LDA (tile),Y
        STA (screen),Y
        IF line = 7
            LDA TUBE_R3
            STA next_mask
        ELIF line = 5
            LDA TUBE_R3
            STA next_tile
        ELIF line = 3
            LDA TUBE_R3
            STA next_tile + 1
        ELIF line = 1
            LDA TUBE_R3
            STA next_screen
        ENDIF
        IF line > 0
            DEY
        ENDIF
    NEXT
    JMP done
.dim
    LDY #7
    FOR line, 7, 0, -1
        LDA (tile),Y
        AND (mask),Y
        STA (screen),Y
        IF line = 7
            LDA TUBE_R3
            STA next_mask
        ELIF line = 5
            LDA TUBE_R3
            STA next_tile
        ELIF line = 3
            LDA TUBE_R3
            STA next_tile + 1
        ELIF line = 1
            LDA TUBE_R3
            STA next_screen
        ENDIF
        IF line > 0
            DEY
        ENDIF
    NEXT
.done
ENDMACRO

\ Draw the list being read from the Tube: a count, then the entries.
.render_light
{
    LIST_READ_BYTE
    BNE some
    RTS
.some
    STA list_count
    LDA #HI(light_masks)
    STA zp_mask + 1
    STA list_mask_b + 1
    LIST_READ_BYTE              \ The first cell's entry
    STA zp_mask
    LIST_READ_BYTE
    STA zp_tile
    LIST_READ_BYTE
    STA zp_tile + 1
    LIST_READ_BYTE
    STA zp_screen
    LIST_READ_BYTE
    STA zp_screen + 1
.cell_a
    LIST_DRAW zp_screen, zp_tile, zp_mask, list_screen_b, list_tile_b, list_mask_b
    DEC list_count
    BNE more_a
    RTS
.more_a
    LIST_READ_BYTE
    STA list_screen_b + 1
    LIST_DRAW list_screen_b, list_tile_b, list_mask_b, zp_screen, zp_tile, zp_mask
    DEC list_count
    BNE more_b
    RTS
.more_b
    LIST_READ_BYTE
    STA zp_screen + 1
    JMP cell_a
}

.list_count     EQUB 0
