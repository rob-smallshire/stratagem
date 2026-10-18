\ MAIN: the game, in user RAM. For now: the player walks (Z, X) and jumps
\ (K) about the world, digs (L) and places blocks (SPACE), aiming down (M)
\ or up (K) or ahead, and the camera follows, scrolling smoothly.
\
\ Each frame, just after vertical sync, the screen is flipped: the CRTC is
\ given the new start address, and any newly exposed columns are drawn,
\ top-down, ahead of the beam. A newly exposed row is always the hidden
\ 32nd row, so it is drawn before the flip, while it cannot be seen. The rest
\ of the frame moves the player and plans the next flip.

CLEAR USER_START, USER_END
ORG USER_START
GUARD USER_END

\ Negative INKEY numbers, as OSBYTE &81 takes them in X
INKEY_Z = &100 - 98
INKEY_X = &100 - 67
INKEY_K = &100 - 71
INKEY_M = &100 - 102
INKEY_L = &100 - 87
INKEY_SPACE = &100 - 99

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
    STA zp_columns_width
    STA zp_sprite_drawn
    STA zp_direction
    STA zp_player_vx
    STA zp_player_vy
    STA zp_player_on_ground
    STA inventory
    STA cooldown
    STA zp_player_jump_held
    STA zp_player_air_jumps
    STA redraw_tile
    LDA #STARTING_ABILITIES
    STA zp_abilities
    LDA #1
    STA zp_player_facing
    LDA #LO(PLAYER_START_X)
    STA zp_player_x
    LDA #HI(PLAYER_START_X)
    STA zp_player_x + 1
    LDA #LO(PLAYER_START_Y)
    STA zp_player_y
    LDA #HI(PLAYER_START_Y)
    STA zp_player_y + 1
    JSR player_focus_and_frame
    LDA #LO(SCREEN_START)
    STA zp_screen_start
    LDA #HI(SCREEN_START)
    STA zp_screen_start + 1
    JSR call_world_reset
    JSR setup_screen
    JSR call_render_clear
    JSR plan_camera             \ The focus is outside the view, so redraw
    JSR apply_plan
    JSR set_crtc_start
    JSR draw_sprite
    LDA #BOOT_READY
    STA zp_boot_status
    \ Fall through into the main loop
}

.main_loop
    INC zp_frame
    LDA #19                     \ Wait for vertical sync
    JSR OSBYTE
    \ After vertical sync, staying ahead of the beam: the new start address;
    \ the new columns' rows above the sprite, which the beam reaches first;
    \ the sprite (well inside the view, so clear of the new columns), which
    \ the beam reaches next; then the rest of the new columns.
    JSR set_crtc_start
    JSR sprite_split_row
    LDA #0
    LDX zp_split_row
    JSR draw_column_rows
    JSR restore_sprite
    JSR redraw_queued_tile
    JSR draw_sprite
    LDA #VIEW_ROWS
    SEC
    SBC zp_split_row
    TAX
    LDA zp_split_row
    JSR draw_column_rows
    LDA #0
    STA zp_columns_width
.frame_shown                    \ The screen now shows the camera's view
    JSR read_input
    JSR update_player
    JSR player_action
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
    JSR read_key
    LDX #INKEY_L
    LDA #INPUT_ACTION
    JSR read_key
    LDX #INKEY_SPACE
    LDA #INPUT_PLACE
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
\ Camera: modelled exactly by tools/stratagem/camera.py. Pure, using only
\ zero page, so it can be tested in py65.

