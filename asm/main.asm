\ MAIN: the game, in user RAM. For now: a focus marker moved with Z, X, K
\ and M, and a camera that follows it, scrolling the world smoothly.
\
\ Each frame, just after vertical sync, the screen is flipped: the CRTC is
\ given the new start address, and any newly exposed columns are drawn,
\ top-down, ahead of the beam. A newly exposed row is always the hidden
\ 32nd row, so it is drawn before the flip, while it cannot be seen. The rest
\ of the frame moves the focus and plans the next flip.

CLEAR USER_START, USER_END
ORG USER_START
GUARD USER_END

INITIAL_FOCUS_X = 128 * 8       \ Pixels
INITIAL_FOCUS_Y = 52 * 16       \ Lines

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
    STA zp_input
    STA zp_lead
    STA zp_camera_x
    STA zp_camera_x + 1
    STA zp_camera_y
    STA zp_camera_y + 1
    STA zp_columns_planned
    STA zp_marker_drawn
    LDA #LO(INITIAL_FOCUS_X)
    STA zp_focus_x
    LDA #HI(INITIAL_FOCUS_X)
    STA zp_focus_x + 1
    LDA #LO(INITIAL_FOCUS_Y)
    STA zp_focus_y
    LDA #HI(INITIAL_FOCUS_Y)
    STA zp_focus_y + 1
    LDA #LO(SCREEN_START)
    STA zp_screen_start
    LDA #HI(SCREEN_START)
    STA zp_screen_start + 1
    JSR setup_screen
    JSR call_render_clear
    JSR plan_camera             \ The focus is outside the view, so redraw
    JSR apply_plan
    JSR set_crtc_start
    JSR draw_marker
    LDA #BOOT_READY
    STA zp_boot_status
    \ Fall through into the main loop
}

.main_loop
    INC zp_frame
    LDA #19                     \ Wait for vertical sync
    JSR OSBYTE
    JSR undraw_marker
    JSR flip
    JSR draw_marker
.frame_shown                    \ The screen now shows the camera's view
    JSR read_input
    JSR update_focus
    JSR plan_camera
    JSR apply_plan
    JMP main_loop

\ ---------------------------------------------------------------------------
\ Input

.read_input
{
    LDA #0
    STA zp_input
    LDX #INKEY_Z
    LDA #INPUT_LEFT
    JSR read_key
    LDX #INKEY_X
    LDA #INPUT_RIGHT
    JSR read_key
    LDX #INKEY_K
    LDA #INPUT_UP
    JSR read_key
    LDX #INKEY_M
    LDA #INPUT_DOWN
    \ Fall through
}

\ If the key with negative INKEY number X is pressed, set bits A in zp_input.
.read_key
{
    PHA
    LDA #&81
    LDY #&FF
    JSR OSBYTE
    PLA
    CPX #&FF
    BNE done
    ORA zp_input
    STA zp_input
.done
    RTS
}

\ ---------------------------------------------------------------------------
\ Focus and camera: modelled exactly by tools/stratagem/camera.py. These
\ routines are pure, using only zero page, so they can be tested in py65.

\ Move the focus by zp_input, and ease the lead towards the direction of
\ travel.
.update_focus
{
    LDA zp_input
    AND #INPUT_LEFT OR INPUT_RIGHT
    CMP #INPUT_RIGHT
    BEQ right
    CMP #INPUT_LEFT
    BEQ left
    LDA #0
    BEQ ease_lead
.right
    CLC
    LDA zp_focus_x
    ADC #FOCUS_SPEED_X
    STA zp_focus_x
    BCC right_added
    INC zp_focus_x + 1
.right_added
    LDA #LO(FOCUS_X_MAX)        \ Clamp to FOCUS_X_MAX
    CMP zp_focus_x
    LDA #HI(FOCUS_X_MAX)
    SBC zp_focus_x + 1
    BCS right_done
    LDA #LO(FOCUS_X_MAX)
    STA zp_focus_x
    LDA #HI(FOCUS_X_MAX)
    STA zp_focus_x + 1
.right_done
    LDA #LEAD_MAX
    BNE ease_lead
.left
    SEC
    LDA zp_focus_x
    SBC #FOCUS_SPEED_X
    STA zp_focus_x
    LDA zp_focus_x + 1
    SBC #0
    STA zp_focus_x + 1
    BCS left_done               \ Clamp to 0
    LDA #0
    STA zp_focus_x
    STA zp_focus_x + 1
.left_done
    LDA #&100 - LEAD_MAX
.ease_lead                      \ Move zp_lead one step towards A
    STA zp_temp
    LDA zp_lead
    SEC
    SBC zp_temp                 \ lead - target, small enough not to overflow
    BEQ vertical
    BMI increase_lead
    DEC zp_lead
    JMP vertical
.increase_lead
    INC zp_lead
.vertical
    LDA zp_input
    AND #INPUT_UP OR INPUT_DOWN
    CMP #INPUT_DOWN
    BEQ down
    CMP #INPUT_UP
    BEQ up
    RTS
.down
    CLC
    LDA zp_focus_y
    ADC #FOCUS_SPEED_Y
    STA zp_focus_y
    BCC down_added
    INC zp_focus_y + 1
.down_added
    LDA #LO(FOCUS_Y_MAX)        \ Clamp to FOCUS_Y_MAX
    CMP zp_focus_y
    LDA #HI(FOCUS_Y_MAX)
    SBC zp_focus_y + 1
    BCS done
    LDA #LO(FOCUS_Y_MAX)
    STA zp_focus_y
    LDA #HI(FOCUS_Y_MAX)
    STA zp_focus_y + 1
    RTS
.up
    SEC
    LDA zp_focus_y
    SBC #FOCUS_SPEED_Y
    STA zp_focus_y
    LDA zp_focus_y + 1
    SBC #0
    STA zp_focus_y + 1
    BCS done                    \ Clamp to 0
    LDA #0
    STA zp_focus_y
    STA zp_focus_y + 1
.done
    RTS
}

