\ Drawing the view: the screen's set-up and hardware scroll, new rows and
\ columns as the camera moves, the whole view, the player's sprite, and tiles
\ that have changed. All by way of the renderer (call_render_*), from the
\ tile cache and the camera.

\ Draw the view's new top or bottom row, which is in the hidden row until the
\ flip. When the camera also moves sideways, the row's cells at the new
\ columns are left to the column drawing: they are outside the hidden row.
.draw_new_row
{
    LDY #0                      \ New top row: view row 0
    LDA zp_plan_dy
    BMI top
    LDY #VIEW_ROWS - 1          \ New bottom row
.top
    TYA
    CLC
    ADC zp_camera_y
    STA zp_render_v
    TYA                         \ Base = screen_start + row * ROW_BYTES
    ASL A
    CLC
    ADC zp_screen_start + 1
    JSR wrap_both_ways
    STA zp_render_base + 1
    LDA zp_screen_start
    STA zp_render_base
    \ The first column drawn: -dx if moving left, otherwise 0.
    LDA zp_plan_dx
    BPL first_column_zero
    EOR #&FF
    CLC
    ADC #1
    BNE first_column_set
.first_column_zero
    LDA #0
.first_column_set
    STA zp_temp
    ASL A                       \ Base += first * CELL_BYTES (at most 16)
    ASL A
    ASL A
    CLC
    ADC zp_render_base
    STA zp_render_base
    LDA zp_render_base + 1
    ADC #0
    JSR wrap_both_ways
    STA zp_render_base + 1
    LDA zp_camera_x             \ u = camera_x + first
    CLC
    ADC zp_temp
    STA zp_render_u
    \ Count = VIEW_COLUMNS - |dx|
    LDA zp_plan_dx
    BPL dx_absolute
    EOR #&FF
    CLC
    ADC #1
.dx_absolute
    STA zp_temp
    LDA #VIEW_COLUMNS
    SEC
    SBC zp_temp
    STA zp_render_count
    JMP call_render_row
}

\ Plan the view's new columns, to be drawn at the flip.
.plan_new_columns
{
    LDA zp_plan_dx
    BMI left
    STA zp_columns_width
    LDA #VIEW_COLUMNS           \ New columns VIEW_COLUMNS - dx onwards
    SEC
    SBC zp_plan_dx
    BNE first_set
.left
    EOR #&FF
    CLC
    ADC #1
    STA zp_columns_width
    LDA #0                      \ New columns 0 onwards
.first_set
    STA zp_temp
    CLC
    ADC zp_camera_x
    STA zp_columns_u
    LDA #0                      \ Base = screen_start + first * CELL_BYTES
    STA zp_temp + 1
    LDA zp_temp
    ASL A
    ASL A
    ASL A
    ROL zp_temp + 1
    CLC
    ADC zp_screen_start
    STA zp_columns_base
    LDA zp_temp + 1
    ADC zp_screen_start + 1
    JSR wrap_both_ways
    STA zp_columns_base + 1
    RTS
}

\ Draw X rows, from view row A, of the planned new columns, a row at a time,
\ ahead of the beam.
.draw_column_rows
{
    CPX #0
    BEQ done
    LDY zp_columns_width
    BEQ done
    STY zp_render_width
    STX zp_render_count
    PHA
    CLC
    ADC zp_camera_y
    STA zp_render_v
    PLA                         \ Base = columns_base + row * ROW_BYTES
    ASL A
    CLC
    ADC zp_columns_base + 1
    JSR wrap_both_ways
    STA zp_render_base + 1
    LDA zp_columns_base
    STA zp_render_base
    LDA zp_columns_u
    STA zp_render_u
    JMP call_render_columns
.done
    RTS
}

\ Set zp_split_row to the view row two above the top of the sprite's new
\ position (or 0): the sprite, where it was and where it will be, is below
\ it, as the player moves at most 6 lines and the camera a row a frame.
.sprite_split_row
{
    JSR sprite_view_line
    LSR A
    LSR A
    LSR A
    SEC
    SBC #2
    BCS set
    LDA #0
.set
    STA zp_split_row
    RTS
}

\ Return in A (and zp_temp + 1) the view line of the player's top, with
\ zp_box_x/y set to its position in pixels and lines.
.sprite_view_line
{
    JSR player_pixels
    LDA zp_camera_y + 1         \ line = py - camera_y * 8
    STA zp_ptr + 1
    LDA zp_camera_y
    ASL A
    ROL zp_ptr + 1
    ASL A
    ROL zp_ptr + 1
    ASL A
    ROL zp_ptr + 1
    STA zp_ptr
    SEC
    LDA zp_box_y
    SBC zp_ptr
    STA zp_temp + 1
    RTS
}

\ Draw the whole view, a row at a time, from the tile cache.
.draw_view
{
    LDA #0
    STA zp_sprite_drawn         \ The sprite and the items are drawn over
    STA host_items_drawn
    STA zp_columns_width
    LDA zp_screen_start
    STA zp_render_base
    LDA zp_screen_start + 1
    STA zp_temp                 \ Base of each row, high byte
    LDA zp_camera_y
    STA zp_temp + 1             \ World row of each row
    LDA #VIEW_ROWS
    STA zp_rows_left
.row_loop
    LDA zp_temp
    STA zp_render_base + 1
    LDA zp_camera_x
    STA zp_render_u
    LDA zp_temp + 1
    STA zp_render_v
    LDA #VIEW_COLUMNS
    STA zp_render_count
    JSR call_render_row
    INC zp_temp + 1
    CLC
    LDA zp_temp
    ADC #HI(ROW_BYTES)
    JSR wrap_both_ways
    STA zp_temp
    DEC zp_rows_left
    BNE row_loop
    RTS
}

