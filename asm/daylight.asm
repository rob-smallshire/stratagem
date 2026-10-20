\ Daylight, on the parasite (docs/tube-game.md): lighting.shaft_sun, and the
\ glow. Each column's sky depth (its first opaque tile) is kept for the whole
\ world in sun_depth. An open tile is lit fully above its column's sky depth,
\ else from the nearest column within SHAFT_REACH open to the sky at its
\ row; a wall at its column's sky depth and below it, from a column open to
\ the sky beside it, and, as a floor, as brightly as the open tile above it;
\ then a level less for each SHAFT_TAPER tiles below its column's surface,
\ so that it dims slowly down a shaft. Light reaches a tile only through
\ open tiles, and then, if the tile is a wall, through walls: never through
\ a wall into the open again, so a roofed hut is dark inside. A tile's
\ daylight is the brighter of that and the glow (lighting.glow).
\
\ Daylight is worked out as tiles enter the tile cache. A change to the
\ world relights the tiles around it (more if it changes its column's sky
\ depth), some each frame: those in the tile cache whose light changes are queued,
\ as the torches' are, to be sent to the host.

SUN_CLEAR = &80
SUN_ROWS_PER_FRAME = 1          \ Rows of relighting a frame
SUN_QUEUE_ROOM = 2 * SHAFT_REACH + 2    \ Free queue entries to relight a row
SUN_DARK = SHAFT_WALL_REACH     \ Rows below a nearby sky depth still lit

ASSERT SHAFT_WALL_REACH = SHAFT_REACH AND SHAFT_REACH = 4

\ Every column's sky depth (the generator opens no column to the sky below
\ the surface, so the search starts there), and its reaches.
.sun_init
{
    LDX #0
.column
    LDY world_heights,X
    CPX #0                      \ The edges are bedrock to the top
    BEQ edge
    CPX #&FF
    BNE scan
.edge
    LDY #0
.scan
    JSR sun_scan
    INX
    BNE column
.near
    JSR sun_near
    INX
    BNE near
    LDA #0
    STA sun_busy
    RTS
}

\ Set column X's sky depth: its first opaque tile from row Y down.
\ Preserves X.
.sun_scan
{
.loop
    JSR sun_clear_at
    BEQ found
    CPY #&FF
    BEQ found
    INY
    BNE loop                    \ Always branches
.found
    TYA
    STA sun_depth,X
    RTS
}

\ Set column X's reaches: sun_reach_1 to sun_reach_4, the deepest sky depth
\ within that many columns of it. Preserves X.
.sun_near
{
    STX sun_save_x
    LDA sun_depth,X
    STA sun_tmp
    LDY #0
.reach
    STY sun_count
    LDA sun_save_x              \ The columns Y + 1 away, either side
    CLC
    SBC sun_count
    BCC left_done
    TAX
    LDA sun_depth,X
    CMP sun_tmp
    BCC left_done
    STA sun_tmp
.left_done
    LDA sun_save_x
    SEC
    ADC sun_count
    BCS right_done
    TAX
    LDA sun_depth,X
    CMP sun_tmp
    BCC right_done
    STA sun_tmp
.right_done
    LDX sun_save_x
    LDA sun_tmp
    LDY sun_count
    BNE not_1
    STA sun_reach_1,X
.not_1
    CPY #1
    BNE not_2
    STA sun_reach_2,X
.not_2
    CPY #2
    BNE not_3
    STA sun_reach_3,X
.not_3
    CPY #3
    BNE not_4
    STA sun_reach_4,X
.not_4
    INY
    CPY #SHAFT_REACH
    BNE reach
    RTS
}

\ SUN_CLEAR in A if tile (X, Y) lets light through, otherwise 0 (and Z
\ set). Preserves X and Y.
.sun_clear_at
{
    JSR tile_at
    STX sun_save_x
    TAX
    LDA material_passable,X
    BNE clear
    LDA zp_world_shape
    AND #SHAPE_BITS             \ Partly dug
    BEQ done
.clear
    LDA #SUN_CLEAR
.done
    LDX sun_save_x
    CMP #0
    RTS
}

