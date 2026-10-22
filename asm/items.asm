\ Items lying in the world (tools/stratagem/items.py, which this does
\ exactly): what a felled tree drops. A trunk's part that breaks, dug or
\ fallen, drops a piece of wood at the bottom of its tile. Items fall, at
\ most a quarter-cell a frame, until something holds a bottom corner: a
\ solid quarter-cell, or another item's top. An item lies still only if
\ both corners are held at the same height, and not both by one item;
\ otherwise it slides SLIDE pixels to the side not held and falls again,
\ unless the slide is blocked: so items pile up, as sand does. Only items
\ over the tile cache move (elsewhere they wait). While P is held
\ (INPUT_PICK), the miner picks up each item he touches. At most ITEM_MAX lie in the world: more go straight
\ into the inventory. The packet carries those in view, for the host to
\ draw as sprites (items_emit).
\
\ An item that stayed as it was in its frame's fall would again in the
\ next, unless a tile changes, an item is picked up, or an item it rested on
\ or was blocked by moves: so it is marked still (ITEM_STILL in its vy) and
\ not moved, until one of those wakes it (a changed tile sets
\ items_moving, which wakes them all; a move wakes those touching the
\ moving item where it was).

ITEM_STILL = &80
ASSERT ITEM_MAX_FALL < ITEM_STILL

ASSERT ITEM_MAX_FALL <= 4 * 16  \ A quarter-cell a frame, at most
ASSERT WOOD = 0 AND ITEM_FRAME_COUNT = 1   \ Wood, for now, is all there is
ITEM_NONE = &FF                 \ What holds a corner: nothing,
ITEM_TERRAIN = &80              \ the ground, or an item's index

\ Material A broke at tile (X, Y): drop what it drops, if anything.
.item_drop
{
    STX item_tx
    TAX
    LDA material_drops,X
    BMI done                    \ Nothing
    LDX item_count
    CPX #ITEM_MAX
    BCS full
    STA item_kind,X
    LDA item_tx                 \ x = tx * 8 + ITEM_OFFSET_X
    ASL A
    ASL A
    ASL A
    ORA #ITEM_OFFSET_X
    STA item_x_low,X
    LDA item_tx
    LSR A
    LSR A
    LSR A
    LSR A
    LSR A
    STA item_x_high,X
    LDA #LO(-ITEM_HEIGHT * 16)  \ y = ((ty + 1) * 16 - ITEM_HEIGHT) * 16
    STA item_y_low,X
    TYA
    STA item_y_high,X
    ASSERT ITEM_HEIGHT * 16 <= 256
    ASL A                       \ Its top: ty * 16 + 16 - ITEM_HEIGHT
    ASL A
    ASL A
    ASL A
    ORA #16 - ITEM_HEIGHT
    STA item_top_low,X
    TYA
    LSR A
    LSR A
    LSR A
    LSR A
    STA item_top_high,X
    LDA #0
    STA item_vy,X
    INC item_count
.done
    RTS
.full
    JMP item_gained
}

\ An item went into the inventory.
.item_gained
{
    LDA wood
    CMP #INVENTORY_MAX
    BCS done
    INC wood
.done
    RTS
}

\ Each item falls, unless it is still, and is picked up if the miner
\ touches it while picking up.
.items_step
{
    LDA items_moving            \ A tile changed: none is still
    BEQ awake
    LDA #0
    STA items_moving
    JSR items_wake
.awake
    LDA item_count
    BEQ done
    LDA #0                      \ The bounds, when an item first falls
    STA item_bounded
    JSR player_pixels           \ The miner's box: zp_box_x, zp_box_y
    LDX #0
.loop
    CPX item_count
    BEQ done
    STX item_i
    LDA item_vy,X
    BMI fallen                  \ Still
    JSR item_fall
    LDX item_i
.fallen
    LDA zp_input                \ Picking up?
    AND #INPUT_PICK
    BEQ next
    JSR item_touches
    BCS next
    JSR item_gained             \ Picked up: the last takes its place, and
    JSR items_wake              \ none is still
    LDX item_i
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
    LDA item_top_low,Y
    STA item_top_low,X
    LDA item_top_high,Y
    STA item_top_high,X
    LDA item_vy,Y
    STA item_vy,X
    LDA item_kind,Y
    STA item_kind,X
    JMP loop
.next
    INX
    BNE loop
.done
    RTS
}

