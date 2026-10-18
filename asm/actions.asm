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
    JSR held_directions         \ Diagonally?
    LDA diagonal_dx
    BEQ straight
    LDA diagonal_dy
    BEQ straight
    JSR diagonal
    BCC diagonal_found
.exit
    RTS
.diagonal_found
    LDA ramp_shape
    BEQ near
    \ Cut the step back to the ramp.
    JSR target_tile
    STA action_tile
    LDA target_shape
    AND #SHAPE_BITS
    TAX
    LDA ramp_shape
    CMP #SHAPE_RAMP_TOP_LEFT
    BNE right_ramp
    LDA cut_ramp_top_left,X
    JMP result
.right_ramp
    LDA cut_ramp_top_right,X
    JMP result
.near
    JSR near_side
    JMP erode
.straight
    LDA #0                      \ Aim for something diggable
    STA want
    JSR aim
    BCS exit
    JSR dig_direction
.erode
    \ Erode it from dig_side by its material's quarters.
    JSR target_tile
    STA action_tile             \ The material, unless nothing is left
    TAX
    LDA material_quarters,X
    CMP #QUARTERS
    BCS nothing_left
    TAY                         \ 1 or 2 quarters
    LDA target_shape            \ Index dig_side * MAX_SHAPES + shape
    AND #SHAPE_BITS
    STA zp_temp
    LDA dig_side
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    ORA zp_temp
    TAX
    LDA dig_1,X
    CPY #1
    BEQ result
    LDA dig_2,X
.result
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
.done
    RTS
}

