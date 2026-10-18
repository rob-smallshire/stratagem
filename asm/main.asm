\ MAIN: the game, in user RAM. For now: set up the 128 x 256 screen, draw a
\ 16 x 16 tile view of the world, and scroll it a tile at a time with
\ Z, X, K and M.

CLEAR USER_START, USER_END
ORG USER_START
GUARD USER_END

INITIAL_VIEW_X = 120
INITIAL_VIEW_Y = 44
SCROLL_FRAMES = 2               \ Frames between scroll steps while a key is held

\ Negative INKEY numbers, as OSBYTE &81 takes them in X
INKEY_Z = &100 - 98
INKEY_X = &100 - 67
INKEY_K = &100 - 71
INKEY_M = &100 - 102

.main_start
{
    LDX #&FF                    \ Reset the stack: the loader is finished
    TXS
    LDA #0
    STA zp_frame
    STA zp_scroll_timer
    JSR setup_screen
    JSR call_render_clear
    LDA #INITIAL_VIEW_X
    STA zp_view_x
    LDA #INITIAL_VIEW_Y
    STA zp_view_y
    LDA #LO(SCREEN_START)
    STA zp_screen_start
    LDA #HI(SCREEN_START)
    STA zp_screen_start + 1
    JSR set_crtc_start
    JSR draw_view
    LDA #BOOT_READY
    STA zp_boot_status
    \ Fall through into the main loop
}

.main_loop
{
    INC zp_frame
    LDA #19                     \ Wait for vertical sync
    JSR OSBYTE
    LDA zp_scroll_timer
    BEQ may_scroll
    DEC zp_scroll_timer
    JMP main_loop
.may_scroll
    JSR scroll_horizontally
    JSR scroll_vertically
    JMP main_loop
}

\ ---------------------------------------------------------------------------
\ Screen

\ Narrow MODE 2 to 64 columns (128 pixels), centred, and set the hardware
\ scroll wrap for a 16K screen at &4000.
.setup_screen
{
    SEI
    LDA #1                      \ R1: characters per line
    STA CRTC_ADDRESS
    LDA #64
    STA CRTC_DATA
    LDA #2                      \ R2: horizontal sync position
    STA CRTC_ADDRESS
    LDA #&5B
    STA CRTC_DATA
    LDA #4                      \ C0 = 0
    STA SYSTEM_VIA_B
    LDA #5                      \ C1 = 0: wrap at &8000 back to &4000
    STA SYSTEM_VIA_B
    CLI
    RTS
}

\ Point the CRTC at zp_screen_start.
.set_crtc_start
{
    LDA zp_screen_start + 1
    STA zp_ptr + 1
    LDA zp_screen_start
    LSR zp_ptr + 1
    ROR A
    LSR zp_ptr + 1
    ROR A
    LSR zp_ptr + 1
    ROR A
    SEI
    LDX #13                     \ R13: start address low
    STX CRTC_ADDRESS
    STA CRTC_DATA
    DEX                         \ R12: start address high
    STX CRTC_ADDRESS
    LDA zp_ptr + 1
    STA CRTC_DATA
    CLI
    RTS
}

\ Draw the whole view, a row at a time.
.draw_view
{
    LDA zp_view_y
    STA zp_strip_y
    LDA zp_screen_start
    STA strip_base
    LDA zp_screen_start + 1
    STA strip_base + 1
.row_loop
    JSR draw_row_strip
    INC zp_strip_y
    CLC
    LDA strip_base + 1
    ADC #HI(TILE_ROW_STEP)
    JSR wrap_high
    STA strip_base + 1
    LDA zp_strip_y
    SEC
    SBC zp_view_y
    CMP #VIEW_TILES
    BNE row_loop
    RTS
}

\ Draw world row zp_strip_y, from column zp_view_x, at strip_base.
.draw_row_strip
{
    LDA #LO(TILE_COLUMN_STEP)
    STA strip_step
    LDA #HI(TILE_COLUMN_STEP)
    STA strip_step + 1
    LDX zp_view_x
    LDY zp_strip_y
    LDA #0
    STA zp_strip_index
.loop
    JSR call_tile_at
    STX zp_strip_x
    LDX zp_strip_index
    STA strip_tiles,X
    INX
    STX zp_strip_index
    LDX zp_strip_x
    INX
    LDA zp_strip_index
    CMP #VIEW_TILES
    BNE loop
    JMP call_render_strip
}