\ The bounds within which an item's tiles are all in the tile cache, for
\ item_fall: its left at least cached_left * 8 + SLIDE, its right at most
\ cached_right * 8 + 7 - SLIDE, its top at least cached_top * 16 + 4, the
\ line under it at most cached_bottom * 16 + 15.
.item_bounds
{
    LDA #0
    STA item_least_left + 1
    LDA cached_left
    ASL A
    ROL item_least_left + 1
    ASL A
    ROL item_least_left + 1
    ASL A
    ROL item_least_left + 1
    ORA #SLIDE                  \ (Its low three bits are clear)
    STA item_least_left
    LDA #0
    STA item_most_right + 1
    LDA cached_right
    ASL A
    ROL item_most_right + 1
    ASL A
    ROL item_most_right + 1
    ASL A
    ROL item_most_right + 1
    ORA #7 - SLIDE
    STA item_most_right
    LDA #0
    STA item_least_top + 1
    LDA cached_top
    ASL A
    ROL item_least_top + 1
    ASL A
    ROL item_least_top + 1
    ASL A
    ROL item_least_top + 1
    ASL A
    ROL item_least_top + 1
    ORA #4
    STA item_least_top
    LDA #0
    STA item_most_below + 1
    LDA cached_bottom
    ASL A
    ROL item_most_below + 1
    ASL A
    ROL item_most_below + 1
    ASL A
    ROL item_most_below + 1
    ASL A
    ROL item_most_below + 1
    ORA #15
    STA item_most_below
    RTS
}
ASSERT SLIDE < 8

\ No item is still. Preserves X.
.items_wake
{
    LDY item_count
    BEQ done
.loop
    LDA item_vy - 1,Y
    AND #&FF - ITEM_STILL
    STA item_vy - 1,Y
    DEY
    BNE loop
.done
    RTS
}

