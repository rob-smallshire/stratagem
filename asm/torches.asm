\ Torches, on the parasite (docs/tube-game.md). One is placed as a block is
\ (actions.asm), torches being a kind (inventory.py), or, with no empty
\ tile to aim at, in the miner's own tile; at most TORCH_MAX in the world. A torch lights the tiles around it as the miner's light does (the same flood, from the torch's
\ tile), but its light is fixed, a level per tile, kept with daylight in the
\ tile cache's light plane: the host draws it with the tiles, and the
\ miner's light shows only where brighter. Each torch's pool is kept, so that
\ tiles entering the tile cache are lit by it.
\
\ When a tile changes within a torch's reach (a torch dropped, a dig), that
\ torch's pool is flooded again and the tiles around it relit; those whose
\ light changes are queued with their new light, and sent to the host as
\ changed tiles, a few a frame. The tile cache takes the new light only when
\ a tile is sent, so that the miner's light always compares against what the
\ host shows.

\ Put a torch in the tile aimed at (actions.asm's place, zp_world_new_shape
\ set) and add it to the torches; return with carry set if the world is
\ full. The tile's change floods it (torch_tile_changed).
.torch_place
{
    LDA light_dirty             \ Light passes a torch as it passed the
    PHA                         \ empty tile: the miner's flood stands
    LDA #TILE_TORCH
    JSR change_target
    PLA
    STA light_dirty
    BCS done                    \ The world is full
    LDX torch_count
    LDA target_x
    STA torch_x,X
    LDA target_y
    STA torch_y,X
    INC torch_count
    CLC
.done
    RTS
}

\ Return carry set if the hand is the torches and there are TORCH_MAX in
\ the world already.
.torch_room
{
    LDX hand
    LDA kind_places,X
    CMP #TILE_TORCH
    CLC
    BNE done
    LDA torch_count
    CMP #TORCH_MAX
.done
    RTS
}

\ If the hand is the torches, set target_x/y to the tile at the middle of
\ the player's box, where a torch goes with nowhere else to go, and return
\ carry clear if it is empty (air or sky); otherwise carry set.
.torch_own_tile
{
    LDX hand
    LDA kind_places,X
    CMP #TILE_TORCH
    BNE none
    JSR player_pixels
    JSR middle_column
    CLC
    LDA zp_box_y
    ADC #PLAYER_HEIGHT DIV 2
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
    STA target_y
    JSR target_tile
    CMP #TILE_AIR
    BEQ empty
    CMP #TILE_SKY
    BEQ empty
.none
    SEC
    RTS
.empty
    CLC
    RTS
}

\ Tile (X, Y) has changed: flood again each torch within its reach, and
\ relight the tiles around it.
.torch_tile_changed
{
    STX torch_change_x
    STY torch_change_y
    LDX #0
.loop
    CPX torch_count
    BEQ done
    LDA torch_x,X               \ Within MINER_RADIUS each way?
    SEC
    SBC torch_change_x
    CLC
    ADC #MINER_RADIUS
    CMP #MINER_SPAN
    BCS next
    LDA torch_y,X
    SEC
    SBC torch_change_y
    CLC
    ADC #MINER_RADIUS
    CMP #MINER_SPAN
    BCS next
    STX torch_index
    JSR torch_flood
    LDX torch_index
    JSR torch_relight
    LDX torch_index
.next
    INX
    BNE loop
.done
    RTS
}

\ Point sl_ptr at torch X's pool.
.torch_pool_pointer
{
    LDA torch_pool_low,X
    STA sl_ptr
    LDA torch_pool_high,X
    STA sl_ptr + 1
    RTS
}

