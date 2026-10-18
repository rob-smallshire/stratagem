\ The player: movement, collisions and animation, modelled exactly by
\ tools/stratagem/player.py and sprites.py. Pure: it reads only zero page,
\ its own tables and the tile cache, so it can be tested in py65.

\ Move the player by zp_input, then set the camera focus and direction and
\ the sprite frame.
.update_player
{
    \ Direction held, and facing.
    LDA zp_input
    AND #INPUT_LEFT OR INPUT_RIGHT
    LDX #1
    CMP #INPUT_RIGHT
    BEQ direction_set
    LDX #&FF
    CMP #INPUT_LEFT
    BEQ direction_set
    LDX #0
.direction_set
    STX zp_direction
    TXA
    BEQ facing_kept
    STA zp_player_facing
.facing_kept
    \ Ease vx towards direction * WALK_SPEED.
    LDA #0
    CPX #0
    BEQ target_set
    LDA #WALK_SPEED
    CPX #1
    BEQ target_set
    LDA #&100 - WALK_SPEED
.target_set
    STA zp_temp                 \ Target
    LDX #AIR_ACCELERATION
    LDA zp_player_on_ground
    BEQ acceleration_set
    LDX #GROUND_ACCELERATION
.acceleration_set
    STX zp_temp + 1
    LDA zp_player_vx
    SEC
    SBC zp_temp                 \ vx - target: small, no overflow
    BEQ vx_done
    BMI below_target
    CMP zp_temp + 1             \ Above: down by the acceleration, not past
    BCC reach_target
    BEQ reach_target
    LDA zp_player_vx
    SEC
    SBC zp_temp + 1
    STA zp_player_vx
    JMP vx_done
.below_target
    EOR #&FF                    \ target - vx
    CLC
    ADC #1
    CMP zp_temp + 1
    BCC reach_target
    BEQ reach_target
    LDA zp_player_vx
    CLC
    ADC zp_temp + 1
    STA zp_player_vx
    JMP vx_done
.reach_target
    LDA zp_temp
    STA zp_player_vx
.vx_done
    \ Jump from the ground, or again in the air with a fresh press of UP; but
    \ while digging, UP aims instead.
    JSR up_held
    BEQ no_jump
    LDA zp_player_on_ground
    BEQ in_the_air
    LDA #&100 - JUMP_SPEED
    STA zp_player_vy
    JMP no_jump
.in_the_air
    LDA zp_player_jump_held
    BNE no_jump
    LDA zp_player_air_jumps
    BEQ no_jump
    DEC zp_player_air_jumps
    LDA #&100 - AIR_JUMP_SPEED
    STA zp_player_vy
.no_jump
    LDA zp_player_vy
    CLC
    ADC #GRAVITY
    BMI vy_set                  \ Still rising
    CMP #MAX_FALL + 1
    BCC vy_set
    LDA #MAX_FALL
.vy_set
    STA zp_player_vy

    JSR move_horizontally
    JSR move_vertically
    \ Landing restores the air jumps the player's abilities allow.
    LDA zp_player_on_ground
    BEQ air_jumps_kept
    LDA zp_abilities
    AND #ABILITY_DOUBLE_JUMP
    BEQ air_jumps_set
    LDA #1
.air_jumps_set
    STA zp_player_air_jumps
.air_jumps_kept
    JSR up_held
    BEQ held_set
    LDA #&FF
.held_set
    STA zp_player_jump_held
    \ Fall through
}

\ Set the camera focus, (px + 2, py + 8), and the sprite frame.
.player_focus_and_frame
{
    JSR player_pixels           \ zp_box_x/y = px, py
    CLC
    LDA zp_box_x
    ADC #2
    STA zp_focus_x
    LDA zp_box_x + 1
    ADC #0
    STA zp_focus_x + 1
    CLC
    LDA zp_box_y
    ADC #8
    STA zp_focus_y
    LDA zp_box_y + 1
    ADC #0
    STA zp_focus_y + 1

    \ The sprite frame.
    LDA #JUMP
    LDX zp_player_on_ground
    BEQ pose_set
    LDA #STAND
    LDX zp_player_vx
    BEQ pose_set
    LDA zp_box_x
    LSR A
    LSR A
    AND #1
    CLC
    ADC #WALK1
.pose_set
    LDX zp_player_facing
    BPL frame_set
    CLC
    ADC #LEFT_FACING
.frame_set
    STA zp_player_frame
    RTS
}

\ Return Z clear if UP is held for jumping: held, and ACTION (digging) not.
.up_held
{
    LDA zp_input
    AND #INPUT_UP OR INPUT_ACTION
    CMP #INPUT_UP
    BEQ held
    LDA #0
    RTS
.held
    LDA #&FF
    RTS
}