\ Decide where the camera goes next: set zp_camera_x/y, and either
\ zp_plan_dx/dy, the movement to apply at the next flip, or zp_redraw.
.plan_camera
{
    LDA #0
    STA zp_redraw
    STA zp_plan_dx
    STA zp_plan_dy
    \ The focus column and row, and where they are in the view.
    LDA zp_focus_x + 1
    LSR A
    STA zp_column + 1
    LDA zp_focus_x
    ROR A
    STA zp_column
    LDA zp_focus_y + 1
    STA zp_row + 1
    LDA zp_focus_y
    LSR zp_row + 1
    ROR A
    LSR zp_row + 1
    ROR A
    LSR zp_row + 1
    ROR A
    STA zp_row
    SEC
    LDA zp_column
    SBC zp_camera_x
    STA zp_relative_x
    LDA zp_column + 1
    SBC zp_camera_x + 1
    BNE jump_to_redraw          \ Left of the view, or far right of it
    LDA zp_relative_x
    CMP #VIEW_COLUMNS
    BCS jump_to_redraw
    SEC
    LDA zp_row
    SBC zp_camera_y
    STA zp_relative_y
    LDA zp_row + 1
    SBC zp_camera_y + 1
    BNE jump_to_redraw
    LDA zp_relative_y
    CMP #VIEW_ROWS
    BCC in_view
.jump_to_redraw
    JMP redraw
.in_view
    \ Horizontally: keep the focus in the window, shifted by the lead.
    LDA #WINDOW_LEFT
    SEC
    SBC zp_lead
    STA zp_temp                 \ Left edge of the window
    LDA zp_relative_x
    CMP zp_temp
    BCS not_left
    LDA zp_temp                 \ Step left by min(MAX_STEP_X, (left - x + 3) >> 2)
    SEC
    SBC zp_relative_x
    CLC
    ADC #3
    LSR A
    LSR A
    CMP #MAX_STEP_X
    BCC left_step
    LDA #MAX_STEP_X
.left_step
    EOR #&FF                    \ Negate
    CLC
    ADC #1
    STA zp_plan_dx
    JMP vertical
.not_left
    LDA #WINDOW_RIGHT
    SEC
    SBC zp_lead
    STA zp_temp                 \ Right edge of the window
    LDA zp_relative_x
    CMP zp_temp
    BCC vertical
    SEC                         \ Step right by min(MAX_STEP_X, (x - right + 4) >> 2)
    SBC zp_temp
    CLC
    ADC #4
    LSR A
    LSR A
    CMP #MAX_STEP_X
    BCC right_step
    LDA #MAX_STEP_X
.right_step
    STA zp_plan_dx
.vertical
    LDA zp_relative_y
    CMP #WINDOW_TOP
    BCS not_up
    LDA #&FF
    STA zp_plan_dy
    BNE apply
.not_up
    CMP #WINDOW_BOTTOM
    BCC apply
    LDA #1
    STA zp_plan_dy
.apply
    \ Move the camera, clamped to the world, and record how far it moved.
    LDA zp_camera_x
    STA zp_temp
    LDA zp_plan_dx
    BEQ x_done
    BMI x_left
    CLC
    ADC zp_camera_x
    STA zp_camera_x
    BCC x_added
    INC zp_camera_x + 1
.x_added
    LDA #LO(CAMERA_X_MAX)
    CMP zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    SBC zp_camera_x + 1
    BCS x_moved
    LDA #LO(CAMERA_X_MAX)
    STA zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    STA zp_camera_x + 1
    JMP x_moved
.x_left
    CLC
    ADC zp_camera_x
    STA zp_camera_x
    LDA zp_camera_x + 1
    ADC #&FF
    STA zp_camera_x + 1
    BCS x_moved                 \ No borrow, so not below 0
    LDA #0
    STA zp_camera_x
    STA zp_camera_x + 1
.x_moved
    LDA zp_camera_x
    SEC
    SBC zp_temp
    STA zp_plan_dx
.x_done
    LDA zp_camera_y
    STA zp_temp
    LDA zp_plan_dy
    BEQ y_done
    BMI y_up
    CLC
    ADC zp_camera_y
    STA zp_camera_y
    BCC y_added
    INC zp_camera_y + 1
.y_added
    LDA #LO(CAMERA_Y_MAX)
    CMP zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    SBC zp_camera_y + 1
    BCS y_moved
    LDA #LO(CAMERA_Y_MAX)
    STA zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    STA zp_camera_y + 1
    JMP y_moved
.y_up
    CLC
    ADC zp_camera_y
    STA zp_camera_y
    LDA zp_camera_y + 1
    ADC #&FF
    STA zp_camera_y + 1
    BCS y_moved
    LDA #0
    STA zp_camera_y
    STA zp_camera_y + 1
.y_moved
    LDA zp_camera_y
    SEC
    SBC zp_temp
    STA zp_plan_dy
.y_done
    RTS

    \ The focus is outside the view: centre the view on it.
.redraw
    LDA #&FF
    STA zp_redraw
    SEC                         \ camera_x = clamp(column - CENTRE_X, 0, CAMERA_X_MAX)
    LDA zp_column
    SBC #CENTRE_X
    STA zp_camera_x
    LDA zp_column + 1
    SBC #0
    STA zp_camera_x + 1
    BCS redraw_x_not_negative
    LDA #0
    STA zp_camera_x
    STA zp_camera_x + 1
.redraw_x_not_negative
    LDA #LO(CAMERA_X_MAX)
    CMP zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    SBC zp_camera_x + 1
    BCS redraw_x_done
    LDA #LO(CAMERA_X_MAX)
    STA zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    STA zp_camera_x + 1
.redraw_x_done
    SEC                         \ camera_y = clamp(row - CENTRE_Y, 0, CAMERA_Y_MAX)
    LDA zp_row
    SBC #CENTRE_Y
    STA zp_camera_y
    LDA zp_row + 1
    SBC #0
    STA zp_camera_y + 1
    BCS redraw_y_not_negative
    LDA #0
    STA zp_camera_y
    STA zp_camera_y + 1
.redraw_y_not_negative
    LDA #LO(CAMERA_Y_MAX)
    CMP zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    SBC zp_camera_y + 1
    BCS redraw_y_done
    LDA #LO(CAMERA_Y_MAX)
    STA zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    STA zp_camera_y + 1
.redraw_y_done
    RTS
}