\ Set dig_side to the side of the tile at target_x/y nearest the player,
\ digging diagonally: the top of a tile wholly below the feet, the bottom of
\ one wholly above the head, otherwise the side towards the player.
.near_side
{
    LDA #0                      \ The tile's top, y * 16
    STA zp_temp + 1
    LDA target_y
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    STA zp_temp
    LDX #FROM_TOP               \ top >= ground: wholly below the feet
    CMP ground
    LDA zp_temp + 1
    SBC ground + 1
    BCS set
    CLC                         \ top + 16 <= py: wholly above the head
    LDA zp_temp
    ADC #TILE_HEIGHT
    STA zp_temp
    LDA zp_temp + 1
    ADC #0
    STA zp_temp + 1
    LDX #FROM_BOTTOM
    LDA zp_box_y
    CMP zp_temp
    LDA zp_box_y + 1
    SBC zp_temp + 1
    BCS set
    LDX #FROM_LEFT
    LDA diagonal_dx
    BPL set
    LDX #FROM_RIGHT
.set
    STX dig_side
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

\ Set diagonal_dx and diagonal_dy to the directions held: -1, 0 or 1.
.held_directions
{
    LDX #0
    LDA zp_input
    AND #INPUT_LEFT OR INPUT_RIGHT
    CMP #INPUT_RIGHT
    BNE not_right
    INX
.not_right
    CMP #INPUT_LEFT
    BNE not_left
    DEX
.not_left
    STX diagonal_dx
    LDX #0
    LDA zp_input
    AND #INPUT_UP OR INPUT_DOWN
    CMP #INPUT_DOWN
    BNE not_down
    INX
.not_down
    CMP #INPUT_UP
    BNE not_up
    DEX
.not_up
    STX diagonal_dy
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
    BNE room_above
    SEC
    RTS
.room_above
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
    LDA #&FF                    \ None found yet
    STA best_row
    LDA #0
    STA best_left
.row_loop
    JSR wanted_here
    BCS next_row
    LDA want                    \ Placing: the lowest
    BNE found
    LDA target_shape            \ Digging: the one with the most left
    AND #SHAPE_BITS
    TAX
    LDA shape_solid_count,X
    CMP best_left
    BCC next_row
    BEQ next_row
    STA best_left
    LDA target_y
    STA best_row
.next_row
    JSR head_row
    CMP target_y
    BEQ rows_done
    DEC target_y
    JMP row_loop
.rows_done
    LDA best_row
    CMP #&FF
    BEQ none
    STA target_y
    CLC
    RTS
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

\ Choose where digging diagonally works next, by diagonal_dx and diagonal_dy
\ (see diagonal in tools/stratagem/actions.py): at target_x/y, either the step
\ to cut back to a ramp (ramp_shape non-zero) or a tile to erode (ramp_shape
\ zero); or none, with carry set. The path of a one-tile diagonal step going
\ down is in two parts, across at the player's height (part0), then a tile
\ down (part1); going up, a tile up (part0). It is worked column by column,
\ nearest the player first: going down, in each column, across, then the
\ step (the floor under the leading edge), then down; going up, the step
\ (the tile ahead at the feet), then up.
.diagonal
{
    JSR player_pixels           \ zp_box_x/y = px, py
    CLC                         \ ground = py + PLAYER_HEIGHT
    LDA zp_box_y
    ADC #PLAYER_HEIGHT
    STA ground
    LDA zp_box_y + 1
    ADC #0
    STA ground + 1
    \ The columns of the player's edges.
    LDA zp_box_x
    STA zp_temp
    LDA zp_box_x + 1
    JSR column_of
    STA left_column
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH - 1
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    JSR column_of
    STA right_column
    \ Part 0 spans px to px + 8 dx, plus the player's width.
    LDA zp_box_x
    STA part0_left
    LDA zp_box_x + 1
    STA part0_left + 1
    LDA diagonal_dx
    BPL part0_left_set
    SEC
    LDA part0_left
    SBC #TILE_WIDTH
    STA part0_left
    BCS part0_left_set
    DEC part0_left + 1
.part0_left_set
    CLC
    LDA part0_left
    ADC #TILE_WIDTH + PLAYER_WIDTH
    STA part0_right
    LDA part0_left + 1
    ADC #0
    STA part0_right + 1
    LDA #0                      \ No step unless one is found in the world
    STA step_valid
    LDA diagonal_dy
    BPL down
    JMP up
.down
    \ Part 0: across, from py to the ground.
    LDA zp_box_y
    STA part0_top
    LDA zp_box_y + 1
    STA part0_top + 1
    LDA ground
    STA part0_bottom
    LDA ground + 1
    STA part0_bottom + 1
    \ Part 1: a tile across, from py down to the tile boundary below
    \ ground + 16.
    LDA zp_box_x
    STA part1_left
    LDA zp_box_x + 1
    STA part1_left + 1
    LDA diagonal_dx
    BMI part1_leftwards
    CLC
    LDA part1_left
    ADC #TILE_WIDTH
    STA part1_left
    BCC part1_left_set
    INC part1_left + 1
    BNE part1_left_set          \ Always branches
.part1_leftwards
    SEC
    LDA part1_left
    SBC #TILE_WIDTH
    STA part1_left
    BCS part1_left_set
    DEC part1_left + 1
.part1_left_set
    CLC
    LDA part1_left
    ADC #PLAYER_WIDTH
    STA part1_right
    LDA part1_left + 1
    ADC #0
    STA part1_right + 1
    LDA zp_box_y
    STA part1_top
    LDA zp_box_y + 1
    STA part1_top + 1
    CLC
    LDA ground
    ADC #TILE_HEIGHT
    AND #&F0
    STA part1_bottom
    LDA ground + 1
    ADC #0
    STA part1_bottom + 1
    \ The step: the floor under the leading edge, at row ground >> 4, which
    \ part 1 never clears (nor the rest of the floor under the player).
    LDX right_column
    LDY #RAMP_DOWN_RIGHT
    LDA diagonal_dx
    BPL down_edge_set
    LDX left_column
    LDY #RAMP_DOWN_LEFT
.down_edge_set
    STX step_x
    STY ramp_shape
    LDA #&FF
    STA keep_row
    LDA ground
    STA zp_temp
    LDA ground + 1
    JSR row_of_checked
    BCS columns
    STA step_y
    STA keep_row
    LDA #&FF
    STA step_valid
    LDA left_column
    STA keep_first
    LDA right_column
    STA keep_last
    JMP columns
.up
    \ Part 0: a tile up, from py - 16 (or the top of the world) to ground - 16.
    SEC
    LDA ground
    SBC #TILE_HEIGHT
    STA part0_bottom
    LDA ground + 1
    SBC #0
    STA part0_bottom + 1
    BCS up_in_world
    SEC                         \ Wholly above the world
    RTS
.up_in_world
    SEC
    LDA zp_box_y
    SBC #TILE_HEIGHT
    STA part0_top
    LDA zp_box_y + 1
    SBC #0
    STA part0_top + 1
    BCS up_top_set
    LDA #0
    STA part0_top
    STA part0_top + 1
.up_top_set
    \ The step: the tile ahead at row (ground >> 4) - 1.
    LDX right_column
    INX
    LDY #RAMP_UP_RIGHT
    LDA diagonal_dx
    BPL up_ahead_set
    LDX left_column
    DEX
    LDY #RAMP_UP_LEFT
.up_ahead_set
    STX step_x
    STY ramp_shape
    LDA ground
    STA zp_temp
    LDA ground + 1
    JSR row_of
    SEC
    SBC #1
    BCC columns                 \ Above the top of the world
    STA step_y
    LDA #&FF
    STA step_valid
.columns
    \ The columns of part 0 (part 1 lies within them), within the world.
    LDA part0_left
    STA zp_temp
    LDA part0_left + 1
    JSR column_of
    STA first_column
    SEC
    LDA part0_right
    SBC #1
    STA zp_temp
    LDA part0_right + 1
    SBC #0
    CMP #HI(256 * TILE_WIDTH)
    BCC right_in_world
    LDA #HI(256 * TILE_WIDTH) - 1
    LDX #&FF
    STX zp_temp
.right_in_world
    JSR column_of
    STA last_column
    LDX first_column            \ From the player's side
    LDA diagonal_dx
    BPL column_start_set
    LDX last_column
.column_start_set
    STX scan_column
.column_loop
    LDA diagonal_dy
    BMI column_up
    LDA #SCAN_MOST_LEFT         \ Going down: across...
    JSR scan_part0
    BCC found_tile
    JSR try_step                \ ... the step...
    BCC found_step
    JSR scan_part1              \ ... then down
    BCC found_tile
    JMP next_column
.column_up
    JSR try_step                \ Going up: the step, then up
    BCC found_step
    LDA #SCAN_LOWEST
    JSR scan_part0
    BCC found_tile
.next_column
    LDA diagonal_dx
    BMI leftwards
    LDA scan_column
    CMP last_column
    BEQ none
    INC scan_column
    JMP column_loop
.leftwards
    LDA scan_column
    CMP first_column
    BEQ none
    DEC scan_column
    JMP column_loop
.none
    SEC
    RTS
.found_step
    CLC
    RTS
.found_tile
    LDA #0
    STA ramp_shape
    CLC
    RTS
}

SCAN_MOST_LEFT = 0              \ Of the tiles in the way, the one with most left
SCAN_LOWEST = 1                 \ The lowest in the way
SCAN_HIGHEST = 2                \ The highest in the way

\ Return carry clear, with target_x/y at the step, if the step is in
\ scan_column, in the world, diggable, and not already cut back as far as
\ ramp_shape.
.try_step
{
    LDA step_valid
    BEQ no
    LDA step_x
    CMP scan_column
    BNE no
    STA target_x
    LDA step_y
    STA target_y
    JSR target_tile
    TAX
    LDA material_quarters,X
    BEQ no
    LDA target_shape
    AND #SHAPE_BITS
    TAX
    LDA ramp_shape
    CMP #SHAPE_RAMP_TOP_LEFT
    BNE right_ramp
    LDA cut_ramp_top_left,X
    JMP cut
.right_ramp
    LDA cut_ramp_top_right,X
.cut
    CMP #&FE                    \ Already cut back as far
    BEQ no
    CLC
    RTS
.no
    SEC
    RTS
}

\ Scan scan_column within part 0 of the path, choosing by A (SCAN_*).
.scan_part0
{
    STA scan_mode
    LDA part0_left
    STA rect_left
    LDA part0_left + 1
    STA rect_left + 1
    LDA part0_right
    STA rect_right
    LDA part0_right + 1
    STA rect_right + 1
    LDA part0_top
    STA rect_top
    LDA part0_top + 1
    STA rect_top + 1
    LDA part0_bottom
    STA rect_bottom
    LDA part0_bottom + 1
    STA rect_bottom + 1
    LDA #0                      \ Part 0 keeps nothing
    STA scan_keeps
    JMP scan_column_in_rect
}

\ Scan scan_column within part 1 of the path (going down), highest first,
\ keeping the floor under the player.
.scan_part1
{
    LDA part1_left
    STA rect_left
    LDA part1_left + 1
    STA rect_left + 1
    LDA part1_right
    STA rect_right
    LDA part1_right + 1
    STA rect_right + 1
    LDA part1_top
    STA rect_top
    LDA part1_top + 1
    STA rect_top + 1
    LDA part1_bottom
    STA rect_bottom
    LDA part1_bottom + 1
    STA rect_bottom + 1
    LDA #SCAN_HIGHEST
    STA scan_mode
    LDA #&FF
    STA scan_keeps
    \ Fall through
}

\ Find, in column scan_column, a diggable tile with solid parts in the
\ rectangle rect_left to rect_right, rect_top to rect_bottom (pixels and
\ lines, right and bottom exclusive): by scan_mode, the one with the most
\ left (the lowest, of equals), the lowest, or the highest. Going up, skip
\ the step; if scan_keeps, skip the floor kept (keep_row, keep_first to
\ keep_last). Return it in target_x/y with carry clear, or carry set.
.scan_column_in_rect
{
    LDA scan_column
    STA target_x
    \ Rows: (bottom - 1) >> 4 up to top >> 4, within the world.
    SEC
    LDA rect_bottom
    SBC #1
    STA zp_temp
    LDA rect_bottom + 1
    SBC #0
    CMP #HI(256 * TILE_HEIGHT)
    BCC bottom_in_world
    LDA #HI(256 * TILE_HEIGHT) - 1
    LDX #&FF
    STX zp_temp
.bottom_in_world
    JSR row_of
    STA last_row
    LDA rect_top
    STA zp_temp
    LDA rect_top + 1
    JSR row_of
    STA first_row
    LDA #0
    STA best_left
    LDX last_row                \ From the bottom, unless the highest first
    LDA scan_mode
    CMP #SCAN_HIGHEST
    BNE row_start_set
    LDX first_row
.row_start_set
    STX target_y
.row_loop
    LDA diagonal_dy             \ Going up, skip the step
    BPL not_step
    LDA step_valid
    BEQ not_step
    LDA target_x
    CMP step_x
    BNE not_step
    LDA target_y
    CMP step_y
    BEQ next_row
.not_step
    LDA scan_keeps              \ Kept?
    BEQ not_kept
    LDA target_y
    CMP keep_row
    BNE not_kept
    LDA target_x
    CMP keep_first
    BCC not_kept
    LDA keep_last
    CMP target_x
    BCS next_row
.not_kept
    JSR target_tile
    TAX
    LDA material_quarters,X
    BEQ next_row
    JSR region_mask             \ The quarter-cells of the tile in the rectangle
    LDX target_shape
    LDA zp_hit_bits
    AND shape_mask_low,X
    STA zp_hit_bits
    LDA zp_hit_bits + 1
    AND shape_mask_high,X
    ORA zp_hit_bits
    BEQ next_row
    LDA scan_mode               \ In the way
    CMP #SCAN_MOST_LEFT
    BNE found                   \ The first, lowest or highest
    LDA shape_solid_count,X
    CMP best_left
    BCC next_row
    BEQ next_row
    STA best_left
    LDA target_y
    STA best_row
.next_row
    LDA scan_mode
    CMP #SCAN_HIGHEST
    BEQ downwards
    LDA target_y
    CMP first_row
    BEQ rows_done
    DEC target_y
    JMP row_loop
.downwards
    LDA target_y
    CMP last_row
    BEQ rows_done
    INC target_y
    JMP row_loop
.rows_done
    LDA best_left
    BEQ none
    LDA best_row
    STA target_y
.found
    CLC
    RTS
.none
    SEC
    RTS
}

\ Return in A the tile row of the line at A (high), zp_temp (low), with carry
\ set if it is outside the world.
.row_of_checked
{
    CMP #HI(256 * TILE_HEIGHT)
    BCS outside
    JSR row_of
    CLC
.outside
    RTS
}

\ Set zp_hit_bits to the quarter-cells of the tile at target_x/y within the
\ rectangle: columns from max(left - x * 8, 0) >> 1 to (min(right - x * 8,
\ 8) - 1) >> 1, rows likewise; none if the rectangle misses the tile.
\ Leaves target_shape as the shape number.
.region_mask
{
    LDA target_shape
    AND #SHAPE_BITS
    STA target_shape
    LDA #0
    STA zp_hit_bits
    STA zp_hit_bits + 1
    \ The tile's left, x * 8, in zp_temp.
    LDA #0
    STA zp_temp + 1
    LDA target_x
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    STA zp_temp
    SEC                         \ (left - x * 8) clamped to 0..8
    LDA rect_left
    SBC zp_temp
    TAX
    LDA rect_left + 1
    SBC zp_temp + 1
    JSR clamp_to_x
    STA span_first
    SEC                         \ (right - x * 8) clamped to 0..8
    LDA rect_right
    SBC zp_temp
    TAX
    LDA rect_right + 1
    SBC zp_temp + 1
    JSR clamp_to_x
    CMP span_first
    BEQ missed
    BCC missed
    SEC
    SBC #1
    LSR A
    STA zp_temp2
    LDA span_first
    LSR A
    ASL A                       \ Index first * 4 + last
    ASL A
    ORA zp_temp2
    TAY
    LDA column_span_low,Y
    STA zp_hit_bits
    LDA column_span_high,Y
    STA zp_hit_bits + 1
    \ The tile's top, y * 16, in zp_temp.
    LDA #0
    STA zp_temp + 1
    LDA target_y
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    STA zp_temp
    SEC                         \ (top - y * 16) clamped to 0..16
    LDA rect_top
    SBC zp_temp
    TAX
    LDA rect_top + 1
    SBC zp_temp + 1
    JSR clamp_to_y
    STA span_first
    SEC                         \ (bottom - y * 16) clamped to 0..16
    LDA rect_bottom
    SBC zp_temp
    TAX
    LDA rect_bottom + 1
    SBC zp_temp + 1
    JSR clamp_to_y
    CMP span_first
    BEQ missed
    BCC missed
    SEC
    SBC #1
    LSR A
    LSR A
    STA zp_temp2
    LDA span_first
    LSR A
    LSR A
    ASL A
    ASL A
    ORA zp_temp2
    TAY
    LDA zp_hit_bits
    AND row_span_low,Y
    STA zp_hit_bits
    LDA zp_hit_bits + 1
    AND row_span_high,Y
    STA zp_hit_bits + 1
    RTS
.missed
    LDA #0
    STA zp_hit_bits
    STA zp_hit_bits + 1
    RTS
}

\ Return in A the signed 16-bit value A (high), X (low) clamped to 0..8.
.clamp_to_x
{
    BMI zero
    BNE eight
    CPX #TILE_WIDTH + 1
    BCS eight
    TXA
    RTS
.eight
    LDA #TILE_WIDTH
    RTS
.zero
    LDA #0
    RTS
}

\ Return in A the signed 16-bit value A (high), X (low) clamped to 0..16.
.clamp_to_y
{
    BMI zero
    BNE sixteen
    CPX #TILE_HEIGHT + 1
    BCS sixteen
    TXA
    RTS
.sixteen
    LDA #TILE_HEIGHT
    RTS
.zero
    LDA #0
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