\ Set zp_box_x/y to the player's position in pixels and lines.
.player_pixels
{
    LDA zp_player_x + 1
    STA zp_box_x + 1
    LDA zp_player_x
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    STA zp_box_x
    LDA zp_player_y + 1
    STA zp_box_y + 1
    LDA zp_player_y
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    STA zp_box_y
    RTS
}

\ Shift the 16-bit value at zero page X left four places: pixels or lines
\ to sixteenths.
.times_sixteen
{
    ASL 0,X
    ROL 1,X
    ASL 0,X
    ROL 1,X
    ASL 0,X
    ROL 1,X
    ASL 0,X
    ROL 1,X
    RTS
}

.move_horizontally
{
    LDA zp_player_vx
    BNE moving
    RTS
.moving
    \ new_x = x + vx
    LDX #0
    LDA zp_player_vx
    BPL positive
    DEX
.positive
    CLC
    ADC zp_player_x
    STA zp_new_x
    TXA
    ADC zp_player_x + 1
    STA zp_new_x + 1
    JSR player_pixels           \ zp_box_y = py
    LDA zp_new_x + 1            \ zp_box_x = new_x >> 4
    STA zp_box_x + 1
    LDA zp_new_x
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    STA zp_box_x
    JSR find_hits
    BCS blocked
    LDA zp_new_x
    STA zp_player_x
    LDA zp_new_x + 1
    STA zp_player_x + 1
    RTS
.blocked
    \ Where to stop, flush against the nearest solid part: x = (left - width)
    \ * 16 moving right, right * 16 moving left.
    LDA zp_player_vx
    BMI stop_left
    SEC
    LDA zp_hit_left
    SBC #PLAYER_WIDTH
    STA zp_stop
    LDA zp_hit_left + 1
    SBC #0
    STA zp_stop + 1
    JMP stop_set
.stop_left
    LDA zp_hit_right
    STA zp_stop
    LDA zp_hit_right + 1
    STA zp_stop + 1
.stop_set
    \ Climb a ledge: if on the ground, the ledge is at most a tile high (and
    \ no higher than the top of the world), and there is room above it; but
    \ not while digging downwards, when a ledge is something to dig into.
    LDA zp_player_on_ground
    BEQ stop
    LDA zp_input
    AND #INPUT_ACTION OR INPUT_DOWN
    CMP #INPUT_ACTION OR INPUT_DOWN
    BEQ stop
    SEC                         \ lift = py + PLAYER_HEIGHT - top
    LDA zp_box_y
    ADC #PLAYER_HEIGHT - 1
    STA zp_lift
    LDA zp_box_y + 1
    ADC #0
    STA zp_lift + 1
    SEC
    LDA zp_lift
    SBC zp_hit_top
    STA zp_lift
    LDA zp_lift + 1
    SBC zp_hit_top + 1
    BNE stop                    \ More than 255 lines
    LDA zp_lift
    CMP #TILE_HEIGHT + 1
    BCS stop
    LDA zp_box_y + 1            \ lift <= py
    BNE room_at_top
    LDA zp_box_y
    CMP zp_lift
    BCC stop
.room_at_top
    SEC                         \ Try the box at py - lift
    LDA zp_box_y
    SBC zp_lift
    STA zp_box_y
    LDA zp_box_y + 1
    SBC #0
    STA zp_box_y + 1
    JSR find_hits
    BCS stop
    LDA zp_new_x
    STA zp_player_x
    LDA zp_new_x + 1
    STA zp_player_x + 1
    LDA zp_box_y
    STA zp_player_y
    LDA zp_box_y + 1
    STA zp_player_y + 1
    LDX #zp_player_y
    JMP times_sixteen
.stop
    LDA zp_stop
    STA zp_player_x
    LDA zp_stop + 1
    STA zp_player_x + 1
    LDX #zp_player_x
    JSR times_sixteen
    LDA #0
    STA zp_player_vx
    RTS
}

