\ Items thrown out into the world (tools/stratagem/items.py, which this
\ does exactly): what a felled tree drops. A trunk's part that breaks, dug
\ or fallen, throws out a piece of wood, sprayed upwards and to one side
\ (item_spray_vx, item_spray_vy, by a count of items thrown). An item flies
\ under gravity, bouncing off solid quarter-cells, until it comes to rest
\ (or for FLY_FRAMES at most); rests for REST_FRAMES; then flies to the
\ miner, through anything, faster each frame, and is his when it touches
\ him. So the miner sees how many there are, and then they are gone. At
\ most ITEM_MAX are out at once: more go straight into the inventory. The
\ packet carries those in view, for the host to draw as sprites
\ (items_emit).

ASSERT ITEM_MAX_FALL <= 4 * 16  \ A quarter-cell a frame, at most
ASSERT WOOD = KIND_WOOD AND ITEM_FRAME_COUNT = KIND_COUNT  \ Item kinds are the inventory's
ASSERT ITEM_OFFSET_X * 16 < 128

\ Material A broke at tile (X, Y): throw out what it drops, if anything.
.item_drop
{
    STX item_tx
    STY item_ty
    TAX
    LDA material_drops,X
    BMI done                    \ Nothing
    LDX item_count
    CPX #ITEM_MAX
    BCS full
    STA item_kind,X
    LDA item_tx                 \ x = (tx * 8 + ITEM_OFFSET_X) * 16
    LSR A
    STA item_x_high,X
    LDA #0
    ROR A
    ORA #ITEM_OFFSET_X * 16
    STA item_x_low,X
    LDA #LO(-ITEM_HEIGHT * 16)  \ y = ((ty + 1) * 16 - ITEM_HEIGHT) * 16
    STA item_y_low,X
    LDA item_ty
    STA item_y_high,X
    ASSERT ITEM_HEIGHT * 16 <= 256
    LDA item_thrown             \ Sprayed, by the count thrown
    AND #7
    TAY
    LDA item_spray_vx,Y
    STA item_vx,X
    LDA item_thrown
    AND #3
    TAY
    LDA item_spray_vy,Y
    STA item_vy,X
    LDA #FLYING
    STA item_state,X
    LDA #0
    STA item_timer,X
    INC item_thrown
    INC item_count
    JMP item_set_place
.done
    RTS
.full
    JMP inventory_gain          \ A is its kind
}

\ Set item X's pixel and top line from its position: px = x >> 4, top =
\ y >> 4. Preserves X.
.item_set_place
{
    LDA item_x_high,X
    STA zp_temp + 1
    LDA item_x_low,X
    JSR lines_of
    STA item_px_low,X
    LDA zp_temp + 1
    STA item_px_high,X
    LDA item_y_high,X
    STA zp_temp + 1
    LDA item_y_low,X
    JSR lines_of
    STA item_top_low,X
    LDA zp_temp + 1
    STA item_top_high,X
    RTS
}

\ Each item moves, by its state; one gathering that touches the miner is
\ his: the last takes its place, and moves in its turn.
.items_step
{
    LDA item_count
    BNE some
    RTS
.some
    JSR player_pixels           \ The miner's box: zp_box_x, zp_box_y
    LDA #0                      \ The tile cache's bounds, when wanted
    STA item_bounded
    LDX #0
.loop
    CPX item_count
    BNE more
    RTS
.more
    STX item_i
    LDA item_state,X
    CMP #RESTING
    BEQ rests
    BCS gathers
    JSR item_fly
    JMP moved
.rests
    DEC item_timer,X
    BNE moved
    JSR item_to_gather
    JMP moved
.gathers
    JSR item_gather
.moved
    LDX item_i
    LDA item_state,X
    CMP #GATHERING
    BNE next
    JSR item_touches
    BCS next
    LDA item_kind,X             \ His: the last takes its place
    JSR inventory_gain
    DEC item_count
    LDY item_count
    LDX item_i
    LDA item_x_low,Y
    STA item_x_low,X
    LDA item_x_high,Y
    STA item_x_high,X
    LDA item_y_low,Y
    STA item_y_low,X
    LDA item_y_high,Y
    STA item_y_high,X
    LDA item_vx,Y
    STA item_vx,X
    LDA item_vy,Y
    STA item_vy,X
    LDA item_state,Y
    STA item_state,X
    LDA item_timer,Y
    STA item_timer,X
    LDA item_kind,Y
    STA item_kind,X
    LDA item_px_low,Y
    STA item_px_low,X
    LDA item_px_high,Y
    STA item_px_high,X
    LDA item_top_low,Y
    STA item_top_low,X
    LDA item_top_high,Y
    STA item_top_high,X
    JMP loop
.next
    INX
    JMP loop
}
ASSERT FLYING = 0 AND RESTING = 1 AND GATHERING = 2