\ Draw world column zp_strip_x, from row zp_view_y, at strip_base.
.draw_column_strip
{
    LDA #LO(TILE_ROW_STEP)
    STA strip_step
    LDA #HI(TILE_ROW_STEP)
    STA strip_step + 1
    LDX zp_strip_x
    LDY zp_view_y
    LDA #0
    STA zp_strip_index
.loop
    JSR call_tile_at
    STY zp_strip_y
    LDY zp_strip_index
    STA strip_tiles,Y
    INY
    STY zp_strip_index
    LDY zp_strip_y
    INY
    LDA zp_strip_index
    CMP #VIEW_TILES
    BNE loop
    JMP call_render_strip
}

\ Set strip_base to zp_screen_start plus the offset (A low, X high), wrapped.
.set_strip_base
{
    CLC
    ADC zp_screen_start
    STA strip_base
    TXA
    ADC zp_screen_start + 1
    JSR wrap_high
    STA strip_base + 1
    RTS
}

\ Wrap the high byte of a screen address in A back into the screen, after
\ adding to it.
.wrap_high
{
    CMP #HI(SCREEN_END)
    BCC done
    SBC #HI(SCREEN_END - SCREEN_START)
.done
    RTS
}

\ Move zp_screen_start back by the offset (A low, X high), wrapped.
.move_screen_start_back
{
    STA zp_ptr
    STX zp_ptr + 1
    SEC
    LDA zp_screen_start
    SBC zp_ptr
    STA zp_screen_start
    LDA zp_screen_start + 1
    SBC zp_ptr + 1
    CMP #HI(SCREEN_START)
    BCS done
    ADC #HI(SCREEN_END - SCREEN_START)
.done
    STA zp_screen_start + 1
    RTS
}

\ Move zp_screen_start on by the offset (A low, X high), wrapped.
.move_screen_start_on
{
    CLC
    ADC zp_screen_start
    STA zp_screen_start
    TXA
    ADC zp_screen_start + 1
    JSR wrap_high
    STA zp_screen_start + 1
    RTS
}

\ ---------------------------------------------------------------------------
\ Scrolling

.scroll_horizontally
{
    LDX #INKEY_X
    JSR key_pressed
    BEQ right
    LDX #INKEY_Z
    JSR key_pressed
    BEQ left
    RTS
.right
    LDA zp_view_x
    CMP #WORLD_LAST_VIEW
    BCS done
    INC zp_view_x
    LDA #LO(TILE_COLUMN_STEP)
    LDX #HI(TILE_COLUMN_STEP)
    JSR move_screen_start_on
    JSR set_crtc_start
    LDA zp_view_x               \ The new right-hand column
    CLC
    ADC #VIEW_TILES - 1
    STA zp_strip_x
    LDA #LO((VIEW_TILES - 1) * TILE_COLUMN_STEP)
    LDX #HI((VIEW_TILES - 1) * TILE_COLUMN_STEP)
    JMP draw_column
.left
    LDA zp_view_x
    BEQ done
    DEC zp_view_x
    LDA #LO(TILE_COLUMN_STEP)
    LDX #HI(TILE_COLUMN_STEP)
    JSR move_screen_start_back
    JSR set_crtc_start
    LDA zp_view_x               \ The new left-hand column
    STA zp_strip_x
    LDA #0
    TAX
.draw_column
    JSR set_strip_base
    JSR draw_column_strip
    LDA #SCROLL_FRAMES - 1
    STA zp_scroll_timer
.done
    RTS
}

.scroll_vertically
{
    LDX #INKEY_M
    JSR key_pressed
    BEQ down
    LDX #INKEY_K
    JSR key_pressed
    BEQ up
    RTS
.down
    LDA zp_view_y
    CMP #WORLD_LAST_VIEW
    BCS done
    INC zp_view_y
    LDA #LO(TILE_ROW_STEP)
    LDX #HI(TILE_ROW_STEP)
    JSR move_screen_start_on
    JSR set_crtc_start
    LDA zp_view_y               \ The new bottom row
    CLC
    ADC #VIEW_TILES - 1
    STA zp_strip_y
    LDA #LO((VIEW_TILES - 1) * TILE_ROW_STEP)
    LDX #HI((VIEW_TILES - 1) * TILE_ROW_STEP)
    JMP draw_row
.up
    LDA zp_view_y
    BEQ done
    DEC zp_view_y
    LDA #LO(TILE_ROW_STEP)
    LDX #HI(TILE_ROW_STEP)
    JSR move_screen_start_back
    JSR set_crtc_start
    LDA zp_view_y               \ The new top row
    STA zp_strip_y
    LDA #0
    TAX
.draw_row
    JSR set_strip_base
    JSR draw_row_strip
    LDA #SCROLL_FRAMES - 1
    STA zp_scroll_timer
.done
    RTS
}

\ Return Z set if the key with negative INKEY number X is pressed.
.key_pressed
{
    LDA #&81
    LDY #&FF
    JSR OSBYTE
    CPX #&FF
    RTS
}

.main_end

SAVE "MAIN", main_start, main_end
