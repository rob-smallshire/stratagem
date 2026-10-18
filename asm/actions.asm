\ Digging and placing, modelled exactly by tools/stratagem/actions.py.

ACTION_NONE  = 0
ACTION_DIG   = 1
ACTION_PLACE = 2
OVERLAP_OFFSET = 64             \ Keeps positions relative to a tile positive

\ Dig or place, by zp_input, after the player has moved.
.player_action
{
    LDA #ACTION_NONE
    STA action
    LDA cooldown
    BEQ ready
    DEC cooldown
    RTS
.ready
    LDA zp_input
    AND #INPUT_ACTION
    BEQ not_digging
    JMP dig
.not_digging
    LDA zp_input
    AND #INPUT_PLACE
    BEQ done
    JMP place
.done
    RTS
}

\ Dig the diggable tile aimed at, if any.
.dig
{
    LDA #0                      \ Aim for something diggable
    STA want
    JSR aim
    BCS done
    \ Erode it: by its material's quarters, from its own side if it is
    \ already shaped, otherwise from the side the player digs from.
    JSR target_tile
    TAX
    STX action_tile          \ The material, unless nothing is left
    LDA material_quarters,X
    CMP #QUARTERS
    BCS nothing_left
    TAY                         \ 1 or 2 quarters
    LDA target_shape
    AND #SHAPE_BITS
    BNE shaped
    JSR dig_direction           \ Whole: erode from the player's side
    LDX dig_side
    LDA whole_dig_1,X
    CPY #1
    BEQ dug
    LDA whole_dig_2,X
    BNE dug                     \ Always branches: something is left
.shaped
    TAX
    LDA shape_dig_1,X
    CPY #1
    BEQ eroded
    LDA shape_dig_2,X
.eroded
    CMP #&FF
    BNE dug
.nothing_left
    \ Nothing left: empty, showing its background.
    JSR target_background       \ A = BACKGROUND_SKY or 0
    STA zp_world_new_shape
    LDX #TILE_AIR
    ORA #0
    BEQ empty_set
    LDX #TILE_SKY
.empty_set
    STX action_tile
    JMP change
.dug
    STA zp_world_new_shape
    JSR target_background
    ORA zp_world_new_shape
    STA zp_world_new_shape
.change
    LDA action_tile
    JSR change_target
    BCS done                    \ The world is full
    LDA #DIG_FRAMES
    STA cooldown
    LDA #ACTION_DIG
    STA action
    LDA zp_world_new_shape      \ Only a tile dug away entirely goes into the
    AND #SHAPE_BITS             \ inventory: an empty material, so SHAPE_FULL
    BNE done
    LDX action_tile
    LDA material_passable,X
    BEQ done
    LDA inventory
    CMP #INVENTORY_MAX
    BCS done
    INC inventory
    RTS
.done
    RTS
}

\ Place a block in the empty tile aimed at, if any and if one is carried.
.place
{
    LDA inventory
    BEQ done
    LDA #&FF                    \ Aim for an empty tile
    STA want
    JSR aim
    BCS done
    JSR target_background
    STA zp_world_new_shape      \ SHAPE_FULL with the background
    LDA #PLACED_TILE
    JSR change_target
    BCS done
    DEC inventory
    LDA #PLACE_FRAMES
    STA cooldown
    LDA #ACTION_PLACE
    STA action
.done
    RTS
}

\ Set dig_side to the side of a tile a dig removes first: the side
\ the player is on.
.dig_direction
{
    LDX #FROM_TOP
    LDA zp_input
    AND #INPUT_DOWN
    BNE set
    LDX #FROM_BOTTOM
    LDA zp_input
    AND #INPUT_UP
    BNE set
    LDX #FROM_LEFT
    LDA zp_player_facing
    BPL set
    LDX #FROM_RIGHT
.set
    STX dig_side
    RTS
}