.move_vertically
{
    LDA zp_player_on_ground
    STA zp_was_on_ground
    LDA #0
    STA zp_player_on_ground
    \ new_y = y + vy, not above the top of the world
    LDX #0
    LDA zp_player_vy
    BPL positive
    DEX
.positive
    CLC
    ADC zp_player_y
    STA zp_new_y
    TXA
    ADC zp_player_y + 1
    STA zp_new_y + 1
    BCS in_world                \ vy >= 0: no carry. vy < 0: carry unless
    LDA zp_player_vy            \ it went above the top
    BPL in_world
    LDA #0
    STA zp_new_y
    STA zp_new_y + 1
    STA zp_player_vy
.in_world
    JSR player_pixels           \ zp_box_x = px
    LDA zp_new_y + 1            \ zp_box_y = new_y >> 4
    STA zp_box_y + 1
    LDA zp_new_y
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    STA zp_box_y
    JSR find_hits
    BCS blocked
    \ Follow the ground down a small step, rather than fall off it.
    LDA zp_was_on_ground
    BEQ fall
    LDA zp_player_vy
    BEQ fall
    BMI fall
    JSR player_pixels           \ The box SNAP_DOWN lines below where it was
    CLC
    LDA zp_box_y
    ADC #SNAP_DOWN
    STA zp_box_y
    BCC snap_added
    INC zp_box_y + 1
.snap_added
    JSR find_hits
    BCS blocked
.fall
    LDA zp_new_y
    STA zp_player_y
    LDA zp_new_y + 1
    STA zp_player_y + 1
    RTS
.blocked
    LDA zp_player_vy
    BEQ up
    BMI up
    SEC                         \ Down: land, y = (top - height) * 16
    LDA zp_hit_top
    SBC #PLAYER_HEIGHT
    STA zp_player_y
    LDA zp_hit_top + 1
    SBC #0
    STA zp_player_y + 1
    LDA #&FF
    STA zp_player_on_ground
    BNE stopped
.up
    LDA zp_hit_bottom           \ Up: y = bottom * 16
    STA zp_player_y
    LDA zp_hit_bottom + 1
    STA zp_player_y + 1
.stopped
    LDX #zp_player_y
    JSR times_sixteen
    LDA #0
    STA zp_player_vy
    RTS
}

\ Find the solid parts of tiles, as the tile cache has them, that a player
\ box at (zp_box_x, zp_box_y), in pixels and lines, would overlap. Return
\ carry clear if none; otherwise carry set, with the least left and top and
\ the greatest right and bottom of them, in world pixels and lines, in
\ zp_hit_left, zp_hit_top, zp_hit_right and zp_hit_bottom.
.find_hits
{
    LDA #&FF                    \ Nothing hit yet: left and top at most,
    STA zp_hit_left             \ right and bottom at least
    STA zp_hit_left + 1
    STA zp_hit_top
    STA zp_hit_top + 1
    LDA #0
    STA zp_hit_right
    STA zp_hit_right + 1
    STA zp_hit_bottom
    STA zp_hit_bottom + 1
    STA zp_hit_any
    \ Tile columns zp_box_x >> 3 to (zp_box_x + PLAYER_WIDTH - 1) >> 3.
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH - 1
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LDA zp_temp
    STA zp_box_right
    \ Tile rows zp_box_y >> 4 to (zp_box_y + PLAYER_HEIGHT - 1) >> 4.
    CLC
    LDA zp_box_y
    ADC #PLAYER_HEIGHT - 1
    STA zp_temp
    LDA zp_box_y + 1
    ADC #0
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LDA zp_temp
    STA zp_box_bottom
    LDA zp_box_y + 1
    STA zp_temp
    LDA zp_box_y
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    STA zp_box_row
.row_loop
    \ zp_ptr = tile_cache + (row MOD 32) * 32
    LDA zp_box_row
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA zp_ptr + 1
    LDA zp_box_row
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_ptr
    LDA zp_ptr                  \ ... and the shapes
    STA zp_shape_ptr
    LDA zp_ptr + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA zp_shape_ptr + 1
    \ The box's top relative to the row, plus 24: box_y - row * 16 + 24.
    LDA zp_box_row
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_temp
    LDA zp_box_y
    SEC
    SBC zp_temp
    CLC
    ADC #24
    STA zp_hit_relative_y
    LDA zp_box_x + 1            \ First column: zp_box_x >> 3
    STA zp_temp
    LDA zp_box_x
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    STA zp_box_column
.column_loop
    LDA zp_box_column
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (zp_ptr),Y              \ The material
    TAX
    LDA material_passable,X
    BNE next_column
    LDA (zp_shape_ptr),Y        \ The shape
    AND #SHAPE_BITS
    TAX
    \ The quarter-cells the box overlaps, by its position relative to the
    \ tile, that are solid: box_columns[x + 8] AND box_rows[y + 24] AND mask.
    LDA zp_box_column
    ASL A
    ASL A
    ASL A
    STA zp_temp
    LDA zp_box_x
    SEC
    SBC zp_temp
    CLC
    ADC #8
    TAY
    LDA box_columns_low,Y
    AND shape_mask_low,X
    STA zp_hit_bits
    LDA box_columns_high,Y
    AND shape_mask_high,X
    STA zp_hit_bits + 1
    LDY zp_hit_relative_y
    LDA zp_hit_bits
    AND box_rows_low,Y
    STA zp_hit_bits
    LDA zp_hit_bits + 1
    AND box_rows_high,Y
    STA zp_hit_bits + 1
    ORA zp_hit_bits
    BEQ next_column
    JSR record_hit
.next_column
    LDA zp_box_column
    INC zp_box_column
    CMP zp_box_right
    BNE column_loop
    LDA zp_box_row
    INC zp_box_row
    CMP zp_box_bottom
    BEQ rows_done
    JMP row_loop
.rows_done
    LDA zp_hit_any              \ Carry set if anything was hit
    CMP #1
    RTS
}

