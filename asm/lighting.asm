\ Light: the miner's light, combined with the stand-in daylight in the tile
\ cache's light plane (modelled by tools/stratagem/lighting.py: miner_light
\ and lit_level).
\
\ A pass works out the miner's pool of light over a window around the
\ miner's tile, then sets the light plane over the window at the last pass
\ and the window now, queueing a redraw for each tile whose light changed.
\ It runs only when the miner has moved to another tile or tiles have
\ changed (light_dirty: dug, placed, or newly in the cache), and only
\ within the tile cache, which holds exactly the view's tiles.

\ Bring the light plane up to date with the miner and the tiles.
.update_light
{
    JSR player_pixels           \ The tile at the middle of the player's box
    CLC
    LDA zp_box_x
    ADC #PLAYER_WIDTH DIV 2
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
    STA miner_x
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
    STA miner_y
    LDA light_dirty
    BNE changed
    LDA light_valid
    BEQ changed
    LDA miner_x
    CMP light_x
    BNE changed
    LDA miner_y
    CMP light_y
    BNE changed
    RTS
.changed
    LDA #0
    STA light_dirty
    JSR compute_pool
    LDA light_valid             \ Where the pool was, then where it is
    BEQ new_window
    LDA light_x
    STA window_x
    LDA light_y
    STA window_y
    JSR apply_window
.new_window
    LDA miner_x
    STA light_x
    STA window_x
    LDA miner_y
    STA light_y
    STA window_y
    LDA #&FF
    STA light_valid
    JMP apply_window
}

\ Work out the pool of light around (miner_x, miner_y), nearest first: each
\ tile from its neighbours one step nearer the miner.
.compute_pool
{
    LDX #0
.loop
    STX pool_index
    CLC
    LDA miner_x
    ADC miner_dx,X
    STA light_tile_x
    CLC
    LDA miner_y
    ADC miner_dy,X
    STA light_tile_y
    TAY
    LDX light_tile_x
    JSR light_in_cache
    LDX pool_index
    BCS inside
    LDA #0                      \ Outside the cache: dark, and stops light
    STA pool,X
    STA pool_clear,X
    JMP next
.inside
    CPX #0
    BNE not_centre
    LDA #MINER_LEVEL            \ The miner's own tile, which lets light out
    STA pool
    LDA #&FF
    STA pool_clear
    JMP next
.not_centre
    LDX light_tile_x            \ Clear if passable or partly dug away
    JSR light_cache_pointer
    LDY #0
    LDA (zp_ptr),Y
    TAX
    LDA material_passable,X
    BNE clear
    LDA zp_ptr + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA zp_ptr + 1
    LDA (zp_ptr),Y
    AND #SHAPE_BITS
    BEQ opaque
.clear
    LDA #&FF
.opaque
    STA pool_clear_here
    LDA #0
    STA pool_best
    LDX pool_index
    LDA miner_across,X
    JSR from_orthogonal
    LDX pool_index
    LDA miner_vertical,X
    JSR from_orthogonal
    LDA pool_clear_here         \ Diagonally only into an open tile, from an
    BEQ store                   \ open one, past an open corner
    LDX pool_index
    LDY miner_diagonal,X
    CPY #LIGHT_NO_TILE
    BEQ store
    LDA pool_clear,Y
    BEQ store
    LDA miner_across,X          \ A diagonal entry has both corners
    TAY
    LDA pool_clear,Y
    BNE corner_open
    LDA miner_vertical,X
    TAY
    LDA pool_clear,Y
    BEQ store
.corner_open
    LDY miner_diagonal,X
    LDA pool,Y
    SEC
    SBC #LIGHT_OPEN_DIAGONAL_STEP
    JSR consider
.store
    LDX pool_index
    LDA pool_best
    STA pool,X
    LDA pool_clear_here
    STA pool_clear,X
.next
    LDX pool_index
    INX
    CPX #MINER_WINDOW
    BEQ done
    JMP loop
.done
    RTS
}