\ Item X (item_i) gathers: it stops, to fly to the miner. Preserves X.
.item_to_gather
{
    LDA #GATHERING
    STA item_state,X
    LDA #0
    STA item_vx,X
    STA item_vy,X
    STA item_timer,X
    RTS
}

\ Item item_i flies a frame (items.fly). Each pixel and line is worked out
\ once: item_new_px and item_new_top go into its place.
.item_fly
{
    LDX item_i
    LDA item_timer,X            \ Flown long enough: gathered
    CLC
    ADC #1
    CMP #FLY_FRAMES
    BCC flying
    JMP item_to_gather
.flying
    STA item_new_timer
    LDA item_vx,X               \ Across: x + vx
    STA item_new_vx
    JSR sign_of
    STA item_tmp
    LDA item_x_low,X
    CLC
    ADC item_vx,X
    STA item_new_x
    LDA item_x_high,X
    ADC item_tmp
    STA item_new_x + 1
    STA zp_temp + 1             \ ... and its pixel
    LDA item_new_x
    JSR lines_of
    STA item_new_px
    LDA zp_temp + 1
    STA item_new_px + 1
    LDA item_new_vx
    BEQ across_done
    LDA item_top_low,X          \ The middle line: top + ITEM_HEIGHT DIV 2
    CLC
    ADC #ITEM_HEIGHT DIV 2
    STA zp_temp2
    LDA item_top_high,X
    ADC #0
    STA zp_temp2 + 1
    LDA item_new_px             \ The edge moving: px, + ITEM_WIDTH - 1 if
    STA zp_temp                 \ moving right
    LDA item_new_px + 1
    STA zp_temp + 1
    LDA item_new_vx
    BMI edge_set
    LDA zp_temp
    CLC
    ADC #ITEM_WIDTH - 1
    STA zp_temp
    BCC edge_set
    INC zp_temp + 1
.edge_set
    JSR item_point_cached
    BCS across_cached
    JMP item_to_gather_i
.across_cached
    JSR solid_at
    BCC across_done
    LDX item_i                  \ Bounces back: x as it was, vx = -(vx >> 1)
    LDA item_x_low,X
    STA item_new_x
    LDA item_x_high,X
    STA item_new_x + 1
    LDA item_px_low,X
    STA item_new_px
    LDA item_px_high,X
    STA item_new_px + 1
    LDA item_new_vx
    CMP #&80
    ROR A
    EOR #&FF
    CLC
    ADC #1
    STA item_new_vx
.across_done
    LDX item_i                  \ Down: vy = min(vy + GRAVITY, ITEM_MAX_FALL)
    LDA item_vy,X
    CLC
    ADC #GRAVITY
    BMI vy_set                  \ (Still rising)
    CMP #ITEM_MAX_FALL
    BCC vy_set
    LDA #ITEM_MAX_FALL
.vy_set
    STA item_new_vy
    BNE moving
    JMP set_y                   \ Neither up nor down: y as it was
.moving
    JSR sign_of                 \ y + vy: carry clear here if it rose past 0
    STA item_tmp
    LDA item_y_low,X
    CLC
    ADC item_new_vy
    STA item_new_y
    LDA item_y_high,X
    ADC item_tmp
    STA item_new_y + 1
    ROR item_carry              \ (Bit 7: the carry)
    STA zp_temp + 1             \ ... and its top line
    LDA item_new_y
    JSR lines_of
    STA item_new_top
    LDA zp_temp + 1
    STA item_new_top + 1
    LDA item_new_px             \ The middle: px + ITEM_WIDTH DIV 2
    CLC
    ADC #ITEM_WIDTH DIV 2
    STA zp_temp
    LDA item_new_px + 1
    ADC #0
    STA zp_temp + 1
    LDA item_new_vy
    BPL falling
    JMP rising
.falling
    LDA item_new_top            \ Falling: the line under it, top +
    CLC                         \ ITEM_HEIGHT
    ADC #ITEM_HEIGHT
    STA zp_temp2
    LDA item_new_top + 1
    ADC #0
    STA zp_temp2 + 1
    JSR item_point_cached
    BCS below_cached
    JMP item_to_gather_i
.below_cached
    JSR solid_at
    BCS lands
    JMP set
.lands
    LDA zp_temp2                \ On the quarter-cell's top: top = (below AND
    AND #&FC                    \ NOT 3) - ITEM_HEIGHT, y = top << 4
    SEC
    SBC #ITEM_HEIGHT
    STA item_new_top
    STA item_new_y
    LDA zp_temp2 + 1
    SBC #0
    STA item_new_top + 1
    ASL item_new_y
    ROL A
    ASL item_new_y
    ROL A
    ASL item_new_y
    ROL A
    ASL item_new_y
    ROL A
    STA item_new_y + 1
    LDA item_new_vy
    CMP #BOUNCE_MIN
    BCS bounces
    LDA #0                      \ Too slow to bounce: it rests
    STA item_new_vx
    STA item_new_vy
    LDA #REST_FRAMES
    STA item_new_timer
    LDX item_i
    LDA #RESTING
    STA item_state,X
    JMP set
.bounces
    LSR A                       \ vy = -(vy >> 1), vx = vx >> 1
    EOR #&FF
    CLC
    ADC #1
    STA item_new_vy
    LDA item_new_vx
    CMP #&80
    ROR A
    STA item_new_vx
    JMP set
.rising
    BIT item_carry              \ Past the world's top: gathered
    BMI top_set
    JMP item_to_gather_i
.top_set
    LDA item_new_top
    STA zp_temp2
    LDA item_new_top + 1
    STA zp_temp2 + 1
    JSR item_point_cached
    BCS top_cached
    JMP item_to_gather_i
.top_cached
    JSR solid_at
    BCC set
    LDA #0                      \ It stops rising: y as it was
    STA item_new_vy
.set_y
    LDX item_i
    LDA item_y_low,X
    STA item_new_y
    LDA item_y_high,X
    STA item_new_y + 1
    LDA item_top_low,X
    STA item_new_top
    LDA item_top_high,X
    STA item_new_top + 1
.set
    LDX item_i
    LDA item_new_x
    STA item_x_low,X
    LDA item_new_x + 1
    STA item_x_high,X
    LDA item_new_y
    STA item_y_low,X
    LDA item_new_y + 1
    STA item_y_high,X
    LDA item_new_vx
    STA item_vx,X
    LDA item_new_vy
    STA item_vy,X
    LDA item_new_timer
    STA item_timer,X
    LDA item_new_px
    STA item_px_low,X
    LDA item_new_px + 1
    STA item_px_high,X
    LDA item_new_top
    STA item_top_low,X
    LDA item_new_top + 1
    STA item_top_high,X
    RTS
}

