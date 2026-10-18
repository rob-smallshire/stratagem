\ Digging and placing, modelled exactly by tools/stratagem/actions.py.

ACTION_NONE  = 0
ACTION_DIG   = 1
ACTION_PLACE = 2

\ Dig or place, by zp_input, after the player has moved.
.player_action
{
    LDA #ACTION_NONE
    STA zp_action
    LDA zp_cooldown
    BEQ ready
    DEC zp_cooldown
    RTS
.ready
    LDA zp_input
    AND #INPUT_ACTION
    BEQ try_place
    LDA #0                      \ Aim for something diggable
    STA zp_want
    JSR aim
    BCS done
    JSR target_tile
    TAX
    LDA dig_frames,X
    STA zp_action_frames
    LDA #TILE_AIR
    JSR change_target
    BCS done                    \ The world is full
    LDA zp_action_frames
    STA zp_cooldown
    LDA #ACTION_DIG
    STA zp_action
    LDA zp_inventory
    CMP #INVENTORY_MAX
    BCS done
    INC zp_inventory
    RTS
.try_place
    LDA zp_input
    AND #INPUT_PLACE
    BEQ done
    LDA zp_inventory
    BEQ done
    LDA #&FF                    \ Aim for an empty tile
    STA zp_want
    JSR aim
    BCS done
    LDA #PLACED_TILE
    JSR change_target
    BCS done
    DEC zp_inventory
    LDA #PLACE_FRAMES
    STA zp_cooldown
    LDA #ACTION_PLACE
    STA zp_action
.done
    RTS
}

\ Choose the tile to dig or place at, zp_target_x/y, by zp_input and what
\ zp_want wants. Return with carry clear if there is one, set if not.
.aim
{
    JSR player_pixels           \ zp_box_x/y = px, py
    LDA zp_input
    AND #INPUT_DOWN
    BEQ not_down
    JSR middle_column           \ Below the feet
    JSR feet_row
    CLC
    ADC #1
    STA zp_target_y
    JMP wanted
.not_down
    LDA zp_input
    AND #INPUT_UP
    BEQ ahead
    LDA zp_box_y + 1            \ Above the head, if not at the top
    BNE room_above
    LDA zp_box_y
    CMP #TILE_HEIGHT
    BCC none
.room_above
    JSR middle_column
    JSR head_row
    SEC
    SBC #1
    STA zp_target_y
    JMP wanted
.ahead
    \ The column ahead: ((px + PLAYER_WIDTH - 1) >> 3) + 1, or (px >> 3) - 1.
    LDA zp_player_facing
    BMI behind
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH - 1
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    JSR column_of
    CLC
    ADC #1
    JMP column_set
.behind
    LDA zp_box_x
    STA zp_temp
    LDA zp_box_x + 1
    JSR column_of
    SEC
    SBC #1
.column_set
    STA zp_target_x
    JSR feet_row                \ From the feet up to the head
    STA zp_target_y
.row_loop
    JSR wanted_here
    BCC found
    JSR head_row
    CMP zp_target_y
    BEQ none
    DEC zp_target_y
    JMP row_loop
.wanted
    JSR wanted_here
    BCC found
.none
    SEC
.found
    RTS
}

\ Set zp_target_x to the player's middle column: (px + PLAYER_WIDTH / 2) >> 3.
.middle_column
{
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH / 2
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    JSR column_of
    STA zp_target_x
    RTS
}

\ Return in A the tile column of the pixel at A (high), zp_temp (low).
.column_of
{
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LDA zp_temp
    RTS
}

\ Return in A the tile row of the player's feet: (py + PLAYER_HEIGHT - 1) >> 4.
.feet_row
{
    CLC
    LDA zp_box_y
    ADC #PLAYER_HEIGHT - 1
    STA zp_temp
    LDA zp_box_y + 1
    ADC #0
    JMP row_of
}

\ Return in A the tile row of the player's head: py >> 4.
.head_row
{
    LDA zp_box_y
    STA zp_temp
    LDA zp_box_y + 1
    \ Fall through
}

\ Return in A the tile row of the line at A (high), zp_temp (low).
.row_of
{
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LDA zp_temp
    RTS
}

\ Return in A the tile at zp_target_x/y, from the tile cache, and point
\ zp_ptr at its row in the cache with Y its column.
.target_tile
{
    LDA zp_target_y
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA zp_ptr + 1
    LDA zp_target_y
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_ptr
    LDA zp_target_x
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (zp_ptr),Y
    RTS
}

\ Return carry clear if the tile at zp_target_x/y is what zp_want wants.
.wanted_here
{
    JSR target_tile
    TAX
    LDA zp_want
    BNE want_empty
    LDA dig_frames,X
    BNE yes
    SEC
    RTS
.want_empty
    LDA tile_empty,X
    BNE yes
    SEC
    RTS
.yes
    CLC
    RTS
}

\ Change the tile at zp_target_x/y to A in the world, the tile cache and on
\ the screen. Return with carry set if the world has no room for it.
.change_target
{
    PHA
    LDX zp_target_x
    LDY zp_target_y
    JSR call_set_tile
    PLA
    BCS done
    PHA
    JSR target_tile
    PLA
    STA (zp_ptr),Y
    JSR redraw_target
    CLC
.done
    RTS
}

\ Redraw the visible cells of the tile at zp_target_x/y: two cell rows of up
\ to four cells.
.redraw_target
{
    \ Column of its first cell in the view: 4 * x - camera_x, signed.
    LDA #0
    STA zp_temp + 1
    LDA zp_target_x
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
    LDA zp_target_y             \ View row = 2 * y + half - camera_y
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

\ For each tile, its dig cooldown in frames, or 0 if it can't be dug.
.dig_frames
    DIG_FRAMES

\ Non-zero for each tile that can be placed into.
.tile_empty
    TILE_EMPTY
