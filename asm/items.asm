\ Items lying in the world (tools/stratagem/items.py, which this does
\ exactly): what a felled tree drops. A trunk's part that breaks, dug or
\ fallen, drops a piece of wood at the bottom of its tile; items fall until
\ the quarter-cell under the middle of their bottom is solid, at most a
\ quarter-cell a frame, over the tile cache (elsewhere they wait); and the
\ miner picks up an item by touching it. At most ITEM_MAX lie in the world:
\ more go straight into the inventory. The packet carries those in view,
\ for the host to draw as sprites (items_emit).
\
\ An item lying on the ground is marked at rest (ITEM_RESTING in its vy) and
\ not moved, as it would land where it is, until a tile changes
\ (call_set_tile sets items_woken).

ITEM_RESTING = &80
ASSERT ITEM_MAX_FALL < ITEM_RESTING

ASSERT ITEM_MAX_FALL <= 4 * 16  \ A quarter-cell a frame, at most
ASSERT WOOD = 0 AND ITEM_FRAME_COUNT = 1   \ Wood, for now, is all there is

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

\ Each item falls, and is picked up if the miner touches it.
.items_step
{
    LDA items_woken             \ A tile changed: nothing is at rest
    BEQ awake
    LDA #0
    STA items_woken
    LDX item_count
    BEQ awake
.wake
    LDA item_vy - 1,X
    AND #&FF - ITEM_RESTING
    STA item_vy - 1,X
    DEX
    BNE wake
.awake
    JSR player_pixels           \ The miner's box: zp_box_x, zp_box_y
    LDX #0
.loop
    CPX item_count
    BEQ done
    STX item_i
    LDA item_vy,X
    BMI rests
    JSR item_fall
    LDX item_i
.rests
    JSR item_touches
    BCS next
    JSR item_gained             \ Picked up: the last takes its place
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

\ Item X falls a frame, if the tile under its middle is in the tile cache.
.item_fall
{
    LDA item_vy,X               \ vy = min(vy + GRAVITY, ITEM_MAX_FALL)
    CLC
    ADC #GRAVITY
    CMP #ITEM_MAX_FALL
    BCC vy_set
    LDA #ITEM_MAX_FALL
.vy_set
    STA item_new_vy
    CLC                         \ y + vy
    ADC item_y_low,X
    STA item_new_y
    LDA item_y_high,X
    ADC #0
    STA item_new_y + 1
    STA item_below + 1          \ The line below it: (y >> 4) + ITEM_HEIGHT
    LDA item_new_y
    LSR item_below + 1
    ROR A
    LSR item_below + 1
    ROR A
    LSR item_below + 1
    ROR A
    LSR item_below + 1
    ROR A
    CLC
    ADC #ITEM_HEIGHT
    STA item_below
    BCC below_set
    INC item_below + 1
.below_set
    LDA item_x_low,X            \ Its middle: x + ITEM_WIDTH / 2
    CLC
    ADC #ITEM_WIDTH DIV 2
    STA item_middle
    LDA item_x_high,X
    ADC #0
    STA item_middle + 1
    STA zp_temp                 \ The tile there
    LDA item_middle
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    STA zp_fill_x
    ASSERT TILE_WIDTH = 8 AND TILE_HEIGHT = 16
    LDA item_below + 1
    STA zp_temp
    LDA item_below
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    STA zp_fill_y
    JSR in_tile_cache
    BCS cached
    RTS                         \ It waits
.cached
    JSR para_cache_pointer
    LDY #0
    LDA (para_cache),Y          \ Passable: not solid
    TAY
    LDA material_passable,Y
    BNE falls
    LDA para_cache + 1          \ The quarter-cell's bit in its shape's mask
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA (para_cache),Y
    AND #SHAPE_BITS
    TAY
    LDA item_middle             \ Column: (middle >> 1) AND 3
    LSR A
    AND #3
    STA zp_temp
    LDA item_below              \ Row: (below >> 2) AND 3
    LSR A
    LSR A
    AND #3
    LSR A                       \ Rows 0-1 in the low byte, 2-3 the high
    BCC even_row
    PHA
    LDA zp_temp
    ORA #4
    STA zp_temp
    PLA
.even_row
    CMP #0
    BNE high_rows
    LDA shape_mask_low,Y
    JMP mask_set
.high_rows
    LDA shape_mask_high,Y
.mask_set
    LDY zp_temp
    AND bit_of,Y
    BNE lands
.falls
    LDX item_i
    LDA item_new_y
    STA item_y_low,X
    LDA item_new_y + 1
    STA item_y_high,X
    LDA item_new_vy
    STA item_vy,X
    RTS
.lands
    LDX item_i                  \ On the quarter-cell's top:
    LDA item_below              \ y = ((below AND NOT 3) - ITEM_HEIGHT) << 4
    AND #&FC
    SEC
    SBC #ITEM_HEIGHT
    STA zp_temp
    LDA item_below + 1
    SBC #0
    ASL zp_temp
    ROL A
    ASL zp_temp
    ROL A
    ASL zp_temp
    ROL A
    ASL zp_temp
    ROL A
    STA item_y_high,X
    LDA zp_temp
    STA item_y_low,X
    LDA #ITEM_RESTING
    STA item_vy,X
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
    LDA item_y_high,X           \ Its top: y >> 4
    STA zp_temp + 1
    LDA item_y_low,X
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    SEC                         \ top - py + ITEM_HEIGHT - 1 < PLAYER_HEIGHT +
    SBC zp_box_y                \ ITEM_HEIGHT - 1
    STA zp_temp
    LDA zp_temp + 1
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

\ Write the items in view to the packet at para_write, past the chunk to
\ fetch (cache_prefetch): a count, then each item's view column, view line
\ and frame. Only those wholly in view and clear of the columns the camera
\ can scroll in are sent (items.shown).
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
    LDA item_y_high,X           \ Line: (y >> 4) - camera_y * 8
    STA zp_temp + 1
    LDA item_y_low,X
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    LSR zp_temp + 1
    ROR A
    SEC
    SBC item_camera_line
    STA zp_temp2
    LDA zp_temp + 1
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
    LDA item_kind,X
    CLC
    ADC #ITEM_FRAME_FIRST
    STA (para_write),Y
    INY
    INC item_sent
.next
    INX
    BNE loop
.done
    LDA item_sent
    LDY #0
    STA (para_write),Y
    RTS
}

.bit_of
    EQUB 1, 2, 4, 8, 16, 32, 64, 128

.material_drops                 \ The kind each material drops, &FF if none
    MATERIAL_DROPS