\ Item item_i gathers (from item_fly, which may have changed X).
.item_to_gather_i
{
    LDX item_i
    JMP item_to_gather
}

\ A's sign, extended: &FF if negative, else 0.
.sign_of
{
    ORA #0
    BMI negative
    LDA #0
    RTS
.negative
    LDA #&FF
    RTS
}

\ Item item_i flies a frame towards the middle of the miner's box,
\ (zp_box_x + (PLAYER_WIDTH - ITEM_WIDTH) DIV 2, zp_box_y + (PLAYER_HEIGHT -
\ ITEM_HEIGHT) DIV 2), faster by a pixel each frame, to GATHER_MAX
\ (items.gather).
.item_gather
{
    LDX item_i
    LDA item_vx,X               \ Its speed
    CMP #GATHER_MAX
    BCS speed_set
    ADC #1
    STA item_vx,X
.speed_set
    LDA item_px_low,X           \ Across
    STA item_tmp
    LDA item_px_high,X
    STA item_tmp + 1
    LDA zp_box_x
    CLC
    ADC #(PLAYER_WIDTH - ITEM_WIDTH) DIV 2
    STA zp_temp2
    LDA zp_box_x + 1
    ADC #0
    STA zp_temp2 + 1
    JSR item_towards
    LDA item_tmp                \ x = px << 4
    STA item_x_low,X
    LDA item_tmp + 1
    ASL item_x_low,X
    ROL A
    ASL item_x_low,X
    ROL A
    ASL item_x_low,X
    ROL A
    ASL item_x_low,X
    ROL A
    STA item_x_high,X
    LDA item_top_low,X          \ Down
    STA item_tmp
    LDA item_top_high,X
    STA item_tmp + 1
    LDA zp_box_y
    CLC
    ADC #(PLAYER_HEIGHT - ITEM_HEIGHT) DIV 2
    STA zp_temp2
    LDA zp_box_y + 1
    ADC #0
    STA zp_temp2 + 1
    JSR item_towards
    LDA item_tmp                \ y = top << 4
    STA item_y_low,X
    LDA item_tmp + 1
    ASL item_y_low,X
    ROL A
    ASL item_y_low,X
    ROL A
    ASL item_y_low,X
    ROL A
    ASL item_y_low,X
    ROL A
    STA item_y_high,X
    JMP item_set_place
}