\ Item item_i's frame (items.fall): it falls, comes to rest or slides; or
\ it waits, if the tiles around it aren't all in the tile cache. Marks it
\ still if it stays as it was (and didn't wait); if it moves, wakes the
\ items touching it where it was.
.item_fall
{
    LDX item_i
    LDA item_x_low,X            \ Its corners' pixels
    STA item_left
    CLC
    ADC #ITEM_WIDTH - 1
    STA item_right
    LDA item_x_high,X
    STA item_left + 1
    ADC #0
    STA item_right + 1
    LDA item_top_low,X          \ Its top, and the line under it
    STA item_top
    STA item_old_top
    CLC
    ADC #ITEM_HEIGHT
    STA item_old_below
    LDA item_top_high,X
    STA item_top + 1
    STA item_old_top + 1
    ADC #0
    STA item_old_below + 1
    LDA item_vy,X               \ vy = min(vy + GRAVITY, ITEM_MAX_FALL)
    CLC
    ADC #GRAVITY
    CMP #ITEM_MAX_FALL
    BCC vy_set
    LDA #ITEM_MAX_FALL
.vy_set
    STA item_new_vy
    CLC                         \ y + vy, and the line under it then
    ADC item_y_low,X
    STA item_new_y
    LDA item_y_high,X
    ADC #0
    STA item_new_y + 1
    STA zp_temp + 1
    LDA item_new_y
    JSR lines_of
    CLC
    ADC #ITEM_HEIGHT
    STA item_below
    LDA zp_temp + 1
    ADC #0
    STA item_below + 1
    \ Wait unless the tiles from (left - SLIDE, top - a quarter-cell) to
    \ (right + SLIDE, below) are in the tile cache: within the bounds
    \ (item_bounds).
    LDA item_bounded
    BNE bounded
    JSR item_bounds
    DEC item_bounded
.bounded
    LDA item_left
    CMP item_least_left
    LDA item_left + 1
    SBC item_least_left + 1
    BCC waits
    LDA item_most_right
    CMP item_right
    LDA item_most_right + 1
    SBC item_right + 1
    BCC waits
    LDA item_top
    CMP item_least_top
    LDA item_top + 1
    SBC item_least_top + 1
    BCC waits
    LDA item_most_below
    CMP item_below
    LDA item_most_below + 1
    SBC item_below + 1
    BCS cached
.waits
    RTS
.cached
    JSR item_held               \ What holds each corner
    LDA item_line
    STA item_held_right
    LDA item_line + 1
    STA item_held_right + 1
    LDX item_i
    LDA item_x_low,X            \ Where it goes: x as it is, unless it slides
    STA item_new_x_low
    LDA item_x_high,X
    STA item_new_x_high
    LDA item_what_left
    AND item_what
    CMP #ITEM_NONE
    BNE held
    JMP set                     \ Neither held: it falls
.held
    LDA item_what_left          \ The higher held: line (left's, unless
    CMP #ITEM_NONE              \ none or the right's is higher)
    BEQ right_line
    LDA item_what
    CMP #ITEM_NONE
    BEQ left_line
    LDA item_line
    CMP item_held_left
    LDA item_line + 1
    SBC item_held_left + 1
    BCC right_line
.left_line
    LDA item_held_left
    STA item_line
    LDA item_held_left + 1
    STA item_line + 1
.right_line
    LDA item_line               \ Lying there: top = line - ITEM_HEIGHT
    SEC
    SBC #ITEM_HEIGHT
    STA item_top
    LDA item_line + 1
    SBC #0
    STA item_top + 1
    STA zp_temp                 \ y = top << 4, vy = 0
    LDA item_top
    ASL A
    ROL zp_temp
    ASL A
    ROL zp_temp
    ASL A
    ROL zp_temp
    ASL A
    ROL zp_temp
    STA item_new_y
    LDA zp_temp
    STA item_new_y + 1
    LDA #0
    STA item_new_vy
    LDA #0                      \ Which corners are held there: bit 1 the
    STA item_holds              \ left, bit 0 the right
    LDA item_what_left
    CMP #ITEM_NONE
    BEQ left_free
    LDA item_held_left
    CMP item_line
    BNE left_free
    LDA item_held_left + 1
    CMP item_line + 1
    BNE left_free
    LDA #2
    STA item_holds
.left_free
    LDA item_what
    CMP #ITEM_NONE
    BEQ right_free
    LDA item_held_right
    CMP item_line
    BNE right_free
    LDA item_held_right + 1
    CMP item_line + 1
    BNE right_free
    LDA item_holds
    ORA #1
    STA item_holds
.right_free
    LDA item_holds
    CMP #3
    BNE one_side
    LDA item_what_left          \ Held at both corners: lies still, unless
    CMP #ITEM_TERRAIN           \ squarely on one item
    BEQ set
    CMP item_what
    BNE set
    TAY                         \ Off it, the way it overhangs it
    LDA item_x_low,Y
    CMP item_x_low,X
    LDA item_x_high,Y
    SBC item_x_high,X
    BCC slide_right             \ It overhangs to the right
    LDA item_x_low,Y
    CMP item_x_low,X
    BNE slide_left
    LDA item_x_high,Y
    CMP item_x_high,X
    BNE slide_left
    TXA                         \ Squarely: by its place in the list
    LSR A
    BCS slide_right
.slide_left
    LDA #&100 - SLIDE
    BNE step_set
.one_side
    CMP #2                      \ Towards the side not held
    BEQ slide_right
    BNE slide_left
.slide_right
    LDA #SLIDE
.step_set
    STA item_step
    BMI edge_left
    LDA item_right              \ The edge it slides: right + SLIDE...
    CLC
    ADC #SLIDE
    STA item_px
    LDA item_right + 1
    ADC #0
    STA item_px + 1
    JMP edge_set
.edge_left
    LDA item_left               \ ... or left - SLIDE
    SEC
    SBC #SLIDE
    STA item_px
    LDA item_left + 1
    SBC #0
    STA item_px + 1
.edge_set
    JSR item_blocked
    BCS set                     \ Blocked: it lies still
    LDX item_i
    LDA item_step               \ x + step
    CLC
    ADC item_x_low,X
    STA item_new_x_low
    LDA item_step
    AND #&80                    \ (the step's sign, extended)
    BEQ positive
    LDA #&FF
.positive
    ADC item_x_high,X
    STA item_new_x_high
.set
    LDX item_i                  \ Moved?
    LDA item_new_x_low
    CMP item_x_low,X
    BNE moved
    LDA item_new_x_high
    CMP item_x_high,X
    BNE moved
    LDA item_new_y
    CMP item_y_low,X
    BNE moved
    LDA item_new_y + 1
    CMP item_y_high,X
    BNE moved
    LDA item_new_vy
    CMP item_vy,X
    BEQ stayed
.moved
    JSR item_wake_touching
    LDX item_i
    LDA item_new_x_low
    STA item_x_low,X
    LDA item_new_x_high
    STA item_x_high,X
    LDA item_new_y
    STA item_y_low,X
    LDA item_new_y + 1
    STA item_y_high,X
    STA zp_temp + 1             \ ... and its top
    LDA item_new_y
    JSR lines_of
    STA item_top_low,X
    LDA zp_temp + 1
    STA item_top_high,X
    LDA item_new_vy
    STA item_vy,X
    RTS
.stayed
    LDA item_vy,X
    ORA #ITEM_STILL
    STA item_vy,X
    RTS
}

\ Item item_i is moving from (item_left, item_old_top): wake the items
\ touching it there, that rested on it (their bottom on its top) or were
\ blocked by it (within SLIDE of its sides), whose fall it may change:
\ those whose box, widened by SLIDE each way and a line downwards, meets
\ its.
.item_wake_touching
{
    LDX #0
.loop
    CPX item_count
    BEQ done
    CPX item_i
    BEQ next
    LDA item_x_low,X            \ x - left + ITEM_WIDTH + SLIDE - 1 <
    SEC                         \ 2 * (ITEM_WIDTH + SLIDE) - 1
    SBC item_left
    TAY
    LDA item_x_high,X
    SBC item_left + 1
    STA item_tmp + 1
    TYA
    CLC
    ADC #ITEM_WIDTH + SLIDE - 1
    TAY
    LDA item_tmp + 1
    ADC #0
    BNE next
    CPY #2 * (ITEM_WIDTH + SLIDE) - 1
    BCS next
    LDA item_top_low,X          \ top - old_top + ITEM_HEIGHT < 2 *
    SEC                         \ ITEM_HEIGHT + 1
    SBC item_old_top
    TAY
    LDA item_top_high,X
    SBC item_old_top + 1
    STA item_tmp + 1
    TYA
    CLC
    ADC #ITEM_HEIGHT
    TAY
    LDA item_tmp + 1
    ADC #0
    BNE next
    CPY #2 * ITEM_HEIGHT + 1
    BCS next
    LDA item_vy,X               \ Woken
    AND #&FF - ITEM_STILL
    STA item_vy,X
.next
    INX
    BNE loop
.done
    RTS
}

\ What holds each of item item_i's corners, its bottom moving from line
\ item_old_below to item_below (items._held): the line its bottom comes to
\ and what holds it there (ITEM_TERRAIN or the holding item), the highest
\ (the ground winning a tie, then the first item); or ITEM_NONE. The left
\ corner's in item_held_left and item_what_left, the right's in item_line
\ and item_what. Both corners in one pass over the items.
.item_held
{
    LDA #ITEM_NONE
    STA item_what_left
    STA item_what
    LDA item_below              \ The ground under each corner
    STA zp_temp2
    LDA item_below + 1
    STA zp_temp2 + 1
    LDA item_left
    STA zp_temp
    LDA item_left + 1
    STA zp_temp + 1
    JSR solid_at
    BCC left_open
    LDA item_below              \ The quarter-cell's top
    AND #&FC
    STA item_held_left
    LDA item_below + 1
    STA item_held_left + 1
    LDA #ITEM_TERRAIN
    STA item_what_left
.left_open
    LDA item_right
    STA zp_temp
    LDA item_right + 1
    STA zp_temp + 1
    JSR solid_at
    BCC right_open
    LDA item_below
    AND #&FC
    STA item_line
    LDA item_below + 1
    STA item_line + 1
    LDA #ITEM_TERRAIN
    STA item_what
.right_open
    LDX #0                      \ The items under each corner
.loop
    CPX item_count
    BEQ done
    CPX item_i
    BEQ next
    JSR item_under
.next
    INX
    BNE loop
.done
    RTS
}

\ For item_held: whether item X is under either corner, and higher than
\ what holds it so far. Preserves X.
.item_under
{
    LDA item_left               \ d = left - x: the left corner is over it
    SEC                         \ if 0 <= d < ITEM_WIDTH, the right if
    SBC item_x_low,X            \ -(ITEM_WIDTH - 1) <= d <= 0
    TAY
    LDA item_left + 1
    SBC item_x_high,X
    BEQ ahead
    CMP #&FF
    BNE out
    CPY #&100 - (ITEM_WIDTH - 1)
    BCC out
    LDA #1                      \ The right
    BNE over
.out
    RTS
.ahead
    TYA
    BEQ both
    CMP #ITEM_WIDTH
    BCS out
    LDA #2                      \ The left
    BNE over
.both
    LDA #3
.over
    STA item_overs
    LDA item_top_low,X          \ Its top, between old_below and below?
    CMP item_old_below
    LDA item_top_high,X
    SBC item_old_below + 1
    BCC next
    LDA item_below
    CMP item_top_low,X
    LDA item_below + 1
    SBC item_top_high,X
    BCC next
    LSR item_overs
    BCC left
    LDA item_what               \ The right: higher than its holder so far?
    CMP #ITEM_NONE
    BEQ right_higher
    LDA item_top_low,X
    CMP item_line
    LDA item_top_high,X
    SBC item_line + 1
    BCS left
.right_higher
    LDA item_top_low,X
    STA item_line
    LDA item_top_high,X
    STA item_line + 1
    STX item_what
.left
    LSR item_overs
    BCC next
    LDA item_what_left          \ The left: higher than its holder so far?
    CMP #ITEM_NONE
    BEQ left_higher
    LDA item_top_low,X
    CMP item_held_left
    LDA item_top_high,X
    SBC item_held_left + 1
    BCS next
.left_higher
    LDA item_top_low,X
    STA item_held_left
    LDA item_top_high,X
    STA item_held_left + 1
    STX item_what_left
.next
    RTS
}

\ Carry clear if item X lies over pixel column item_px: x <= px < x +
\ ITEM_WIDTH. Preserves X.
.item_over_px
{
    LDA item_px
    SEC
    SBC item_x_low,X
    TAY
    LDA item_px + 1
    SBC item_x_high,X
    BNE over_not
    CPY #ITEM_WIDTH
    RTS                         \ Carry clear if px - x < ITEM_WIDTH
.over_not
    SEC
    RTS
}

\ Carry set if item item_i, with its top at line item_top, would overlap
\ solid ground or another item in pixel column item_px (items._blocked).
.item_blocked
{
    LDA item_px
    STA zp_temp
    LDA item_px + 1
    STA zp_temp + 1
    LDA item_top                \ Lines top, top + 4 and top + ITEM_HEIGHT - 1
    STA zp_temp2
    LDA item_top + 1
    STA zp_temp2 + 1
    JSR solid_at
    BCS done
    LDA item_top
    CLC
    ADC #4
    STA zp_temp2
    LDA item_top + 1
    ADC #0
    STA zp_temp2 + 1
    JSR solid_at
    BCS done
    LDA item_top
    CLC
    ADC #ITEM_HEIGHT - 1
    STA zp_temp2
    LDA item_top + 1
    ADC #0
    STA zp_temp2 + 1
    JSR solid_at
    BCS done
    LDX #0                      \ Another item there: over px, and its top
.loop                           \ within ITEM_HEIGHT - 1 of top
    CPX item_count
    BEQ clear
    CPX item_i
    BEQ next
    JSR item_over_px
    BCS next
    LDA item_top_low,X          \ other - top + ITEM_HEIGHT - 1 < 2 *
    CLC                         \ ITEM_HEIGHT - 1
    ADC #ITEM_HEIGHT - 1
    STA item_tmp
    LDA item_top_high,X
    ADC #0
    STA item_tmp + 1
    LDA item_tmp
    SEC
    SBC item_top
    TAY
    LDA item_tmp + 1
    SBC item_top + 1
    BNE next
    CPY #2 * ITEM_HEIGHT - 1
    BCC done                    \ (Carry clear: overlaps)
.next
    INX
    BNE loop
.clear
    CLC
    RTS
.done
    BCC overlaps
    RTS                         \ Carry set: solid ground
.overlaps
    SEC
    RTS
}

\ Carry set if the quarter-cell holding pixel zp_temp (16 bits) of line
\ zp_temp2 (16 bits) is solid, from the tile cache (which must hold it).
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

\ A, the low byte of y (sixteenths of a line), with zp_temp + 1 its high:
\ return y >> 4's low byte in A, and its high in zp_temp + 1.
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
    LDA item_x_low,X            \ x - px + ITEM_WIDTH - 1 < PLAYER_WIDTH +
    SEC                         \ ITEM_WIDTH - 1
    SBC zp_box_x
    STA zp_temp
    LDA item_x_high,X
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
    LDA item_top_low,X          \ top - py + ITEM_HEIGHT - 1 < PLAYER_HEIGHT +
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

\ Set the box the miner's sprite covers, this frame or last (as the host
\ drew it), in world bytes and lines: item_box_left to item_box_right,
\ item_box_top to item_box_bottom, exclusive at the right and bottom; and
\ keep this frame's position for the next.
.item_miner_box
{
    LDA zp_player_x + 1         \ The sprite's byte column: x >> 5
    STA zp_temp + 1
    LDA zp_player_x
    JSR lines_of
    LSR zp_temp + 1
    ROR A
    STA item_tmp
    LDA zp_temp + 1
    STA item_tmp + 1
    LDA zp_player_y + 1         \ Its line: y >> 4
    STA zp_temp + 1
    LDA zp_player_y
    JSR lines_of
    STA zp_temp
    LDA item_tmp                \ Left: the lesser column
    CMP item_miner_column
    LDA item_tmp + 1
    SBC item_miner_column + 1
    BCC this_left
    LDA item_miner_column
    STA item_box_left
    LDA item_miner_column + 1
    STA item_box_left + 1
    LDA item_tmp
    CLC
    ADC #SPRITE_COLUMNS
    STA item_box_right
    LDA item_tmp + 1
    ADC #0
    STA item_box_right + 1
    JMP across
.this_left
    LDA item_tmp
    STA item_box_left
    LDA item_tmp + 1
    STA item_box_left + 1
    LDA item_miner_column
    CLC
    ADC #SPRITE_COLUMNS
    STA item_box_right
    LDA item_miner_column + 1
    ADC #0
    STA item_box_right + 1
.across
    LDA zp_temp                 \ Top: the lesser line
    CMP item_miner_line
    LDA zp_temp + 1
    SBC item_miner_line + 1
    BCC this_top
    LDA item_miner_line
    STA item_box_top
    LDA item_miner_line + 1
    STA item_box_top + 1
    LDA zp_temp
    CLC
    ADC #PLAYER_HEIGHT
    STA item_box_bottom
    LDA zp_temp + 1
    ADC #0
    STA item_box_bottom + 1
    JMP kept
.this_top
    LDA zp_temp
    STA item_box_top
    LDA zp_temp + 1
    STA item_box_top + 1
    LDA item_miner_line
    CLC
    ADC #PLAYER_HEIGHT
    STA item_box_bottom
    LDA item_miner_line + 1
    ADC #0
    STA item_box_bottom + 1
.kept
    LDA item_tmp                \ For the next frame
    STA item_miner_column
    LDA item_tmp + 1
    STA item_miner_column + 1
    LDA zp_temp
    STA item_miner_line
    LDA zp_temp + 1
    STA item_miner_line + 1
    RTS
}

\ Set item_tmp to ITEM_BY_MINER if item X's sprite meets the miner's box
\ (item_miner_box), else 0: then the host must draw it again each frame,
\ as the miner's sprite is. Preserves X and Y; returns with carry clear.
.item_by_miner
{
    LDA #0
    STA item_tmp
    LDA item_x_high,X           \ Its byte column: x >> 1
    LSR A
    STA zp_temp + 1
    LDA item_x_low,X
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
    JSR item_miner_box
    LDA #0
    STA item_sent
    LDY #1                      \ Where the next item goes
    LDX #0
.loop
    CPX item_count
    BEQ done
    LDA item_x_high,X           \ Column: (x >> 1) - camera_x - MAX_STEP_X
    LSR A
    STA zp_temp + 1
    LDA item_x_low,X
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

.bit_of
    EQUB 1, 2, 4, 8, 16, 32, 64, 128

.material_drops                 \ The kind each material drops, &FF if none
    MATERIAL_DROPS
