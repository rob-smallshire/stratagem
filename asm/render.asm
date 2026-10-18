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

.tile_graphics
    TILE_GRAPHICS

CLEAR RENDER_CODE, RENDER_END
ORG RENDER_CODE
GUARD RENDER_END

MARKER_COLOUR = &3F             \ Both pixels colour 7

\ Copy cells cell_first to cell_end - 1 of the cell list to the screen: each
\ is eight bytes from its cell_source, drawn at cell_base, cell_base +
\ cell_step, and so on, wrapping at the end of the screen. A cell never
\ crosses the end of the screen, as cells are 8-byte aligned.
.render_cells
{
    LDA cell_base
    STA zp_screen
    LDA cell_base + 1
    STA zp_screen + 1
    LDX cell_first
.cell_loop
    LDA cell_source_low,X
    STA zp_tile
    LDA cell_source_high,X
    STA zp_tile + 1
    LDY #7
    FOR line, 7, 1, -1
        LDA (zp_tile),Y
        STA (zp_screen),Y
        DEY
    NEXT
    LDA (zp_tile),Y
    STA (zp_screen),Y
    CLC
    LDA zp_screen
    ADC cell_step
    STA zp_screen
    LDA zp_screen + 1
    ADC cell_step + 1
    CMP #HI(SCREEN_END)
    BCC no_wrap
    SBC #HI(SCREEN_END - SCREEN_START)
.no_wrap
    STA zp_screen + 1
    INX
    CPX cell_end
    BNE cell_loop
    RTS
}

\ Exclusive-OR the marker, two columns by MARKER_LINES lines, onto the
\ screen with its top line at zp_marker_address. Drawing it twice removes
\ it.
.render_marker
{
    LDA zp_marker_address
    AND #&F8
    STA zp_screen
    LDA zp_marker_address + 1
    STA zp_screen + 1
    LDA zp_marker_address
    AND #7
    TAY
    LDX #MARKER_LINES
.line_loop
    \ The second column is the next cell, which may be past the screen's end.
    CLC
    LDA zp_screen
    ADC #CELL_BYTES
    STA zp_screen_lower
    LDA zp_screen + 1
    ADC #0
    JSR wrap_screen_high
    STA zp_screen_lower + 1
    LDA (zp_screen),Y
    EOR #MARKER_COLOUR
    STA (zp_screen),Y
    LDA (zp_screen_lower),Y
    EOR #MARKER_COLOUR
    STA (zp_screen_lower),Y
    INY
    CPY #8
    BNE next_line
    LDY #0                      \ Down to the next character row
    CLC
    LDA zp_screen + 1
    ADC #HI(ROW_BYTES)
    JSR wrap_screen_high
    STA zp_screen + 1
.next_line
    DEX
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