\ ---------------------------------------------------------------------------
\ Applying the plan

\ Redraw the whole view, or move the screen start by the planned movement,
\ draw the new row (if any) into the hidden row, and prepare the new
\ columns (if any) to be drawn at the flip.
.apply_plan
{
    LDA zp_redraw
    BEQ move
    JMP redraw_view
.move
    \ zp_screen_start += plan_dx * CELL_BYTES + plan_dy * ROW_BYTES, wrapped.
    LDA #0
    STA zp_temp + 1
    LDA zp_plan_dx
    BPL dx_positive
    DEC zp_temp + 1             \ Sign extend
.dx_positive
    LDA zp_plan_dy              \ +1 or -1 rows: +2 or -2 pages
    ASL A
    CLC
    ADC zp_temp + 1
    STA zp_temp + 1             \ High byte of the offset
    LDA zp_plan_dx
    ASL A
    ASL A
    ASL A
    CLC
    ADC zp_screen_start
    STA zp_screen_start
    LDA zp_screen_start + 1
    ADC zp_temp + 1
    JSR wrap_both_ways
    STA zp_screen_start + 1
    LDA zp_plan_dy
    BEQ no_row
    JSR draw_new_row
.no_row
    LDA zp_plan_dx
    BEQ no_columns
    JMP prepare_new_columns
.no_columns
    RTS
}