\ SUN_CLEAR in A if tile (X, Y) lets light through, otherwise 0 (and Z
\ set): from the tile cache where it holds the tile (sun_bounds), otherwise
\ from the world. Preserves X and Y.
.sun_clear_xy
{
    CPX sun_safe_l
    BCC world
    CPX sun_safe_r
    BEQ across
    BCS world
.across
    CPY sun_safe_t
    BCC world
    CPY sun_safe_b
    BEQ cached
    BCS world
.cached
    STX sun_save_x
    STY sun_save_y
    TYA
    JSR sl_cache_row
    TXA
    AND #TILE_CACHE_SIZE - 1
    TAY
    LDA (sl_map_ptr),Y
    TAX
    LDA material_passable,X
    BNE clear
    LDA (sl_shape_ptr),Y
    AND #SHAPE_BITS             \ Partly dug
    BEQ done
.clear
    LDA #SUN_CLEAR
.done
    LDX sun_save_x
    LDY sun_save_y
    CMP #0
    RTS
.world
    JMP sun_clear_at
}

\ The distance in Y (1 to SHAFT_REACH) to the nearest column beside column
\ X (sun_x) open to the sky at row A (sun_y), or 0 if none, whatever lies
\ between: no column is nearer by sun_walk. Preserves X.
.sun_nearest
{
    LDY #1
    CMP sun_reach_1,X
    BCC found
    INY
    CMP sun_reach_2,X
    BCC found
    INY
    CMP sun_reach_3,X
    BCC found
    INY
    CMP sun_reach_4,X
    BCC found
    LDY #0
.found
    RTS
}

\ The distance in Y (1 to sun_most) to the nearest column open to the sky
\ at row sun_y, reached from tile (sun_x, sun_y) along the row through open
\ tiles (after walls, if sun_wall is set: from a wall), or 0 if none. Finds
\ the nearest such column each way (side X: 0 leftwards, 1 rightwards) from
\ the sky depths, then reads the tiles between, the nearer side first.
.sun_walk
{
    LDX #1
.find
    LDA sun_x
    LDY #0
.look
    INY
    CPY sun_most
    BEQ in_reach
    BCS none_here
.in_reach
    CMP sun_walk_edge,X
    BEQ none_here
    CLC
    ADC sun_walk_step,X
    STA sun_column
    STX sun_side
    TAX
    LDA sun_y
    CMP sun_depth,X
    LDX sun_side
    BCC found
    LDA sun_column
    JMP look
.none_here
    LDY #0
.found
    TYA
    STA sun_target,X
    DEX
    BPL find
    LDX #0                      \ The nearer first
    LDA sun_target + 1
    BEQ first
    LDA sun_target
    BEQ second
    CMP sun_target + 1
    BCC first
.second
    LDX #1
.first
    LDA sun_target,X
    BEQ none
    JSR sun_path
    BCS reached
    TXA                         \ Then the other
    EOR #1
    TAX
    LDA sun_target,X
    BEQ none
    JSR sun_path
    BCS reached
.none
    LDY #0
    RTS
.reached
    LDY sun_target,X
    RTS
}
.sun_walk_edge
    EQUB 0, &FF                 \ The world's edges
.sun_walk_step
    EQUB &FF, 1

\ Carry set if light passes along row sun_y from sun_x, side X, to the
\ column sun_target,X away, as sun_walk. Preserves X.
.sun_path
{
    STX sun_side
    LDA sun_wall
    STA sun_in_wall
    LDA sun_target,X
    STA sun_dist
    LDA sun_x
    STA sun_column
.loop
    DEC sun_dist
    BEQ passes
    LDX sun_side
    LDA sun_column
    CLC
    ADC sun_walk_step,X
    STA sun_column
    TAX
    LDY sun_y
    JSR sun_clear_xy
    BEQ wall
    LDA #0                      \ Open: no further walls
    STA sun_in_wall
    BEQ loop                    \ Always branches
.wall
    LDA sun_in_wall
    BNE loop
    LDX sun_side
    CLC
    RTS
.passes
    LDX sun_side
    SEC
    RTS
}

