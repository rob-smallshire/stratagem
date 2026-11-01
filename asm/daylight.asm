\ Daylight, on the parasite (docs/tube-game.md): lighting.shaft_sun, and the
\ glow. Each column's sky depth (its first opaque tile) is kept for the whole
\ world in sun_depth. An open tile is lit fully above its column's sky depth,
\ else from the nearest column within SHAFT_REACH open to the sky at its
\ row; a wall at its column's sky depth and below it, from a column open to
\ the sky beside it, and, as a floor, as brightly as the open tile above it;
\ then a level less for each SHAFT_TAPER tiles below its column's surface,
\ so that it dims slowly down a shaft. A tile's daylight is the brighter of
\ that and the glow (lighting.glow).
\
\ Daylight is worked out as tiles enter the tile cache. A change to the
\ world relights the tiles around the columns whose sky depth it changes,
\ some each frame: those in the tile cache whose light changes are queued,
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
    TYA                         \ The sky floor: the surface, as generated
    STA sky_floor,X
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

\ Point sun_ptr and sun_shape at row zp_fill_y of the tile cache's
\ materials and shapes, and Y at column zp_fill_x in them.
.sun_cache_point
{
    LDA zp_fill_y               \ tile_cache + (y MOD 32) * 32
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA sun_ptr + 1
    ADC #HI(tile_cache_shapes - tile_cache)
    STA sun_shape + 1
    LDA zp_fill_y
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA sun_ptr
    STA sun_shape
    LDA zp_fill_x
    AND #TILE_CACHE_SIZE - 1
    TAY
    RTS
}

\ Move sun_ptr and sun_shape up a row, wrapping within the tile cache.
\ Preserves Y.
.sun_cache_up
{
    LDA sun_ptr
    SEC
    SBC #TILE_CACHE_SIZE
    STA sun_ptr
    STA sun_shape
    BCS done
    LDA sun_ptr + 1
    SBC #0                      \ Carry clear: less 1
    CMP #HI(tile_cache)
    BCS high_set
    ADC #HI(TILE_CACHE_SIZE * TILE_CACHE_SIZE)
.high_set
    STA sun_ptr + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA sun_shape + 1
.done
    RTS
}

\ SUN_CLEAR in A if the tile cache's tile at sun_ptr and sun_shape, column
\ Y, lets light through, otherwise 0 (and Z set). Preserves Y.
.sun_clear_here
{
    LDA (sun_ptr),Y
    TAX
    LDA material_passable,X
    BNE clear
    LDA (sun_shape),Y
    AND #SHAPE_BITS             \ Partly dug
    BEQ done
.clear
    LDA #SUN_CLEAR
.done
    RTS
}

\ The distance in Y (1 to SHAFT_REACH) to the nearest column beside column
\ X (sun_x) open to the sky at row A (sun_y), or 0 if none. Preserves X.
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

\ The sunlight of an open tile at (sun_x, sun_y), in A.
.sun_open
{
    LDX sun_x
    LDA sun_y
    CMP sun_depth,X
    BCC full                    \ Open to the sky
    JSR sun_nearest
    LDA sun_side_open,Y
    RTS
.full
    LDA #LIGHT_FULL
    RTS
}

\ The sunlight of tile (zp_fill_x, zp_fill_y), in the tile cache, in A.
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
    JSR sun_cache_point
    JSR sun_clear_here
    BEQ wall
    LDA sun_y                   \ Open: from the nearest column beside it
    LDX sun_x
    JSR sun_nearest
    LDA sun_side_open,Y
    RTS
.wall
    LDX sun_x
    LDA #0                      \ Below the sky depth
    STA sun_best
    LDA sun_y
    SEC
    SBC sun_depth,X
    BCC beside
    CMP #SUN_DARK
    BCS beside
    TAY
    LDA sun_wall_levels,Y
    STA sun_best
.beside
    LDA sun_y                   \ Beside a column open to the sky
    JSR sun_nearest
    LDA sun_side_wall,Y
    CMP sun_best
    BCC floor
    STA sun_best
.floor
    LDA sun_y                   \ A floor: lit as the open tile above
    BEQ done
    CMP view_top
    BEQ above_outside
    BCC above_outside
    LDA zp_fill_x
    AND #TILE_CACHE_SIZE - 1
    TAY
    JSR sun_cache_up
    JSR sun_clear_here
    JMP above_known
.above_outside
    LDX sun_x
    LDY sun_y
    DEY
    JSR sun_clear_at