\ Light from window entry A (or none, LIGHT_NO_TILE), an orthogonal
\ neighbour one step nearer the miner, into the entry at pool_index: from an
\ open tile into an open one, less LIGHT_OPEN_STEP; into a wall's face,
\ undimmed; from wall to wall, less LIGHT_WALL_STEP; never out of a wall.
.from_orthogonal
{
    CMP #LIGHT_NO_TILE
    BEQ done
    TAY
    LDA pool_clear,Y
    BEQ from_wall
    LDA pool,Y
    LDX pool_clear_here
    BEQ into_wall
    SEC
    SBC #LIGHT_OPEN_STEP
    JMP consider
.into_wall
    SEC
    JMP consider
.from_wall
    LDA pool_clear_here
    BNE done
    LDA pool,Y
    SEC
    SBC #LIGHT_WALL_STEP
    JMP consider
.done
    RTS
}

\ Keep A as pool_best if it is brighter, unless the subtraction that made it
\ went below zero (carry clear).
.consider
{
    BCC done
    CMP pool_best
    BCC done
    STA pool_best
.done
    RTS
}

\ Set the light plane over the window centred on (window_x, window_y): each
\ tile the brighter of daylight and the pool (if within it). Queue each tile
\ whose light changes for redrawing.
.apply_window
{
    LDX #0
.loop
    STX pool_index
    CLC
    LDA window_x
    ADC miner_dx,X
    STA light_tile_x
    CLC
    LDA window_y
    ADC miner_dy,X
    STA light_tile_y
    TAY
    LDX light_tile_x
    JSR light_in_cache
    BCC next
    JSR light_fixed
    STA pool_best
    TXA                         \ The offset from the miner, if within the pool
    SEC
    SBC miner_x
    CLC
    ADC #MINER_RADIUS
    CMP #MINER_SPAN
    BCS lit
    STA zp_temp
    TYA
    SEC
    SBC miner_y
    CLC
    ADC #MINER_RADIUS
    CMP #MINER_SPAN
    BCS lit
    TAX
    LDA times_span,X
    CLC
    ADC zp_temp
    TAX
    LDY miner_index,X
    LDA pool,Y
    CMP pool_best
    BCC lit
    STA pool_best
.lit
    LDX light_tile_x
    LDY light_tile_y
    JSR light_cache_pointer
    LDA zp_ptr + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache)
    STA zp_ptr + 1
    LDA pool_best
    ASSERT LIGHT_SCALE = 16
    ASL A
    ASL A
    ASL A
    ASL A
    LDY #0
    CMP (zp_ptr),Y
    BEQ next
    STA (zp_ptr),Y
    LDX light_queue_count
    LDA light_tile_x
    STA light_queue_x,X
    LDA light_tile_y
    STA light_queue_y,X
    INC light_queue_count
.next
    LDX pool_index
    INX
    CPX #MINER_WINDOW
    BEQ done
    JMP loop
.done
    RTS
}

\ Carry set if tile (X, Y) is in the tile cache. Preserves X and Y.
.light_in_cache
{
    CPX cached_left
    BCC out
    CPX cached_right
    BEQ across
    BCS out
.across
    CPY cached_top
    BCC out
    CPY cached_bottom
    BEQ inside
    BCS out
.inside
    SEC
    RTS
.out
    CLC
    RTS
}

\ Point zp_ptr at the material of tile (X, Y) in the tile cache.
\ Preserves X and Y.
.light_cache_pointer
{
    TYA
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA zp_ptr + 1
    TYA
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_ptr
    TXA
    AND #TILE_CACHE_SIZE - 1
    ORA zp_ptr
    STA zp_ptr
    RTS
}

\ The level daylight alone gives tile (X, Y), in A: lighting.fixed_light.
\ Preserves X and Y.
.light_fixed
{
    TYA
    SEC
    SBC surface_heights,X       \ The depth below the surface
    BCC full                    \ Above it
    BEQ full                    \ At it
    CMP #LIGHT_FULL - LIGHT_FIXED_FLOOR
    BCS floor
    EOR #&FF                    \ LIGHT_FULL - depth
    CLC
    ADC #LIGHT_FULL + 1
    RTS
.floor
    LDA #LIGHT_FIXED_FLOOR
    RTS
.full
    LDA #LIGHT_FULL
    RTS
}

\ Redraw the tiles whose light changed, and empty the queue.
.redraw_light_queue
{
    LDA #0
    STA light_queue_index
.loop
    LDX light_queue_index
    CPX light_queue_count
    BEQ done
    LDA light_queue_x,X
    STA target_x
    LDA light_queue_y,X
    STA target_y
    JSR redraw_target
    INC light_queue_index
    JMP loop
.done
    LDA #0
    STA light_queue_count
    RTS
}

INCLUDE "build/generated/miner.asm"