\ The sunlight of an open tile at (sun_x, sun_y), in A.
.sun_open
{
    LDX sun_x
    LDA sun_y
    CMP sun_depth,X
    BCC full                    \ Open to the sky
    JSR sun_nearest
    CPY #0
    BEQ dark
    LDA #0
    STA sun_wall
    LDA #SHAFT_REACH
    STA sun_most
    JSR sun_walk
    LDA sun_side_open,Y
    RTS
.dark
    LDA #0
    RTS
.full
    LDA #LIGHT_FULL
    RTS
}

\ The sunlight of tile (zp_fill_x, zp_fill_y), in A.
.sun_tile
{
    LDA zp_fill_x
    STA sun_x
    TAX
    LDA zp_fill_y
    STA sun_y
    SEC                         \ Too far below every sky depth near it?
    SBC sun_reach_4,X
    BCC near
    CMP #SUN_DARK
    BCC near
    LDA #0
    RTS
.near
    LDA sun_y                   \ Above the sky depth: open, and full
    CMP sun_depth,X
    BCS below
    LDA #LIGHT_FULL
    RTS
.below
    LDY sun_y
    JSR sun_clear_xy
    BEQ wall
    JMP sun_open
.wall
    LDA #0
    STA sun_best
    LDA sun_y                   \ Soaked down from the sky depth, through
    SEC                         \ walls only
    SBC sun_depth,X
    CMP #SUN_DARK
    BCS beside
    TAY
    LDA sun_wall_levels,Y
    STA sun_level
    LDY sun_y
.up
    TYA
    CMP sun_depth,X
    BEQ soaked
    CPY sun_y                   \ (The tile itself is a wall)
    BEQ step
    JSR sun_clear_xy
    BNE beside
.step
    DEY
    JMP up
.soaked
    LDA sun_level
    STA sun_best
.beside
    LDA sun_y                   \ From a column open to the sky beside it,
    JSR sun_nearest             \ through walls then open tiles
    CPY #0
    BEQ floor
    LDA #&FF
    STA sun_wall
    LDA #SHAFT_WALL_REACH
    STA sun_most
    JSR sun_walk
    LDA sun_side_wall,Y
    CMP sun_best
    BCC floor
    STA sun_best
.floor
    LDA sun_y                   \ A floor: lit as the open tile above
    BEQ done
    TAY
    DEY
    LDX sun_x
    JSR sun_clear_xy
    BEQ done
    DEC sun_y
    JSR sun_open
    CMP sun_best
    BCC done
    STA sun_best
.done
    LDA sun_best
    RTS
}

\ The daylight of tile (zp_fill_x, zp_fill_y), in the tile cache, scaled, in
\ A: the brighter of its sunlight, a level less for each SHAFT_TAPER tiles
\ it is below its column's surface, and the glow (below the surface only:
\ LIGHT_FULL - GLOW_LOSS a tile below it, then a level less a tile deeper).
.sun_daylight
{
    JSR sun_tile
    STA sun_level
    LDX zp_fill_x
    LDA zp_fill_y
    SEC
    SBC world_heights,X
    BCC covered
    BEQ covered
    STA sun_tmp
    LSR A                       \ The taper
    LSR A
    ASSERT SHAFT_TAPER = 4
    STA sun_taper
    LDA sun_level
    SEC
    SBC sun_taper
    BCS tapered
    LDA #0
.tapered
    STA sun_level
    LDA #LIGHT_FULL - GLOW_LOSS
    SEC
    SBC sun_tmp
    BCS glow_set
    LDA #0
    BEQ glow_set                \ Always branches
.covered
    LDA #0                      \ At or above the surface: no glow
.glow_set
    CMP sun_level
    BCS brighter
    LDA sun_level
.brighter
    ASSERT LIGHT_SCALE = 16
    ASL A
    ASL A
    ASL A
    ASL A
    RTS
}