.above_known
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
\ it is below its column's surface, and the glow (LIGHT_FULL - GLOW_LOSS
\ down to the surface, then a level less a tile deeper); dimmed by the
\ time of day, sun_dim levels less; and sky in the glow's bands, the
\ DAYNIGHT_BANDS rows above its column's sky floor, brighter by the glow's
\ boost (stratagem.daynight.level).
.sun_daylight
{
    JSR sun_tile
    STA sun_level
    LDX zp_fill_x               \ The surface: as generated, or lower where
    LDA sky_floor,X             \ the sky reaches further down (the row
    BEQ generated               \ above the sky floor; lighting.surface_row)
    SEC
    SBC #1
    CMP world_heights,X
    BCS surface_set
.generated
    LDA world_heights,X
.surface_set
    STA sun_surface
    LDA zp_fill_y
    SEC
    SBC sun_surface
    BCC full
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
.full
    LDA #LIGHT_FULL - GLOW_LOSS
.glow_set
    CMP sun_level
    BCS brighter
    LDA sun_level
.brighter
    SEC                         \ Dimmed
    SBC sun_dim
    BCS dimmed
    LDA #0
.dimmed
    STA sun_level
    LDX zp_fill_x               \ Sky in a band?
    LDA sky_floor,X
    SEC
    SBC zp_fill_y               \ Rows above the sky floor
    BCC lit
    CMP #DAYNIGHT_BANDS + 1
    BCS lit
    SBC #0                      \ (Carry clear: less 1) The band: 0 for rows 0 and 1
    BCS band_set
    LDA #0
.band_set
    ORA sun_boost
    STA sun_tmp
    JSR sun_cache_point
    LDA (sun_ptr),Y
    CMP #TILE_SKY
    BNE lit
    LDX sun_tmp
    LDA sun_level
    CLC
    ADC daynight_band_boosts,X
    CMP #LIGHT_FULL + 1
    BCC boosted
    LDA #LIGHT_FULL
.boosted
    STA sun_level
.lit
    LDA sun_level
    ASSERT LIGHT_SCALE = 16
    ASL A
    ASL A
    ASL A
    ASL A
    RTS
}
ASSERT DAYNIGHT_BANDS = 4