\ Move item_tmp (16 bits) towards zp_temp2 (16 bits) by item X's speed
\ (its vx), at most to it. Preserves X.
.item_towards
{
    LDA zp_temp2                \ d = target - position
    SEC
    SBC item_tmp
    STA zp_temp
    LDA zp_temp2 + 1
    SBC item_tmp + 1
    STA zp_temp + 1
    BMI behind
    BNE ahead_far               \ d >= 256: the speed
    LDA zp_temp
    CMP item_vx,X
    BCC arrive                  \ d < speed: there
.ahead_far
    LDA item_tmp
    CLC
    ADC item_vx,X
    STA item_tmp
    BCC done
    INC item_tmp + 1
.done
    RTS
.behind
    CMP #&FF                    \ d <= -256: the speed
    BNE behind_far
    LDA zp_temp                 \ -d < speed: there
    EOR #&FF
    CLC
    ADC #1
    BEQ behind_far              \ (d = -256)
    CMP item_vx,X
    BCC arrive
.behind_far
    LDA item_tmp
    SEC
    SBC item_vx,X
    STA item_tmp
    BCS done
    DEC item_tmp + 1
    RTS
.arrive
    LDA zp_temp2
    STA item_tmp
    LDA zp_temp2 + 1
    STA item_tmp + 1
    RTS
}

\ Carry set if pixel zp_temp of line zp_temp2 (16 bits each) is in a tile in
\ the tile cache, from its bounds in pixels and lines (item_bounds, worked
\ out when first wanted in a frame).
.item_point_cached
{
    LDA item_bounded
    BNE bounded
    JSR item_bounds
    DEC item_bounded
.bounded
    LDA zp_temp
    CMP item_least_x
    LDA zp_temp + 1
    SBC item_least_x + 1
    BCC out
    LDA item_most_x
    CMP zp_temp
    LDA item_most_x + 1
    SBC zp_temp + 1
    BCC out
    LDA zp_temp2
    CMP item_least_y
    LDA zp_temp2 + 1
    SBC item_least_y + 1
    BCC out
    LDA item_most_y
    CMP zp_temp2
    LDA item_most_y + 1
    SBC zp_temp2 + 1
    RTS                         \ Carry set if inside
.out
    CLC
    RTS
}