\ Flood torch X's pool, as the miner's (the flood's own pool is scratch).
.torch_flood
{
    LDA sl_cx
    PHA
    LDA sl_cy
    PHA
    LDA torch_x,X
    STA sl_cx
    LDA torch_y,X
    STA sl_cy
    TXA
    PHA
    JSR sl_flood_pool
    PLA
    TAX
    PLA
    STA sl_cy
    PLA
    STA sl_cx
    JSR torch_pool_pointer
    LDY #MINER_WINDOW - 1
.copy
    LDA sl_pool,Y
    STA (sl_ptr),Y
    DEY
    BPL copy
    RTS
}

\ Gather the torches in tiles gather_left-gather_right across and
\ gather_top-gather_bottom down (inclusive).
.torch_gather
{
    LDY #0
    LDX #0
.loop
    CPX torch_count
    BEQ done
    LDA torch_x,X
    CMP gather_left
    BCC next
    CMP gather_right
    BEQ across
    BCS next
.across
    LDA torch_y,X
    CMP gather_top
    BCC next
    CMP gather_bottom
    BEQ down
    BCS next
.down
    TXA
    STA torch_near,Y
    INY
.next
    INX
    BNE loop
.done
    STY torch_near_count
    RTS
}

\ Set the gathering rectangle to tiles A-X across and Y-zp_temp down,
\ widened by MINER_RADIUS each way (clamped to the world).
.torch_gather_around
{
    SEC
    SBC #MINER_RADIUS
    BCS left_set
    LDA #0
.left_set
    STA gather_left
    TXA
    CLC
    ADC #MINER_RADIUS
    BCC right_set
    LDA #&FF
.right_set
    STA gather_right
    TYA
    SEC
    SBC #MINER_RADIUS
    BCS top_set
    LDA #0
.top_set
    STA gather_top
    LDA zp_temp
    CLC
    ADC #MINER_RADIUS
    BCC bottom_set
    LDA #&FF
.bottom_set
    STA gather_bottom
    JMP torch_gather
}

\ The gathered torches' light at tile (zp_fill_x, zp_fill_y), scaled, in A.
.torch_light
{
    LDA #0
    STA torch_best
    LDY #0
.loop
    CPY torch_near_count
    BEQ done
    LDX torch_near,Y
    LDA zp_fill_x               \ Its offset from the torch, if in its pool
    SEC
    SBC torch_x,X
    CLC
    ADC #MINER_RADIUS
    CMP #MINER_SPAN
    BCS next
    STA torch_dx
    LDA zp_fill_y
    SEC
    SBC torch_y,X
    CLC
    ADC #MINER_RADIUS
    CMP #MINER_SPAN
    BCS next
    STY torch_save_y
    TAY
    LDA times_span,Y
    ADC torch_dx                \ Carry clear
    TAY
    LDA miner_index,Y           \ The window entry
    PHA
    JSR torch_pool_pointer
    PLA
    TAY
    LDA (sl_ptr),Y
    LDY torch_save_y
    CMP torch_best
    BCC next
    STA torch_best
.next
    INY
    BNE loop
.done
    LDA torch_best
    ASSERT LIGHT_SCALE = 16
    ASL A
    ASL A
    ASL A
    ASL A
    RTS
}

\ Relight the tiles within MINER_RADIUS of torch X that are in the tile
\ cache: daylight, or the torches' light where brighter. Queue those whose
\ light changes.
.torch_relight
{
    LDA torch_y,X               \ The torches whose light reaches its pool
    CLC
    ADC #MINER_RADIUS
    STA zp_temp
    LDA torch_y,X
    SEC
    SBC #MINER_RADIUS
    TAY
    LDA torch_x,X
    CLC
    ADC #MINER_RADIUS
    PHA
    LDA torch_x,X
    SEC
    SBC #MINER_RADIUS
    TAX
    PLA
    STX zp_temp + 1
    TAX
    LDA zp_temp + 1
    JSR torch_gather_around
    LDX torch_index
    LDA torch_y,X
    SEC
    SBC #MINER_RADIUS
    STA torch_row
    LDA #MINER_SPAN
    STA torch_rows
    LDX torch_index
.row
    LDA torch_x,X
    SEC
    SBC #MINER_RADIUS
    STA torch_column
    LDA #MINER_SPAN
    STA torch_columns
.column
    LDA torch_row               \ In the tile cache?
    CMP cached_top
    BCC next
    CMP cached_bottom
    BEQ down_inside
    BCS next
.down_inside
    LDA torch_column
    CMP cached_left
    BCC next
    CMP cached_right
    BEQ inside
    BCS next
.inside
    STA zp_fill_x
    LDA torch_row
    STA zp_fill_y
    JSR sun_daylight            \ Daylight, or the torches' light
    STA torch_new
    JSR torch_light
    CMP torch_new
    BCC lit
    STA torch_new
.lit
    JSR para_cache_pointer      \ Changed?
    LDA para_cache + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA torch_new
    CMP (para_cache),Y
    BEQ next
    LDX torch_queue_tail        \ Queue it, if there is room: its new light
    STA torch_queue_light,X     \ goes into the tile cache when it is sent,
    LDA zp_fill_x               \ as the host draws it
    STA torch_queue_x,X
    LDA zp_fill_y
    STA torch_queue_y,X
    INX
    TXA
    AND #TORCH_QUEUE - 1
    CMP torch_queue_head
    BEQ next
    STA torch_queue_tail
.next
    INC torch_column
    DEC torch_columns
    BNE column
    LDX torch_index
    INC torch_row
    DEC torch_rows
    BEQ done
    JMP row
.done
    RTS
}

\ Light the tiles just filled into the tile cache (a strip from
\ (para_strip_x, para_strip_y), para_count long, down if para_strip_down)
\ by any torches near them.
.torch_light_strip
{
    LDA torch_count
    BEQ done
    LDA para_count              \ The torches whose light reaches the strip
    SEC
    SBC #1
    LDX para_strip_down
    BNE gather_down
    CLC                         \ Along a row
    ADC para_strip_x
    TAX
    LDA para_strip_y
    STA zp_temp
    TAY
    LDA para_strip_x
    JMP gather
.gather_down
    CLC                         \ Down a column
    ADC para_strip_y
    STA zp_temp
    LDX para_strip_x
    LDY para_strip_y
    TXA
.gather
    JSR torch_gather_around
    LDA torch_near_count
    BEQ done
    LDA para_strip_x
    STA zp_fill_x
    LDA para_strip_y
    STA zp_fill_y
    LDA para_count
    STA torch_columns
.tile
    JSR torch_light
    STA torch_new
    JSR para_cache_pointer
    LDA para_cache + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA torch_new
    CMP (para_cache),Y
    BCC next
    STA (para_cache),Y
.next
    LDA para_strip_down
    BNE step_down
    INC zp_fill_x
    JMP stepped
.step_down
    INC zp_fill_y
.stepped
    DEC torch_columns
    BNE tile
.done
    RTS
}

.torch_pool_low
FOR n, 0, TORCH_MAX - 1
    EQUB LO(torch_pools + n * MINER_WINDOW)
NEXT
.torch_pool_high
FOR n, 0, TORCH_MAX - 1
    EQUB HI(torch_pools + n * MINER_WINDOW)
NEXT