\ Light the tiles just filled into the tile cache (a strip from
\ (para_strip_x, para_strip_y), para_count long, down if para_strip_down)
\ by daylight.
.sun_light_strip
{
    LDA para_strip_x
    STA zp_fill_x
    LDA para_strip_y
    STA zp_fill_y
    LDA para_count
    STA sun_count
.tile
    JSR sun_daylight
    STA sun_new
    JSR para_cache_pointer
    LDA para_cache + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA sun_new
    STA (para_cache),Y
    LDA para_strip_down
    BNE step_down
    INC zp_fill_x
    JMP stepped
.step_down
    INC zp_fill_y
.stepped
    DEC sun_count
    BNE tile
    RTS
}

\ Tile (X, Y) has changed (sun_was_clear: whether it let light through
\ before): if it now lets light through differently, its column's sky
\ depth, and the tiles to relight,
\ SHAFT_REACH either side: if the sky depth is the same, those whose way
\ along a row may cross it (its row, and the floors below it) and those
\ below it soaked through it, to SUN_DARK below the sky depth; otherwise
\ from the highest of the tile and the old and new sky depths, to SUN_DARK
\ below the lowest.
.sun_tile_changed
{
    STX sun_x
    STY sun_y
    LDA sun_depth,X
    STA sun_old_depth
    JSR sun_clear_at
    CMP sun_was_clear           \ Lets light through as before: no change
    BNE changed
    RTS
.changed
    CMP #0
    BEQ opaque
    TYA                         \ Opened at the sky depth: look further down
    CMP sun_depth,X
    BNE depth_set
    JSR sun_scan
    JMP depth_set
.opaque
    TYA                         \ Closed above it: the new sky depth
    CMP sun_depth,X
    BCS depth_set
    STA sun_depth,X
.depth_set
    LDA sun_depth,X
    CMP sun_old_depth
    BEQ near_done
    TXA                         \ The reaches of each column it reaches
    SEC
    SBC #SHAFT_REACH
    BCS near_from
    LDA #0
.near_from
    TAX
    LDA sun_x
    CLC
    ADC #SHAFT_REACH
    BCC near_to
    LDA #&FF
.near_to
    STA sun_near_to
.near
    JSR sun_near
    CPX sun_near_to
    BEQ near_done
    INX
    BNE near                    \ Always branches
.near_done
    LDX sun_x
    LDA sun_x                   \ The tiles to relight
    SEC
    SBC #SHAFT_REACH
    BCS left_set
    LDA #0
.left_set
    STA sun_req_l
    LDA sun_x
    CLC
    ADC #SHAFT_REACH
    BCC right_set
    LDA #&FF
.right_set
    STA sun_req_r
    LDA sun_depth,X
    CMP sun_old_depth
    BNE depth_changed
    LDA sun_y                   \ The same: from the tile
    STA sun_req_t
    CLC                         \ To the floor below it, or SUN_DARK below
    ADC #1                      \ the sky depth
    BCS bottom_max
    STA sun_tmp
    LDA sun_depth,X
    CLC
    ADC #SUN_DARK - 1
    BCS bottom_max
    CMP sun_tmp
    BCS bottom_set
    LDA sun_tmp
    BCC bottom_set              \ Always branches
.depth_changed
    LDA sun_y                   \ From the highest
    CMP sun_old_depth
    BCC top_old
    LDA sun_old_depth
.top_old
    CMP sun_depth,X
    BCC top_set
    LDA sun_depth,X
.top_set
    STA sun_req_t
    LDA sun_y                   \ To the lowest, and SUN_DARK below
    CMP sun_old_depth
    BCS bottom_old
    LDA sun_old_depth
.bottom_old
    CMP sun_depth,X
    BCS bottom_from
    LDA sun_depth,X
.bottom_from
    CLC
    ADC #SUN_DARK
    BCC bottom_set
.bottom_max
    LDA #&FF
.bottom_set
    STA sun_req_b
    \ Fall through
}