\ The tile cache's bounds, in pixels and lines: cached_left * 8 to
\ cached_right * 8 + 7, cached_top * 16 to cached_bottom * 16 + 15.
.item_bounds
{
    LDA #0
    STA item_least_x + 1
    LDA cached_left
    ASL A
    ROL item_least_x + 1
    ASL A
    ROL item_least_x + 1
    ASL A
    ROL item_least_x + 1
    STA item_least_x
    LDA #0
    STA item_most_x + 1
    LDA cached_right
    ASL A
    ROL item_most_x + 1
    ASL A
    ROL item_most_x + 1
    ASL A
    ROL item_most_x + 1
    ORA #7
    STA item_most_x
    LDA #0
    STA item_least_y + 1
    LDA cached_top
    ASL A
    ROL item_least_y + 1
    ASL A
    ROL item_least_y + 1
    ASL A
    ROL item_least_y + 1
    ASL A
    ROL item_least_y + 1
    STA item_least_y
    LDA #0
    STA item_most_y + 1
    LDA cached_bottom
    ASL A
    ROL item_most_y + 1
    ASL A
    ROL item_most_y + 1
    ASL A
    ROL item_most_y + 1
    ASL A
    ROL item_most_y + 1
    ORA #15
    STA item_most_y
    RTS
}

\ Carry set if the quarter-cell holding pixel zp_temp (16 bits) of line
\ zp_temp2 (16 bits) is solid, from the tile cache (which must hold it).
\ Preserves zp_temp and zp_temp2.
.solid_at
{
    LDA zp_temp + 1             \ The tile: (px >> 3, line >> 4)
    STA zp_fill_x
    LDA zp_temp
    LSR zp_fill_x
    ROR A
    LSR zp_fill_x
    ROR A
    LSR zp_fill_x
    ROR A
    STA zp_fill_x
    LDA zp_temp2 + 1
    STA zp_fill_y
    LDA zp_temp2
    LSR zp_fill_y
    ROR A
    LSR zp_fill_y
    ROR A
    LSR zp_fill_y
    ROR A
    LSR zp_fill_y
    ROR A
    STA zp_fill_y
    JSR para_cache_pointer
    LDY #0
    LDA (para_cache),Y          \ Passable: not solid
    TAY
    LDA material_passable,Y
    BNE not_solid
    LDA para_cache + 1          \ The quarter-cell's bit in its shape's mask
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA (para_cache),Y
    AND #SHAPE_BITS
    TAY
    LDA zp_temp                 \ Column: (px >> 1) AND 3
    LSR A
    AND #3
    STA item_bit
    LDA zp_temp2                \ Row: (line >> 2) AND 3; rows 0-1 in the
    LSR A                       \ low byte, 2-3 the high
    LSR A
    AND #3
    LSR A
    BCC even_row
    PHA
    LDA item_bit
    ORA #4
    STA item_bit
    PLA
.even_row
    CMP #0
    BNE high_rows
    LDA shape_mask_low,Y
    JMP mask_set
.high_rows
    LDA shape_mask_high,Y
.mask_set
    LDY item_bit
    AND bit_of,Y
    BEQ not_solid
    SEC
    RTS
.not_solid
    CLC
    RTS
}

\ A, the low byte of a 16-bit value, with zp_temp + 1 its high: return the
\ value >> 4's low byte in A, and its high in zp_temp + 1.
.lines_of
{
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    RTS
}