\ Record the quarter-cells zp_hit_bits of the tile (zp_box_column, zp_box_row)
\ as hit: widen zp_hit_left/right/top/bottom to include them.
.record_hit
{
    LDA #1
    STA zp_hit_any
    \ Their columns: the OR of the mask's four rows (nibbles).
    LDA zp_hit_bits
    ORA zp_hit_bits + 1
    STA zp_temp
    LSR A
    LSR A
    LSR A
    LSR A
    ORA zp_temp
    AND #&0F
    TAY
    LDA lowest_bit,Y            \ Left and right, in pixels within the tile
    ASL A
    STA zp_rect_left
    LDA highest_bit,Y
    ASL A
    ADC #2                      \ Carry is clear
    STA zp_rect_right
    \ Their rows: which of the four nibbles are non-zero.
    LDY #0
    LDA zp_hit_bits
    AND #&0F
    BEQ no_row_0
    LDY #1
.no_row_0
    LDA zp_hit_bits
    AND #&F0
    BEQ no_row_1
    TYA
    ORA #2
    TAY
.no_row_1
    LDA zp_hit_bits + 1
    AND #&0F
    BEQ no_row_2
    TYA
    ORA #4
    TAY
.no_row_2
    LDA zp_hit_bits + 1
    AND #&F0
    BEQ no_row_3
    TYA
    ORA #8
    TAY
.no_row_3
    LDA lowest_bit,Y            \ Top and bottom, in lines within the tile
    ASL A
    ASL A
    STA zp_rect_top
    LDA highest_bit,Y
    ASL A
    ASL A
    ADC #4                      \ Carry is clear
    STA zp_rect_bottom
    \ Column * 8 and row * 16, 16 bits, in zp_temp and zp_temp2.
    LDA #0
    STA zp_temp + 1
    LDA zp_box_column
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    ASL A
    ROL zp_temp + 1
    STA zp_temp
    LDA #0
    STA zp_temp2 + 1
    LDA zp_box_row
    ASL A
    ROL zp_temp2 + 1
    ASL A
    ROL zp_temp2 + 1
    ASL A
    ROL zp_temp2 + 1
    ASL A
    ROL zp_temp2 + 1
    STA zp_temp2
    \ Left: keep the least.
    CLC
    LDA zp_temp
    ADC zp_rect_left
    TAY
    LDA zp_temp + 1
    ADC #0
    CMP zp_hit_left + 1
    BCC new_left
    BNE left_done
    CPY zp_hit_left
    BCS left_done
.new_left
    STY zp_hit_left
    STA zp_hit_left + 1
.left_done
    \ Right: keep the greatest.
    CLC
    LDA zp_temp
    ADC zp_rect_right
    TAY
    LDA zp_temp + 1
    ADC #0
    CMP zp_hit_right + 1
    BCC right_done
    BNE new_right
    CPY zp_hit_right
    BCC right_done
    BEQ right_done
.new_right
    STY zp_hit_right
    STA zp_hit_right + 1
.right_done
    \ Top: keep the least.
    CLC
    LDA zp_temp2
    ADC zp_rect_top
    TAY
    LDA zp_temp2 + 1
    ADC #0
    CMP zp_hit_top + 1
    BCC new_top
    BNE top_done
    CPY zp_hit_top
    BCS top_done
.new_top
    STY zp_hit_top
    STA zp_hit_top + 1
.top_done
    \ Bottom: keep the greatest.
    CLC
    LDA zp_temp2
    ADC zp_rect_bottom
    TAY
    LDA zp_temp2 + 1
    ADC #0
    CMP zp_hit_bottom + 1
    BCC bottom_done
    BNE new_bottom
    CPY zp_hit_bottom
    BCC bottom_done
    BEQ bottom_done
.new_bottom
    STY zp_hit_bottom
    STA zp_hit_bottom + 1
.bottom_done
    RTS
}

\ The properties of materials and shapes.
INCLUDE "build/generated/shapes.asm"
