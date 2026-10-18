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

\ Draw VIEW_TILES tiles from strip_tiles at strip_base, strip_base +
\ strip_step, and so on. strip_base must be inside the screen, and
\ strip_step less than the screen size.
.render_strip
{
    LDA strip_base
    STA zp_screen
    LDA strip_base + 1
    STA zp_screen + 1
    LDX #0
.tile_loop
    STX zp_render_index
    \ zp_tile = tile_graphics + tile * TILE_BYTES
    LDA #0
    STA zp_tile + 1
    LDA strip_tiles,X
    ASL A
    ASL A
    ASL A
    ASL A
    ROL zp_tile + 1
    ASL A
    ROL zp_tile + 1
    ASL A
    ROL zp_tile + 1
    CLC
    ADC #LO(tile_graphics)
    STA zp_tile
    LDA zp_tile + 1
    ADC #HI(tile_graphics)
    STA zp_tile + 1
    JSR plot_tile
    CLC
    LDA zp_screen
    ADC strip_step
    STA zp_screen
    LDA zp_screen + 1
    ADC strip_step + 1
    JSR wrap_screen_high
    STA zp_screen + 1
    LDX zp_render_index
    INX
    CPX #VIEW_TILES
    BNE tile_loop
    RTS
}

\ Plot the tile at zp_tile: its top half (four columns of eight lines,
\ 32 bytes) at zp_screen and its bottom half one character row below. A
\ half never crosses the screen's end, because tiles are 32-byte aligned.
.plot_tile
{
    LDY #31
.top_loop
    LDA (zp_tile),Y
    STA (zp_screen),Y
    DEY
    BPL top_loop
    CLC
    LDA zp_tile
    ADC #32
    STA zp_tile_lower
    LDA zp_tile + 1
    ADC #0
    STA zp_tile_lower + 1
    LDA zp_screen
    STA zp_screen_lower
    LDA zp_screen + 1
    CLC
    ADC #HI(ROW_BYTES)
    JSR wrap_screen_high
    STA zp_screen_lower + 1
    LDY #31
.bottom_loop
    LDA (zp_tile_lower),Y
    STA (zp_screen_lower),Y
    DEY
    BPL bottom_loop
    RTS
}

\ Wrap the high byte of a screen address in A back into the screen.
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