\ Wrap a screen address high byte in A, after a signed addition, back into
\ the screen.
.wrap_both_ways
{
    CMP #HI(SCREEN_START)
    BCC below
    CMP #HI(SCREEN_END)
    BCC done
    SBC #HI(SCREEN_END - SCREEN_START)
    RTS
.below
    ADC #HI(SCREEN_END - SCREEN_START)
.done
    RTS
}

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
    STA zp_cell_v
    LDA zp_camera_y + 1
    ADC #0
    STA zp_cell_v + 1
    TYA                         \ cell_base = screen_start + row * ROW_BYTES
    ASL A
    CLC
    ADC zp_screen_start + 1
    JSR wrap_both_ways
    STA cell_base + 1
    LDA zp_screen_start
    STA cell_base
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
    ASL A                       \ cell_base += first * CELL_BYTES (at most 16)
    ASL A
    ASL A
    CLC
    ADC cell_base
    STA cell_base
    LDA cell_base + 1
    ADC #0
    JSR wrap_both_ways
    STA cell_base + 1
    CLC                         \ u = camera_x + first
    LDA zp_camera_x
    ADC zp_temp
    STA zp_cell_u
    LDA zp_camera_x + 1
    ADC #0
    STA zp_cell_u + 1
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
    STA zp_cell_count
    STA cell_end
    LDA #0
    STA zp_cell_down
    STA cell_first
    LDX #0
    JSR prepare_cells
    LDA #CELL_BYTES
    STA cell_step
    LDA #0
    STA cell_step + 1
    JMP call_render_cells
}

\ Prepare the view's new columns, to be drawn at the flip.
.prepare_new_columns
{
    LDA zp_plan_dx
    BMI left
    STA zp_columns_planned
    LDA #VIEW_COLUMNS           \ New columns VIEW_COLUMNS - dx onwards
    SEC
    SBC zp_plan_dx
    BNE first_set
.left
    EOR #&FF
    CLC
    ADC #1
    STA zp_columns_planned
    LDA #0                      \ New columns 0 onwards
.first_set
    STA zp_view_column
    LDX #0                      \ Index into the cell list
    LDY #0                      \ Which new column
.column_loop
    STY zp_new_column
    \ column_base[Y] = screen_start + column * CELL_BYTES, wrapped
    LDA zp_view_column
    ASL A
    ASL A
    ASL A
    STA zp_temp
    LDA #0
    ROL A
    STA column_base_high,Y
    CLC
    LDA zp_temp
    ADC zp_screen_start
    STA column_base_low,Y
    LDA column_base_high,Y
    ADC zp_screen_start + 1
    JSR wrap_both_ways
    STA column_base_high,Y
    CLC                         \ u = camera_x + column, v = camera_y
    LDA zp_camera_x
    ADC zp_view_column
    STA zp_cell_u
    LDA zp_camera_x + 1
    ADC #0
    STA zp_cell_u + 1
    LDA zp_camera_y
    STA zp_cell_v
    LDA zp_camera_y + 1
    STA zp_cell_v + 1
    LDA #VIEW_ROWS
    STA zp_cell_count
    STA zp_cell_down
    JSR prepare_cells
    INC zp_view_column
    LDY zp_new_column
    INY
    CPY zp_columns_planned
    BNE column_loop
    RTS
}

\ After vertical sync: point the CRTC at the new screen start, and draw the
\ planned columns, each top-down, ahead of the beam.
.flip
{
    JSR set_crtc_start
    LDA #LO(ROW_BYTES)
    STA cell_step
    LDA #HI(ROW_BYTES)
    STA cell_step + 1
    LDA #0
    STA cell_first
    LDY #0
.column_loop
    CPY zp_columns_planned
    BEQ done
    LDA column_base_low,Y
    STA cell_base
    LDA column_base_high,Y
    STA cell_base + 1
    LDA cell_first
    CLC
    ADC #VIEW_ROWS
    STA cell_end
    STY zp_new_column
    JSR call_render_cells
    LDA cell_end
    STA cell_first
    LDY zp_new_column
    INY
    BNE column_loop
.done
    LDA #0
    STA zp_columns_planned
    RTS
}