\ Choose the tile to dig or place at, target_x/y, by zp_input and what
\ want wants. Return with carry clear if there is one, set if not.
.aim
{
    JSR player_pixels           \ zp_box_x/y = px, py
    LDA zp_input
    AND #INPUT_DOWN
    BEQ not_down
    JSR middle_column           \ The line just below the feet
    CLC
    LDA zp_box_y
    ADC #PLAYER_HEIGHT
    STA zp_temp
    LDA zp_box_y + 1
    ADC #0
    JSR row_of
    STA target_y
    JMP wanted
.not_down
    LDA zp_input
    AND #INPUT_UP
    BEQ ahead
    LDA zp_box_y                \ The line just above the head, if any
    ORA zp_box_y + 1
    BEQ none
    JSR middle_column
    SEC
    LDA zp_box_y
    SBC #1
    STA zp_temp
    LDA zp_box_y + 1
    SBC #0
    JSR row_of
    STA target_y
    JMP wanted
.ahead
    \ The column of the pixel just ahead: (px + PLAYER_WIDTH) >> 3, or
    \ (px - 1) >> 3.
    LDA zp_player_facing
    BMI behind
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    JMP column_found
.behind
    SEC
    LDA zp_box_x
    SBC #1
    STA zp_temp
    LDA zp_box_x + 1
    SBC #0
.column_found
    JSR column_of
    STA target_x
    JSR feet_row                \ From the feet up to the head
    STA target_y
.row_loop
    JSR wanted_here
    BCC found
    JSR head_row
    CMP target_y
    BEQ none
    DEC target_y
    JMP row_loop
.wanted
    JSR wanted_here
    BCC found
.none
    SEC
.found
    RTS
}

\ Set target_x to the player's middle column: (px + PLAYER_WIDTH / 2) >> 3.
.middle_column
{
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH / 2
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    JSR column_of
    STA target_x
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

\ Return in A the material of the tile at target_x/y, from the tile cache,
\ and its shape in target_shape; point zp_ptr at its row in the cache
\ (of materials) with Y its column.
.target_tile
{
    LDA target_y
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache_shapes)
    STA zp_ptr + 1
    LDA target_y
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_ptr
    LDA target_x
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (zp_ptr),Y
    STA target_shape
    LDA zp_ptr + 1
    SEC
    SBC #HI(tile_cache_shapes - tile_cache)
    STA zp_ptr + 1
    LDA (zp_ptr),Y
    RTS
}

\ Return in A the background bits for the tile at target_x/y:
\ BACKGROUND_SKY if it is at or above its column's surface, otherwise 0.
.target_background
{
    LDX target_x
    LDA surface_heights,X
    CMP target_y
    LDA #0
    BCC done
    LDA #BACKGROUND_SKY
.done
    RTS
}

\ Return carry clear if the tile at target_x/y is what want wants:
\ something diggable, or an empty tile clear of the player.
.wanted_here
{
    JSR target_tile
    TAX
    LDA want
    BNE want_empty
    LDA material_quarters,X
    BNE yes
.no
    SEC
    RTS
.want_empty
    LDA material_empty,X
    BEQ no
    \ Clear of the player: not (px - x * 8 in -5..7 and py - y * 16 in
    \ -23..15), working with OVERLAP_OFFSET added.
    LDA target_x
    ASL A
    ASL A
    ASL A
    STA zp_temp
    LDA zp_box_x
    SEC
    SBC zp_temp
    CLC
    ADC #OVERLAP_OFFSET
    CMP #OVERLAP_OFFSET + TILE_WIDTH
    BCS yes
    CMP #OVERLAP_OFFSET - PLAYER_WIDTH + 1
    BCC yes
    LDA target_y
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_temp
    LDA zp_box_y
    SEC
    SBC zp_temp
    CLC
    ADC #OVERLAP_OFFSET
    CMP #OVERLAP_OFFSET + TILE_HEIGHT
    BCS yes
    CMP #OVERLAP_OFFSET - PLAYER_HEIGHT + 1
    BCC yes
    SEC                         \ It would overlap the player
    RTS
.yes
    CLC
    RTS
}

\ Change the tile at target_x/y to material A and shape zp_world_new_shape
\ in the world and the tile cache, and
\ queue it to be redrawn on the screen. (The screen may still show the
\ player's sprite where it was before this frame's move, over the tile, so
\ the tile is redrawn at the next flip, between removing the sprite and
\ drawing it again.) Return with carry set if the world has no room for it.
.change_target
{
    PHA
    LDX target_x
    LDY target_y
    JSR call_set_tile
    PLA
    BCS done
    PHA
    JSR target_tile             \ Points zp_ptr at the row of materials
    PLA
    STA (zp_ptr),Y
    LDA zp_ptr + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA zp_ptr + 1
    LDA zp_world_new_shape
    STA (zp_ptr),Y
    LDA target_x
    STA redraw_tile_x
    LDA target_y
    STA redraw_tile_y
    LDA #&FF
    STA redraw_tile
    CLC
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