\ Carry clear if item X touches the miner's box (zp_box_x, zp_box_y): their
\ boxes overlap. Preserves X.
.item_touches
{
    LDA item_px_low,X           \ px - box_x + ITEM_WIDTH - 1 < PLAYER_WIDTH +
    SEC                         \ ITEM_WIDTH - 1
    SBC zp_box_x
    STA zp_temp
    LDA item_px_high,X
    SBC zp_box_x + 1
    STA zp_temp + 1
    LDA zp_temp
    CLC
    ADC #ITEM_WIDTH - 1
    STA zp_temp
    LDA zp_temp + 1
    ADC #0
    BNE apart
    LDA zp_temp
    CMP #PLAYER_WIDTH + ITEM_WIDTH - 1
    BCS apart
    LDA item_top_low,X          \ top - box_y + ITEM_HEIGHT - 1 < PLAYER_HEIGHT +
    SEC                         \ ITEM_HEIGHT - 1
    SBC zp_box_y
    STA zp_temp
    LDA item_top_high,X
    SBC zp_box_y + 1
    STA zp_temp + 1
    LDA zp_temp
    CLC
    ADC #ITEM_HEIGHT - 1
    STA zp_temp
    LDA zp_temp + 1
    ADC #0
    BNE apart
    LDA zp_temp
    CMP #PLAYER_HEIGHT + ITEM_HEIGHT - 1
    RTS                         \ Carry clear if they touch
.apart
    SEC
    RTS
}

.item_spray_vx                  \ Sixteenths of a pixel a frame
    ITEM_SPRAY_VX
.item_spray_vy                  \ Sixteenths of a line a frame
    ITEM_SPRAY_VY

\ Set the box the miner's sprite covers, this frame or last (as the host
\ drew it), in world bytes and lines: item_box_left to item_box_right,
\ item_box_top to item_box_bottom, exclusive at the right and bottom; and
\ keep this frame's position for the next.
.item_miner_box
{
    LDA zp_player_x + 1         \ This frame's byte column: x >> 5
    STA zp_temp + 1
    LDA zp_player_x
    JSR lines_of
    LSR zp_temp + 1
    ROR A
    STA item_box_left
    STA item_box_right
    LDA zp_temp + 1
    STA item_box_left + 1
    STA item_box_right + 1
    LDA item_miner_x + 1        \ Last frame's
    STA zp_temp + 1
    LDA item_miner_x
    JSR lines_of
    LSR zp_temp + 1
    ROR A
    STA item_tmp
    CMP item_box_left           \ The lesser is the left, the greater the
    LDA zp_temp + 1             \ right
    STA item_tmp + 1
    SBC item_box_left + 1
    BCS last_right
    LDA item_tmp
    STA item_box_left
    LDA item_tmp + 1
    STA item_box_left + 1
    JMP across
.last_right
    LDA item_tmp
    STA item_box_right
    LDA item_tmp + 1
    STA item_box_right + 1
.across
    LDA item_box_right          \ Exclusive: + SPRITE_COLUMNS
    CLC
    ADC #SPRITE_COLUMNS
    STA item_box_right
    BCC right_set
    INC item_box_right + 1
.right_set
    LDA zp_player_y + 1         \ This frame's line: y >> 4
    STA zp_temp + 1
    LDA zp_player_y
    JSR lines_of
    STA item_box_top
    STA item_box_bottom
    LDA zp_temp + 1
    STA item_box_top + 1
    STA item_box_bottom + 1
    LDA item_miner_y + 1        \ Last frame's
    STA zp_temp + 1
    LDA item_miner_y
    JSR lines_of
    STA item_tmp
    CMP item_box_top
    LDA zp_temp + 1
    STA item_tmp + 1
    SBC item_box_top + 1
    BCS last_below
    LDA item_tmp
    STA item_box_top
    LDA item_tmp + 1
    STA item_box_top + 1
    JMP down
.last_below
    LDA item_tmp
    STA item_box_bottom
    LDA item_tmp + 1
    STA item_box_bottom + 1
.down
    LDA item_box_bottom         \ Exclusive: + PLAYER_HEIGHT
    CLC
    ADC #PLAYER_HEIGHT
    STA item_box_bottom
    BCC item_miner_keep
    INC item_box_bottom + 1
    \ Fall through
}