\ Draw the whole view at the camera, a row at a time.
.redraw_view
{
    LDA #0
    STA zp_marker_drawn         \ The marker is drawn over
    STA zp_columns_planned
    STA cell_first
    LDA #VIEW_COLUMNS
    STA cell_end
    LDA #CELL_BYTES
    STA cell_step
    LDA #0
    STA cell_step + 1
    LDA zp_screen_start
    STA cell_base
    LDA zp_screen_start + 1
    STA cell_base + 1
    LDA zp_camera_y
    STA zp_cell_v
    LDA zp_camera_y + 1
    STA zp_cell_v + 1
    LDA #VIEW_ROWS
    STA zp_rows_left
.row_loop
    LDA zp_camera_x
    STA zp_cell_u
    LDA zp_camera_x + 1
    STA zp_cell_u + 1
    LDA #VIEW_COLUMNS
    STA zp_cell_count
    LDA #0
    STA zp_cell_down
    LDX #0
    JSR prepare_cells
    JSR call_render_cells
    INC zp_cell_v               \ prepare_cells left it unchanged along a row
    BNE v_done
    INC zp_cell_v + 1
.v_done
    CLC
    LDA cell_base + 1
    ADC #HI(ROW_BYTES)
    JSR wrap_both_ways
    STA cell_base + 1
    DEC zp_rows_left
    BNE row_loop
    RTS
}

\ Fill the cell list from index X with the graphics addresses of
\ zp_cell_count world cells from (zp_cell_u, zp_cell_v), along the row, or
\ down the column if zp_cell_down is non-zero.
.prepare_cells
{
    JSR fetch_tile
.cell_loop
    LDA zp_cell_v               \ Offset in the tile: (v AND 1) * 32 + (u AND 3) * 8
    AND #1
    LSR A
    ROR A
    ROR A
    ROR A
    STA zp_temp
    LDA zp_cell_u
    AND #3
    ASL A
    ASL A
    ASL A
    ORA zp_temp
    LDY zp_cell_tile
    CLC
    ADC tile_address_low,Y
    STA cell_source_low,X
    LDA tile_address_high,Y
    ADC #0
    STA cell_source_high,X
    INX
    DEC zp_cell_count
    BEQ done
    LDA zp_cell_down
    BNE down
    INC zp_cell_u
    BNE u_done
    INC zp_cell_u + 1
.u_done
    LDA zp_cell_u
    AND #3
    BNE cell_loop               \ Still in the same tile
    JSR fetch_tile
    JMP cell_loop
.down
    INC zp_cell_v
    BNE v_done
    INC zp_cell_v + 1
.v_done
    LDA zp_cell_v
    AND #1
    BNE cell_loop
    JSR fetch_tile
    JMP cell_loop
.done
    RTS
}

\ Set zp_cell_tile to the tile containing world cell (zp_cell_u, zp_cell_v).
\ Preserves X.
.fetch_tile
{
    STX zp_cell_index
    LDA zp_cell_u + 1           \ Tile x = u >> 2
    STA zp_temp + 1
    LDA zp_cell_u
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    TAX
    LDA zp_cell_v + 1           \ Tile y = v >> 1
    LSR A
    LDA zp_cell_v
    ROR A
    TAY
    JSR call_tile_at
    STA zp_cell_tile
    LDX zp_cell_index
    RTS
}

\ ---------------------------------------------------------------------------
\ Screen

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

\ Draw the marker at the focus.
.draw_marker
{
    \ View column = (focus_x >> 1) - camera_x, line = focus_y - camera_y * 8
    LDA zp_focus_x + 1
    LSR A
    LDA zp_focus_x
    ROR A
    SEC
    SBC zp_camera_x
    STA zp_temp                 \ Column
    LDA zp_camera_y + 1
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
    LDA zp_focus_y
    SBC zp_ptr
    STA zp_temp + 1             \ Line
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
    STA zp_marker_address
    LDA zp_ptr + 1
    ADC zp_screen_start + 1
    JSR wrap_both_ways
    STA zp_marker_address + 1
    JSR call_render_marker
    LDA #&FF
    STA zp_marker_drawn
    RTS
}

\ Remove the marker, if it is drawn.
.undraw_marker
{
    LDA zp_marker_drawn
    BEQ done
    JSR call_render_marker
    LDA #0
    STA zp_marker_drawn
.done
    RTS
}

\ ---------------------------------------------------------------------------
\ Data

\ The graphics address of each tile, in the render region.
.tile_address_low
    FOR tile, 0, TILE_COUNT - 1
        EQUB LO(tile_graphics + tile * TILE_BYTES)
    NEXT
.tile_address_high
    FOR tile, 0, TILE_COUNT - 1
        EQUB HI(tile_graphics + tile * TILE_BYTES)
    NEXT

.column_base_low    SKIP MAX_STEP_X
.column_base_high   SKIP MAX_STEP_X

.main_end

SAVE "MAIN", main_start, main_end