\ Add tiles sun_req_l-sun_req_r across, sun_req_t-sun_req_b down, to those
\ to relight: the rectangle sun_l/r/t/b, from row sun_row down.
.sun_request
{
    LDA sun_busy
    BNE merge
    LDA sun_req_l
    STA sun_l
    LDA sun_req_r
    STA sun_r
    LDA sun_req_t
    STA sun_row
    LDA sun_req_b
    STA sun_b
    LDA #&FF
    STA sun_busy
    RTS
.merge
    LDA sun_req_l               \ Widened across: relight what was done too
    CMP sun_l
    BCS left_kept
    STA sun_l
    LDA sun_req_t
    STA sun_row
.left_kept
    LDA sun_r
    CMP sun_req_r
    BCS right_kept
    LDA sun_req_r
    STA sun_r
    LDA sun_req_t
    STA sun_row
.right_kept
    LDA sun_b
    CMP sun_req_b
    BCS bottom_kept
    LDA sun_req_b
    STA sun_b
.bottom_kept
    LDA sun_req_t
    CMP sun_row
    BCS done
    STA sun_row
.done
    RTS
}

\ Relight SUN_ROWS_PER_FRAME rows of the rectangle, while the torch queue
\ has room: queue the tiles in the tile cache whose light (the brighter of
\ daylight and the torches') differs from it.
.sun_step
{
    LDA sun_busy
    BNE work
    RTS
.work
    LDA sun_l                   \ The torches near the rectangle
    LDX sun_r
    LDY sun_b
    STY zp_temp
    LDY sun_row
    JSR torch_gather_around
    LDA #SUN_ROWS_PER_FRAME
    STA sun_rows_left
.row
    LDA torch_queue_head        \ Free entries: head - tail - 1
    CLC
    SBC torch_queue_tail
    AND #TORCH_QUEUE - 1
    CMP #SUN_QUEUE_ROOM
    BCS room
    RTS
.room
    LDA sun_row                 \ Past the last row, or the cache's?
    CMP sun_b
    BEQ inside
    BCS past
.inside
    CMP cached_bottom
    BEQ in_cache
    BCC in_cache
.past
    JMP finished
.in_cache
    CMP cached_top
    BCC next
    STA zp_fill_y
    LDA sun_l
    CMP cached_left
    BCS left_set
    LDA cached_left
.left_set
    STA zp_fill_x
    LDA sun_r
    CMP cached_right
    BCC right_set
    LDA cached_right
.right_set
    STA sun_to
    CMP zp_fill_x
    BCC next
.tile
    JSR sun_daylight
    STA sun_new
    LDA torch_near_count
    BEQ torches_done
    JSR torch_light
    CMP sun_new
    BCC torches_done
    STA sun_new
.torches_done
    JSR para_cache_pointer
    LDA para_cache + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA sun_new
    CMP (para_cache),Y
    BEQ tile_done
    LDX torch_queue_tail        \ Queue it
    STA torch_queue_light,X
    LDA zp_fill_x
    STA torch_queue_x,X
    LDA zp_fill_y
    STA torch_queue_y,X
    INX
    TXA
    AND #TORCH_QUEUE - 1
    STA torch_queue_tail
.tile_done
    LDA zp_fill_x
    CMP sun_to
    BEQ next
    INC zp_fill_x
    BNE tile                    \ Always branches
.next
    INC sun_row
    BEQ finished
    DEC sun_rows_left
    BEQ out
    JMP row
.out
    RTS
.finished
    LDA #0
    STA sun_busy
    RTS
}

\ Sunlight by distance from a column open to the sky: an open tile's, and a
\ wall's beside it (lighting.shaft_sun)
.sun_side_open
    EQUB 0
FOR d, 1, SHAFT_REACH
    EQUB LIGHT_FULL - SHAFT_SIDE_STEP * d
NEXT
.sun_side_wall
    EQUB 0
FOR d, 1, SHAFT_REACH
    EQUB LIGHT_FULL - SUN_WALL_STEP * (d - 1)
NEXT
\ And a wall's, by depth below its own column's sky depth
.sun_wall_levels
FOR d, 0, SUN_DARK - 1
    EQUB LIGHT_FULL - SUN_WALL_STEP * d
NEXT