\ The time of day (zp_time's high byte), through daynight_table: the sun's
\ level, as sun_dim, and the glow's boost; when they change, the tile
\ cache is relit (sun_sweep).
.sun_time
{
    LDX zp_time + 1
    LDA daynight_table,X
    CMP sun_applied
    BEQ done
    STA sun_applied
    AND #&0F
    EOR #LIGHT_FULL             \ LIGHT_FULL less the level
    STA sun_dim
    LDA sun_applied
    LSR A
    LSR A
    AND #&0C                    \ The boost, times 4
    STA sun_boost
    LDA #TILE_CACHE_SIZE
    STA sweep_rows
    LDA view_top
    STA sweep_row
    LDA cached_left
    STA sweep_x
.done
    RTS
}
ASSERT LIGHT_FULL = &0F

\ Relight SWEEP_TILES tiles of the tile cache, a row at a time from the
\ view's top, its tiles from the left, wrapping from the cache's bottom to
\ its top, until sweep_rows are done: each tile's daylight, or the torches'
\ light where brighter, queued to be sent where it changes, as the
\ torches' are (torch_relight), and only while the queue has room.
SWEEP_TILES = 4
.sun_sweep
{
    LDA sweep_rows
    BNE sweeping
.idle
    RTS
.sweeping
    LDA torch_queue_head        \ Room: (head - tail - 1) MOD TORCH_QUEUE
    CLC
    SBC torch_queue_tail
    AND #TORCH_QUEUE - 1
    CMP #SWEEP_TILES
    BCC idle
    LDA #SWEEP_TILES
    STA sweep_tiles
.row
    LDA sweep_row               \ In the tile cache? (Else on to the next.)
    CMP cached_top
    BCC next_row
    CMP cached_bottom
    BEQ inside
    BCS next_row
.inside
    STA zp_temp                 \ The torches whose light reaches the row
    TAY
    LDA cached_left
    LDX cached_right
    JSR torch_gather_around
.tile
    LDA sweep_x
    CMP cached_left
    BCC next_row
    CMP cached_right
    BEQ in_row
    BCS next_row
.in_row
    STA zp_fill_x
    LDA sweep_row
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
    BEQ next_tile
    LDX torch_queue_tail        \ Queued (the room was seen to)
    STA torch_queue_light,X
    LDA zp_fill_x
    STA torch_queue_x,X
    LDA zp_fill_y
    STA torch_queue_y,X
    INX
    TXA
    AND #TORCH_QUEUE - 1
    STA torch_queue_tail
.next_tile
    INC sweep_x
    DEC sweep_tiles
    BNE tile
    RTS
.next_row
    LDA cached_left
    STA sweep_x
    DEC sweep_rows
    BEQ done
    LDX sweep_row
    INX
    CPX cached_bottom
    BEQ row_set
    BCC row_set
    LDX cached_top
.row_set
    STX sweep_row
    DEC sweep_tiles
    BEQ done
    JMP row
.done
    RTS
}
ASSERT TORCH_QUEUE > SWEEP_TILES

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

\ Tile (X, Y) has changed: its column's sky floor, the first tile from the
\ top that doesn't show the sky (lighting.sky_floor). If that has moved,
\ the sky in the glow's bands over it, old and new, is queued to be sent
\ again, as its band may have changed, and its light; and the column is
\ relit below them, as its surface (lighting.surface_row) may have moved.
\ Preserves X and Y.
.sky_floor_note
{
    STX sky_x
    STY sky_y
    LDA sky_floor,X
    STA sky_old_floor
    JSR tile_at
    JSR sky_shows
    BCC closed
    CPY sky_old_floor           \ Opened at the sky floor: look further down
    BNE done
.scan
    INY
    CPY #&FF
    BEQ found
    JSR tile_at
    JSR sky_shows
    BCS scan
.found
    TYA
    STA sky_floor,X
    JMP moved
.closed
    TYA                         \ Closed above it: the new sky floor
    CMP sky_floor,X
    BCS done
    STA sky_floor,X
.moved
    LDA sky_old_floor           \ The bands over the old sky floor
    JSR sky_bands_queue
    LDX sky_x
    LDA sky_floor,X             \ And the new
    JSR sky_bands_queue
    LDX sky_x                   \ The column relit, from the higher bands
    STX sun_req_l               \ down
    STX sun_req_r
    LDA sky_floor,X
    CMP sky_old_floor
    BCC higher
    LDA sky_old_floor
.higher
    SEC
    SBC #DAYNIGHT_BANDS
    BCS top_set
    LDA #0
.top_set
    STA sun_req_t
    LDA #&FF
    STA sun_req_b
    JSR sun_request
.done
    LDX sky_x
    LDY sky_y
    RTS
}

\ Carry set if the tile A, of shape zp_world_shape, shows the sky through
\ it: passable, with the sky behind it (lighting.shows_sky). X is the
\ column, sky_x.
.sky_shows
{
    TAX
    CLC
    LDA material_passable,X
    BEQ done
    LDA zp_world_shape
    AND #BACKGROUND_SKY
    BEQ done
    SEC
.done
    LDX sky_x
    RTS
}

\ Queue the sky in the glow's bands over a sky floor at row A, in column
\ sky_x, to be sent again: those of its DAYNIGHT_BANDS rows that are in the
\ tile cache, and sky, with their daylight; while the queue has room.
.sky_bands_queue
{
    SEC
    SBC #DAYNIGHT_BANDS
    BCS top_set
    LDA #0
.top_set
    STA zp_fill_y
    LDA sky_x
    STA zp_fill_x
    LDA #DAYNIGHT_BANDS
    STA sky_rows
.row
    LDA zp_fill_y               \ In the tile cache?
    CMP cached_top
    BCC next
    CMP cached_bottom
    BEQ in_rows
    BCS next
.in_rows
    LDA zp_fill_x
    CMP cached_left
    BCC done
    CMP cached_right
    BEQ in_cache
    BCS done
.in_cache
    JSR sun_cache_point         \ Sky?
    LDA (sun_ptr),Y
    CMP #TILE_SKY
    BNE next
    LDA torch_queue_head        \ Room?
    CLC
    SBC torch_queue_tail
    AND #TORCH_QUEUE - 1
    BEQ done
    JSR sun_daylight
    LDX torch_queue_tail        \ Queued
    STA torch_queue_light,X
    LDA zp_fill_x
    STA torch_queue_x,X
    LDA zp_fill_y
    STA torch_queue_y,X
    INX
    TXA
    AND #TORCH_QUEUE - 1
    STA torch_queue_tail
.next
    INC zp_fill_y
    DEC sky_rows
    BNE row
.done
    RTS
}

\ Tile (X, Y) has changed: its column's sky depth, and the tiles to relight:
\ if the sky depth is the same, the tile and the floor below it; otherwise
\ SHAFT_REACH either side, from the highest of the tile and the old and new
\ sky depths, to SUN_DARK below the lowest (and the floor below the tile).
.sun_tile_changed
{
    JSR sky_floor_note
    STX sun_x
    STY sun_y
    LDA sun_depth,X
    STA sun_old_depth
    JSR sun_clear_at
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
    BNE depth_changed
    STX sun_req_l               \ The same: only the tile, and the floor
    STX sun_req_r               \ below it
    LDA sun_y
    STA sun_req_t
    CLC
    ADC #1
    BCC below_set
    LDA #&FF
.below_set
    STA sun_req_b
    JMP sun_request
.depth_changed
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
    LDA sun_req_l               \ Widened across (from the higher of the
    CMP sun_l                   \ next row and the new top, below)
    BCS left_kept
    STA sun_l
.left_kept
    LDA sun_r
    CMP sun_req_r
    BCS right_kept
    LDA sun_req_r
    STA sun_r
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