\ Ease the lead towards the focus's direction of travel, zp_direction, then
\ decide where the camera goes next: set zp_camera_x/y, and either
\ zp_plan_dx/dy, the movement to apply at the next flip, or zp_redraw.
.plan_camera
{
    LDA #0
    LDX zp_direction
    BEQ target_set
    LDA #LEAD_MAX
    CPX #1
    BEQ target_set
    LDA #&100 - LEAD_MAX
.target_set
    STA zp_temp
    LDA zp_lead
    SEC
    SBC zp_temp                 \ lead - target, small enough not to overflow
    BEQ lead_done
    BMI increase_lead
    DEC zp_lead
    JMP lead_done
.increase_lead
    INC zp_lead
.lead_done
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
\ bring the tile cache up to date, draw the new row (if any) into the
\ hidden row, and plan the new columns (if any) to be drawn at the flip.
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
    JSR update_tile_cache
    LDA zp_plan_dy
    BEQ no_row
    JSR draw_new_row
.no_row
    LDA zp_plan_dx
    BEQ no_columns
    JMP plan_new_columns
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

\ Set view_left/right/top/bottom to the tiles the view at the camera
\ shows.
.view_tiles
{
    LDA zp_camera_x + 1         \ Left: camera_x >> 2
    STA zp_temp
    LDA zp_camera_x
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    STA view_left
    CLC                         \ Right: (camera_x + VIEW_COLUMNS - 1) >> 2
    LDA zp_camera_x
    ADC #VIEW_COLUMNS - 1
    STA zp_temp
    LDA zp_camera_x + 1
    ADC #0
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LDA zp_temp
    STA view_right
    LDA zp_camera_y + 1         \ Top: camera_y >> 1
    LSR A
    LDA zp_camera_y
    ROR A
    STA view_top
    CLC                         \ Bottom: (camera_y + VIEW_ROWS - 1) >> 1
    LDA zp_camera_y
    ADC #VIEW_ROWS - 1
    STA zp_temp
    LDA zp_camera_y + 1
    ADC #0
    LSR A
    LDA zp_temp
    ROR A
    STA view_bottom
    RTS
}

\ Bring the tile cache up to date for the view at the camera, which has
\ moved by at most a tile each way: fill any new tile columns, then any new
\ tile rows (across the new columns too, so the corner is filled).
.update_tile_cache
{
    JSR view_tiles
    LDA view_bottom          \ Columns are filled over the view's rows
    SEC
    SBC view_top
    STA zp_temp + 1
    INC zp_temp + 1             \ Tiles in a column
.right_loop
    LDA cached_right
    CMP view_right
    BCS right_done              \ Only ever expand: cached_right >= view_right
    INC cached_right
    LDA cached_right
    JSR fill_tile_column
    JMP right_loop
.right_done
.left_loop
    LDA view_left
    CMP cached_left
    BCS left_done               \ view_left >= cached_left
    DEC cached_left
    LDA cached_left
    JSR fill_tile_column
    JMP left_loop
.left_done
    LDA view_right           \ Rows are filled over the view's columns
    SEC
    SBC view_left
    STA zp_temp + 1
    INC zp_temp + 1             \ Tiles in a row
.down_loop
    LDA cached_bottom
    CMP view_bottom
    BCS down_done               \ cached_bottom >= view_bottom
    INC cached_bottom
    LDA cached_bottom
    JSR fill_tile_row
    JMP down_loop
.down_done
.up_loop
    LDA view_top
    CMP cached_top
    BCS up_done                 \ view_top >= cached_top
    DEC cached_top
    LDA cached_top
    JSR fill_tile_row
    JMP up_loop
.up_done
    \ The cache now holds exactly the view's tiles.
    LDA view_left
    STA cached_left
    LDA view_right
    STA cached_right
    LDA view_top
    STA cached_top
    LDA view_bottom
    STA cached_bottom
    RTS
}

\ Fill the cache for tile column A, zp_temp + 1 tiles from the view's top.
.fill_tile_column
{
    STA zp_fill_x
    LDA view_top
    STA zp_fill_y
    LDA #&FF
    BNE fill                    \ Always branches
}

\ Fill the cache for tile row A, zp_temp + 1 tiles from the view's left.
.fill_tile_row
{
    STA zp_fill_y
    LDA view_left
    STA zp_fill_x
    LDA #0
}

.fill
{
    STA zp_fill_down
    LDA zp_temp + 1
    STA zp_fill_count
    JMP call_fill_cache
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

\ Fill the tile cache for the view at the camera, and draw the whole view, a
\ row at a time.
.redraw_view
{
    LDA #0
    STA zp_sprite_drawn         \ The sprite is drawn over
    STA zp_columns_width
    JSR view_tiles
    LDA view_right
    SEC
    SBC view_left
    STA zp_temp + 1
    INC zp_temp + 1             \ Tiles in a row
    LDA view_top
    STA cached_top
.fill_loop
    LDA cached_top
    JSR fill_tile_row
    LDA cached_top
    INC cached_top
    CMP view_bottom
    BNE fill_loop
    LDA view_left
    STA cached_left
    LDA view_right
    STA cached_right
    LDA view_top
    STA cached_top
    LDA view_bottom
    STA cached_bottom

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

\ ---------------------------------------------------------------------------
\ Data

INCLUDE "asm/player.asm"
INCLUDE "asm/actions.asm"

.main_end

SAVE "MAIN", main_start, main_end
