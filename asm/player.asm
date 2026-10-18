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
    \ Jump, and gravity.
    LDA zp_input
    AND #INPUT_UP
    BEQ no_jump
    LDA zp_player_on_ground
    BEQ no_jump
    LDA #&100 - JUMP_SPEED
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
    JSR box_free
    BCS blocked
    LDA zp_new_x
    STA zp_player_x
    LDA zp_new_x + 1
    STA zp_player_x + 1
    RTS
.blocked
    \ Climb a step: if on the ground and there is room a tile higher.
    LDA zp_player_on_ground
    BEQ stop
    LDA zp_box_y + 1
    BNE room_above
    LDA zp_box_y
    CMP #TILE_HEIGHT
    BCC stop
.room_above
    SEC
    LDA zp_box_y
    SBC #TILE_HEIGHT
    STA zp_box_y
    LDA zp_box_y + 1
    SBC #0
    STA zp_box_y + 1
    JSR box_free
    BCS stop_from_climb
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
.stop_from_climb
    CLC                         \ Put zp_box_y back (it is not used again,
    LDA zp_box_y                \ but keep it meaningful)
    ADC #TILE_HEIGHT
    STA zp_box_y
    BCC stop
    INC zp_box_y + 1
.stop
    \ Stop flush against the tile in the way.
    LDA zp_player_vx
    BMI stop_left
    CLC                         \ Right: x = (edge * 8 - PLAYER_WIDTH) * 16,
    LDA zp_box_x                \ edge = (new_px + PLAYER_WIDTH - 1) >> 3
    ADC #PLAYER_WIDTH - 1
    STA zp_player_x
    LDA zp_box_x + 1
    ADC #0
    STA zp_player_x + 1
    LDA zp_player_x
    AND #&F8
    SEC
    SBC #PLAYER_WIDTH
    STA zp_player_x
    LDA zp_player_x + 1
    SBC #0
    STA zp_player_x + 1
    JMP stopped
.stop_left
    LDA zp_box_x                \ Left: x = ((new_px >> 3) + 1) * 8 * 16
    AND #&F8
    CLC
    ADC #TILE_WIDTH
    STA zp_player_x
    LDA zp_box_x + 1
    ADC #0
    STA zp_player_x + 1
.stopped
    LDX #zp_player_x
    JSR times_sixteen
    LDA #0
    STA zp_player_vx
    RTS
}

.move_vertically
{
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
    JSR box_free
    BCS blocked
    LDA zp_new_y
    STA zp_player_y
    LDA zp_new_y + 1
    STA zp_player_y + 1
    RTS
.blocked
    LDA zp_player_vy
    BEQ up
    BMI up
    \ Down: land, y = (edge * 16 - PLAYER_HEIGHT) * 16,
    \ edge = (new_py + PLAYER_HEIGHT - 1) >> 4
    CLC
    LDA zp_box_y
    ADC #PLAYER_HEIGHT - 1
    STA zp_player_y
    LDA zp_box_y + 1
    ADC #0
    STA zp_player_y + 1
    LDA zp_player_y
    AND #&F0
    SEC
    SBC #PLAYER_HEIGHT
    STA zp_player_y
    LDA zp_player_y + 1
    SBC #0
    STA zp_player_y + 1
    LDA #&FF
    STA zp_player_on_ground
    BNE stopped
.up
    LDA zp_box_y                \ Up: y = ((new_py >> 4) + 1) * 16 * 16
    AND #&F0
    CLC
    ADC #TILE_HEIGHT
    STA zp_player_y
    LDA zp_box_y + 1
    ADC #0
    STA zp_player_y + 1
.stopped
    LDX #zp_player_y
    JSR times_sixteen
    LDA #0
    STA zp_player_vy
    RTS
}

\ Return carry clear if a player box at (zp_box_x, zp_box_y), in pixels and
\ lines, overlaps only passable tiles, as the tile cache has them; carry set
\ if not.
.box_free
{
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
    LDA (zp_ptr),Y
    TAX
    LDA tile_passable,X
    BEQ solid
    LDA zp_box_column
    INC zp_box_column
    CMP zp_box_right
    BNE column_loop
    LDA zp_box_row
    INC zp_box_row
    CMP zp_box_bottom
    BNE row_loop
    CLC
    RTS
.solid
    SEC
    RTS
}

\ Non-zero for each tile a body can pass through.
.tile_passable
    TILE_PASSABLE