\ Keep this frame's position of the miner, for the next.
.item_miner_keep
{
    LDA zp_player_x
    STA item_miner_x
    LDA zp_player_x + 1
    STA item_miner_x + 1
    LDA zp_player_y
    STA item_miner_y
    LDA zp_player_y + 1
    STA item_miner_y + 1
    RTS
}

\ Set item_tmp to ITEM_BY_MINER if item X's sprite meets the miner's box
\ (item_miner_box), else 0: then the host must draw it again each frame,
\ as the miner's sprite is. Preserves X and Y; returns with carry clear.
.item_by_miner
{
    LDA #0
    STA item_tmp
    LDA item_px_high,X          \ Its byte column: px >> 1
    LSR A
    STA zp_temp + 1
    LDA item_px_low,X
    ROR A
    STA zp_temp
    CMP item_box_right          \ column < right
    LDA zp_temp + 1
    SBC item_box_right + 1
    BCS apart
    LDA zp_temp                 \ column + SPRITE_COLUMNS > left
    CLC
    ADC #SPRITE_COLUMNS
    STA zp_temp
    BCC added
    INC zp_temp + 1
.added
    LDA item_box_left
    CMP zp_temp
    LDA item_box_left + 1
    SBC zp_temp + 1
    BCS apart
    LDA item_top_low,X          \ top < bottom
    CMP item_box_bottom
    LDA item_top_high,X
    SBC item_box_bottom + 1
    BCS apart
    LDA item_top_low,X          \ top + ITEM_HEIGHT > box top
    CLC
    ADC #ITEM_HEIGHT
    STA zp_temp
    LDA item_top_high,X
    ADC #0
    STA zp_temp + 1
    LDA item_box_top
    CMP zp_temp
    LDA item_box_top + 1
    SBC zp_temp + 1
    BCS apart
    LDA #ITEM_BY_MINER
    STA item_tmp
.apart
    CLC
    RTS
}

\ Write the items in view to the packet at para_write, past the chunk to
\ fetch (cache_prefetch): a count, then each item's view column, view line
\ and frame. Only those wholly in view and clear of the columns the camera
\ can scroll in are sent (items.shown). The count has ITEMS_UNTOUCHED set
\ if the host redraws nothing under them this frame (no light's list, no
\ changed tiles, not the whole view), so that it can leave as they are
\ those drawn where they were.
.items_emit
{
    LDY #0                      \ Past the chunk to fetch: 0, or 3 bytes
    LDA (para_write),Y
    BEQ no_fetch
    LDA #FETCH_BYTES
    BNE past
.no_fetch
    LDA #1
.past
    CLC
    ADC para_write
    STA para_write
    BCC counted
    INC para_write + 1
.counted
    LDA #0
    STA item_sent
    LDA zp_camera_y             \ The camera's top line: camera_y * 8
    STA item_camera_line
    LDA zp_camera_y + 1
    ASL item_camera_line
    ROL A
    ASL item_camera_line
    ROL A
    ASL item_camera_line
    ROL A
    STA item_camera_line + 1
    LDA item_count              \ None: only the miner's position, kept
    BNE any
    JSR item_miner_keep
    LDY #1
    JMP done
.any
    JSR item_miner_box
    LDY #1                      \ Where the next item goes
    LDX #0
.loop
    CPX item_count
    BEQ done
    LDA item_px_high,X          \ Column: (px >> 1) - camera_x - MAX_STEP_X
    LSR A
    STA zp_temp + 1
    LDA item_px_low,X
    ROR A
    SEC
    SBC zp_camera_x
    STA zp_temp
    LDA zp_temp + 1
    SBC zp_camera_x + 1
    STA zp_temp + 1
    LDA zp_temp
    SEC
    SBC #MAX_STEP_X
    STA zp_temp
    LDA zp_temp + 1
    SBC #0
    BNE next
    LDA zp_temp
    CMP #VIEW_COLUMNS - 2 * MAX_STEP_X - ITEM_WIDTH DIV 2 + 1
    BCS next
    ADC #MAX_STEP_X             \ (Carry clear)
    STA zp_temp
    LDA item_top_low,X          \ Line: top - camera_y * 8
    SEC
    SBC item_camera_line
    STA zp_temp2
    LDA item_top_high,X
    SBC item_camera_line + 1
    BNE next
    LDA zp_temp2
    CMP #VIEW_LINES - ITEM_HEIGHT + 1
    BCS next
    LDA zp_temp                 \ Sent
    STA (para_write),Y
    INY
    LDA zp_temp2
    STA (para_write),Y
    INY
    JSR item_by_miner           \ Its frame, marked if by the miner
    LDA item_kind,X
    ADC #ITEM_FRAME_FIRST       \ (Carry clear)
    ORA item_tmp
    STA (para_write),Y
    INY
    INC item_sent
.next
    INX
    BNE loop
.done
    JSR hand_emit               \ And the hand, if shown
    LDA zp_redraw               \ Nothing redrawn under them?
    ORA para_changes
    ORA sl_list_count
    BEQ untouched
    LDA item_sent
    JMP count_set
.untouched
    LDA item_sent
    ORA #ITEMS_UNTOUCHED
.count_set
    LDY #0
    STA (para_write),Y
    RTS
}