\ Narrow MODE 2 to 64 columns (128 pixels), centred, display VIEW_ROWS of the
\ 32 rows, and set the hardware scroll wrap for a 16K screen at &4000.
.setup_screen
{
    SEI
    LDA #1                      \ R1: characters per line
    STA CRTC_ADDRESS
    LDA #VIEW_COLUMNS
    STA CRTC_DATA
    LDA #2                      \ R2: horizontal sync position
    STA CRTC_ADDRESS
    LDA #&5B
    STA CRTC_DATA
    LDA #6                      \ R6: character rows displayed
    STA CRTC_ADDRESS
    LDA #VIEW_ROWS
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

\ Draw the player's sprite, saving the screen under it.
.draw_sprite
{
    \ View column = (px >> 1) - camera_x, line = py - camera_y * 8
    JSR sprite_view_line        \ Line, in zp_temp + 1
    LDA zp_box_x + 1
    LSR A
    LDA zp_box_x
    ROR A
    SEC
    SBC zp_camera_x
    STA zp_temp                 \ Column
    \ Address = screen_start + (line >> 3) * ROW_BYTES + column * 8 + (line AND 7)
    LDA #0
    STA zp_ptr + 1
    LDA zp_temp
    ASL A
    ASL A
    ROL zp_ptr + 1
    ASL A
    ROL zp_ptr + 1
    STA zp_ptr
    LDA zp_temp + 1
    LSR A
    LSR A
    AND #&FE                    \ (line >> 3) * 2 pages
    CLC
    ADC zp_ptr + 1
    STA zp_ptr + 1
    LDA zp_temp + 1
    AND #7
    ORA zp_ptr                  \ Column * 8 has its low three bits clear
    CLC
    ADC zp_screen_start
    STA zp_sprite_address
    LDA zp_ptr + 1
    ADC zp_screen_start + 1
    JSR wrap_both_ways
    STA zp_sprite_address + 1
    LDA zp_player_frame
    STA zp_sprite_frame
    JSR call_render_sprite
    LDA #&FF
    STA zp_sprite_drawn
    RTS
}

\ Remove the player's sprite, if it is drawn.
.restore_sprite
{
    LDA zp_sprite_drawn
    BEQ done
    JSR call_render_restore
    LDA #0
    STA zp_sprite_drawn
.done
    RTS
}

\ Redraw the tile queued by change_target, if any.
.redraw_queued_tile
{
    LDA redraw_tile
    BEQ done
    LDA #0
    STA redraw_tile
    LDA redraw_tile_x
    STA target_x
    LDA redraw_tile_y
    STA target_y
    JMP redraw_target
.done
    RTS
}

\ Redraw the visible cells of the tile at target_x/y: two cell rows of up
\ to four cells.
.redraw_target
{
    \ Column of its first cell in the view: 4 * x - camera_x, signed.
    LDA #0
    STA zp_temp + 1
    LDA target_x
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    SEC
    SBC zp_camera_x
    STA zp_temp
    LDA zp_temp + 1
    SBC zp_camera_x + 1
    BEQ right_of_left_edge
    CMP #&FF
    BNE off_view                \ Far off the view
    LDA zp_temp
    CMP #&100 - 3
    BCS partly_left
.off_view
    RTS                         \ Entirely left of the view
.partly_left
    \ Partly left of the view: draw from column 0.
    CLC
    ADC #4
    STA zp_render_width         \ Cells to draw (count, kept here for now)
    LDA #0
    STA zp_temp
    BEQ columns_set
.right_of_left_edge
    LDA zp_temp
    CMP #VIEW_COLUMNS
    BCS off_view                \ Right of the view
    LDA #VIEW_COLUMNS           \ min(4, VIEW_COLUMNS - first)
    SEC
    SBC zp_temp
    CMP #4
    BCC count_set
    LDA #4
.count_set
    STA zp_render_width
.columns_set
    \ zp_temp is the first view column, zp_render_width the count. Each of
    \ the tile's two cell rows: v = 2 * y + half.
    LDX #0
.half_loop
    STX zp_temp + 1
    LDA target_y             \ View row = 2 * y + half - camera_y
    ASL A
    STA zp_ptr
    LDA #0
    ROL A
    STA zp_ptr + 1
    TXA
    ORA zp_ptr
    STA zp_ptr
    SEC
    SBC zp_camera_y
    STA zp_render_v             \ Temporarily the view row
    LDA zp_ptr + 1
    SBC zp_camera_y + 1
    BNE next_half
    LDA zp_render_v
    CMP #VIEW_ROWS
    BCS next_half
    \ Base = screen_start + row * ROW_BYTES + column * CELL_BYTES.
    ASL A
    CLC
    ADC zp_screen_start + 1
    STA zp_render_base + 1
    LDA zp_temp
    ASL A
    ASL A
    ASL A
    PHP
    CLC
    ADC zp_screen_start
    STA zp_render_base
    LDA zp_render_base + 1
    ADC #0
    PLP
    ADC #0                      \ Column * 8 can carry into the high byte
    JSR wrap_both_ways
    STA zp_render_base + 1
    LDA zp_ptr                  \ v, low byte
    STA zp_render_v
    CLC                         \ u = camera_x + first column, low byte
    LDA zp_camera_x
    ADC zp_temp
    STA zp_render_u
    LDA zp_render_width
    STA zp_render_count
    LDA zp_temp
    PHA
    LDA zp_temp + 1
    PHA
    JSR call_render_row
    PLA
    STA zp_temp + 1
    PLA
    STA zp_temp
.next_half
    LDX zp_temp + 1
    INX
    CPX #2
    BNE half_loop
.done
    RTS
}