\ After the items, the hand, shown above the miner as its kind's item for
\ HAND_FRAMES frames once it changes (items.hand_shown), marked as by the
\ miner, so that it is drawn each frame as he moves. Y is where it goes in
\ the packet, and is moved on past it.
.hand_emit
{
    LDA hand
    CMP hand_last
    BEQ same
    STA hand_last
    LDA #HAND_FRAMES
    STA hand_timer
    BNE show                    \ Always branches
.same
    LDA hand_timer
    BEQ done
    DEC hand_timer
    BEQ done
.show
    LDA zp_player_x + 1         \ Column: (x >> 5) - camera_x
    STA zp_temp + 1
    LDA zp_player_x
    LDX #5
.shift_x
    LSR zp_temp + 1
    ROR A
    DEX
    BNE shift_x
    SEC
    SBC zp_camera_x
    STA zp_temp
    LDA zp_temp + 1
    SBC zp_camera_x + 1
    BNE done
    LDA zp_temp
    SEC
    SBC #MAX_STEP_X
    CMP #VIEW_COLUMNS - 2 * MAX_STEP_X - ITEM_WIDTH DIV 2 + 1
    BCS done
    LDA zp_player_y + 1         \ Line: (y >> 4) - ITEM_HEIGHT - HAND_GAP
    STA zp_temp2 + 1            \ - camera_y * 8
    LDA zp_player_y
    LDX #4
.shift_y
    LSR zp_temp2 + 1
    ROR A
    DEX
    BNE shift_y
    SEC
    SBC #ITEM_HEIGHT + HAND_GAP
    STA zp_temp2
    LDA zp_temp2 + 1
    SBC #0
    STA zp_temp2 + 1
    LDA zp_temp2
    SEC
    SBC item_camera_line
    STA zp_temp2
    LDA zp_temp2 + 1
    SBC item_camera_line + 1
    BNE done
    LDA zp_temp2
    CMP #VIEW_LINES - ITEM_HEIGHT + 1
    BCS done
    LDA zp_temp                 \ Sent
    STA (para_write),Y
    INY
    LDA zp_temp2
    STA (para_write),Y
    INY
    LDA hand
    CLC
    ADC #ITEM_FRAME_FIRST
    ORA #ITEM_BY_MINER
    STA (para_write),Y
    INY
    INC item_sent
.done
    RTS
}

.bit_of
    EQUB 1, 2, 4, 8, 16, 32, 64, 128

.material_drops                 \ The kind each material drops, &FF if none
    MATERIAL_DROPS
