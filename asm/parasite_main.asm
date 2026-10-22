\ PGAME: the game, on the parasite (docs/tube-game.md). Each frame: wait
\ until the host has read the last packet (its mailbox count catches up),
\ take the input it wrote, move the player, dig or place, plan the camera,
\ bring the tile cache up to date, light the miner's surroundings, and send
\ the host a packet of all it needs to draw the frame.

.pgame_start
{
    LDX #&FF                    \ The parasite's own stack: we never return
    TXS
    CLI
    LDA #0
    STA zp_frame
    STA zp_input
    STA zp_lead
    STA zp_camera_x
    STA zp_camera_x + 1
    STA zp_camera_y
    STA zp_camera_y + 1
    STA zp_direction
    STA zp_player_vx
    STA zp_player_vy
    STA zp_player_on_ground
    STA inventory
    STA wood
    STA cooldown
    STA zp_player_jump_held
    STA zp_player_air_jumps
    STA redraw_tile
    STA light_dirty
    STA MAILBOX_FRAME
    STA para_sent
    STA support_head
    STA support_tail
    STA support_lost
    LDA #STARTING_ABILITIES
    STA zp_abilities
    LDA #1
    STA zp_player_facing
    LDA #LO(PLAYER_START_X)
    STA zp_player_x
    LDA #HI(PLAYER_START_X)
    STA zp_player_x + 1
    LDA #LO(PLAYER_START_Y)
    STA zp_player_y
    LDA #HI(PLAYER_START_Y)
    STA zp_player_y + 1
    JSR player_focus_and_frame
    LDA #LO(SCREEN_START)       \ As the host starts it
    STA zp_screen_start
    LDA #HI(SCREEN_START)
    STA zp_screen_start + 1
    JSR world_reset
    JSR piece_init
    JSR sun_init
    JSR sl_init
    JSR plan_camera             \ The focus is outside the view, so redraw
    JMP first_frame
}

.para_loop
{
.wait                           \ Until the host has read every packet sent
    LDA MAILBOX_FRAME
    CMP para_sent
    BNE wait
    LDA MAILBOX_INPUT
    STA zp_input
.*para_input                    \ (Labels like this are for timing)
    INC zp_frame
    JSR update_player
    JSR player_action
    LDA redraw_tile             \ A torch, unless a tile has changed already
    BNE no_torch
    JSR torch_input
.no_torch
    JSR plan_camera
}
.first_frame
    JSR para_frame
    JMP para_loop

\ Bring everything up to date for the frame planned, write its packet, and
\ send it.
.para_frame
{
    LDA para_sent               \ This frame's buffers
    AND #1
    BNE second
    LDA #LO(PACKET_BUFFER_0)
    STA para_packet
    LDA #HI(PACKET_BUFFER_0)
    STA para_packet + 1
    LDA #LO(LIST_BUFFER_0)
    STA para_list
    LDA #HI(LIST_BUFFER_0)
    STA para_list + 1
    JMP buffers_set
.second
    LDA #LO(PACKET_BUFFER_1)
    STA para_packet
    LDA #HI(PACKET_BUFFER_1)
    STA para_packet + 1
    LDA #LO(LIST_BUFFER_1)
    STA para_list
    LDA #HI(LIST_BUFFER_1)
    STA para_list + 1
.buffers_set
    CLC                         \ Strips are written after their count
    LDA para_packet
    ADC #PACKET_STRIPS + 1
    STA para_write
    LDA para_packet + 1
    ADC #0
    STA para_write + 1
    LDA #0
    STA para_strips

    LDA zp_redraw               \ The plan: the whole view
    BEQ move
    JSR fill_view
    JSR sl_reset_view
    JMP planned
.move                           \ Or the screen start, the tile cache, and
    JSR move_screen_start       \ the new row, which the host draws as
    LDA light_dirty             \ daylight alone. New tiles in the cache
    PHA                         \ matter to the light only if they move the
    JSR pool_in_cache           \ cache's edge within the pool's window
    STA para_inside
    JSR update_tile_cache
    JSR pool_in_cache
    AND para_inside
    TAX
    PLA
    CPX #0
    BNE dirty_set
    LDA #&FF
.dirty_set
    STA light_dirty
    LDA zp_plan_dy
    BEQ planned
    BMI top
    LDA zp_camera_y
    CLC
    ADC #VIEW_ROWS - 1
    JMP reset_row
.top
    LDA zp_camera_y
.reset_row
    JSR sl_reset_row
.planned

    LDA #1                      \ Changed tiles: a dug or placed one, its
    STA para_change_y           \ torches flooded again, then those queued
    LDA #0
    STA para_changes
    LDA redraw_tile
    BEQ changed_done
    LDA #0
    STA redraw_tile
    LDX redraw_tile_x
    LDY redraw_tile_y
    JSR sun_tile_changed
    LDX redraw_tile_x
    LDY redraw_tile_y
    JSR torch_tile_changed
    LDA redraw_tile_x
    STA zp_fill_x
    LDA redraw_tile_y
    STA zp_fill_y
    JSR para_emit_change
.changed_done
    JSR support_step            \ Pieces no longer held fall, sent as changed
.*para_daylight
    JSR sun_step                \ Relighting by daylight, queueing changes
.*para_daylit
.queued
    LDA para_changes
    CMP #CHANGES_PER_FRAME
    BCS changes_done
    LDX torch_queue_head
    CPX torch_queue_tail
    BEQ changes_done
    LDA torch_queue_light,X
    STA para_new_light
    LDA torch_queue_x,X
    STA zp_fill_x
    LDA torch_queue_y,X
    STA zp_fill_y
    INX
    TXA
    AND #TORCH_QUEUE - 1
    STA torch_queue_head
    LDA zp_fill_y               \ Still in the tile cache?
    CMP cached_top
    BCC queued
    CMP cached_bottom
    BEQ down_inside
    BCS queued
.down_inside
    LDA zp_fill_x
    CMP cached_left
    BCC queued
    CMP cached_right
    BEQ inside
    BCS queued
.inside
    JSR para_cache_pointer      \ Its new light, now the host will draw it
    LDA para_cache + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache)
    STA para_cache + 1
    LDY #0
    LDA para_new_light
    STA (para_cache),Y
    JSR para_emit_change
    JMP queued
.changes_done
    LDY #0
    LDA para_changes
    STA (para_write),Y
    JSR store_emit
    JSR cache_prefetch
    LDY #PACKET_STRIPS
    LDA para_strips
    STA (para_packet),Y

    LDA #0                      \ The columns the light's list may draw in:
    STA sl_col_lo               \ not new ones, which the host draws after it
    LDA #VIEW_COLUMNS - 1
    STA sl_col_hi
    LDA zp_redraw
    BNE columns_set
    LDA zp_plan_dx
    BEQ columns_set
    BMI new_left
    LDA #VIEW_COLUMNS - 1
    SEC
    SBC zp_plan_dx
    STA sl_col_hi
    JMP columns_set
.new_left
    EOR #&FF
    CLC
    ADC #1
    STA sl_col_lo
.columns_set

    CLC                         \ The light, and its list
    LDA para_list
    ADC #1
    STA sl_list_ptr
    LDA para_list + 1
    ADC #0
    STA sl_list_ptr + 1
    LDA #0
    STA sl_list_count
.*para_light
    JSR sl_update
.*para_lit
    LDY #0
    LDA sl_list_count
    STA (para_list),Y

    LDA zp_redraw               \ The new columns, drawn after the list as
    BNE header                  \ daylight alone: for the next pass
    LDA zp_plan_dx
    BEQ header
    BMI reset_left
    STA para_count
    LDA #VIEW_COLUMNS
    SEC
    SBC zp_plan_dx
    JMP reset_columns
.reset_left
    EOR #&FF
    CLC
    ADC #1
    STA para_count
    LDA #0
.reset_columns
    STA para_column
.reset_column
    LDA para_column
    JSR sl_reset_column
    INC para_column
    DEC para_count
    BNE reset_column

.header
    LDY #PACKET_FLAGS
    LDA zp_redraw
    AND #PACKET_REDRAW
    STA (para_packet),Y
    LDY #PACKET_PLAN_DX
    LDA zp_plan_dx
    STA (para_packet),Y
    INY
    LDA zp_plan_dy
    STA (para_packet),Y
    INY
    LDX #0
.header_loop                    \ Camera, player position (in zero page order)
    LDA header_sources,X
    STA sl_ptr2
    LDA #0
    STA sl_ptr2 + 1
    STY para_y
    LDY #0
    LDA (sl_ptr2),Y
    LDY para_y
    STA (para_packet),Y
    INY
    INX
    CPX #header_sources_end - header_sources
    BNE header_loop

.*para_send
    LDA #COMMAND_FRAME          \ Send it
    JSR OSWRCH
    LDA para_sent
    AND #1
    JSR OSWRCH
    INC para_sent
    RTS
}

\ After the changed tiles, the changes queued for the host's copy of the
\ store (world.asm), as many as fit: a count, then each change's slot and
\ offset, then a tile's material and shape, or the whole chunk.
.store_emit
{
    LDA para_change_y           \ Past the changed tiles
    CLC
    ADC para_write
    STA para_write
    STA zp_store_count          \ The count goes here
    LDA para_write + 1
    ADC #0
    STA para_write + 1
    STA zp_store_count + 1
    INC para_write              \ The changes after it
    BNE room
    INC para_write + 1
.room
    LDA para_packet             \ Room: the packet's end less para_write
    CLC                         \ (and the chunk to fetch)
    ADC #LO(PACKET_BYTES - FETCH_BYTES)
    STA store_room
    LDA para_packet + 1
    ADC #HI(PACKET_BYTES - FETCH_BYTES)
    STA store_room + 1
    LDA store_room
    SEC
    SBC para_write
    STA store_room
    LDA store_room + 1
    SBC para_write + 1
    STA store_room + 1
    LDA #0
    STA store_count
.change
    LDX store_head
    CPX store_tail
    BEQ done
    LDA store_queue_offset,X
    CMP #STORE_CHUNK
    BEQ chunk
    LDA #STORE_TILE_BYTES       \ A tile
    JSR store_take
    BCS done
    LDY #2
    LDA store_queue_material,X
    STA (para_write),Y
    INY
    LDA store_queue_shape,X
    STA (para_write),Y
    LDA #STORE_TILE_BYTES
    BNE next                    \ Always branches
.chunk
    LDA #STORE_CHUNK_BYTES      \ A whole chunk
    JSR store_take
    BCS done
    LDY store_queue_slot,X      \ From its cache slot (not dropped while
    LDA cache_of,Y              \ anything is queued for it)
    JSR point_at_slot
    LDA para_write              \ Its bytes after the slot and offset
    CLC
    ADC #2
    STA para_write
    BCC copy
    INC para_write + 1
.copy
    LDY #SLOT_BYTES - 1
.copy_loop
    LDA (zp_world_pointer),Y
    STA (para_write),Y
    DEY
    BPL copy_loop
    LDA #SLOT_BYTES
.next
    CLC                         \ Past the change
    ADC para_write
    STA para_write
    BCC taken
    INC para_write + 1
.taken
    INC store_count
    INX
    TXA
    AND #STORE_QUEUE - 1
    STA store_head
    JMP change
.done
    LDY #0
    LDA store_count
    STA (zp_store_count),Y
    RTS
}

\ Take A bytes of the packet's room for queued change X, and write its slot
\ and offset; or return with carry set if there isn't room. Preserves X.
.store_take
{
    STA para_tmp
    LDA store_room
    SEC
    SBC para_tmp
    STA para_tmp
    LDA store_room + 1
    SBC #0
    BCC full
    STA store_room + 1
    LDA para_tmp
    STA store_room
    LDY #0
    LDA store_queue_slot,X
    STA (para_write),Y
    INY
    LDA store_queue_offset,X
    STA (para_write),Y
    CLC
    RTS
.full
    SEC
    RTS
}

\ The zero page sources of the packet's header from PACKET_CAMERA_X.
.header_sources
    EQUB zp_camera_x, zp_camera_x + 1, zp_camera_y, zp_camera_y + 1
    EQUB zp_player_x, zp_player_x + 1, zp_player_y, zp_player_y + 1
    EQUB zp_player_frame
.header_sources_end
ASSERT PACKET_PLAYER_FRAME + 1 = PACKET_STRIPS
ASSERT header_sources_end - header_sources = PACKET_STRIPS - PACKET_CAMERA_X

\ &FF if the window of the last flood (the tiles within MINER_RADIUS of its
\ centre) is inside the tile cache, otherwise 0.
.pool_in_cache
{
    LDA sl_valid
    BEQ outside
    LDA sl_pcx
    SEC
    SBC #MINER_RADIUS
    BCC outside
    CMP cached_left
    BCC outside
    LDA sl_pcx
    CLC
    ADC #MINER_RADIUS
    BCS outside
    CMP cached_right
    BEQ across
    BCS outside
.across
    LDA sl_pcy
    SEC
    SBC #MINER_RADIUS
    BCC outside
    CMP cached_top
    BCC outside
    LDA sl_pcy
    CLC
    ADC #MINER_RADIUS
    BCS outside
    CMP cached_bottom
    BEQ inside
    BCS outside
.inside
    LDA #&FF
    RTS
.outside
    LDA #0
    RTS
}

\ Add tile (zp_fill_x, zp_fill_y) to the packet's changed tiles, from the
\ tile cache, and reset its light: the host draws it as daylight alone.
.para_emit_change
{
    LDY para_change_y
    LDA zp_fill_x
    STA (para_write),Y
    INY
    LDA zp_fill_y
    STA (para_write),Y
    INY
    JSR para_cache_pointer
    JSR para_copy_tile          \ (Too few to move para_write on)
    STY para_change_y
    INC para_changes
    LDX zp_fill_x
    LDY zp_fill_y
    JMP sl_reset_tile
}
ASSERT 1 + CHANGES_PER_FRAME * (2 + PARA_TILE_MOST) < &100 - PARA_TILE_MOST

\ Fill the tile cache from the world, and record what was filled in the
\ packet: a strip.
.call_fill_cache
{
    LDA zp_fill_x
    STA para_strip_x
    LDA zp_fill_y
    STA para_strip_y
    LDA zp_fill_count
    STA para_count
    LDA zp_fill_down
    STA para_strip_down
    JSR fill_cache
    JSR sun_light_strip
    JSR torch_light_strip
    LDY #0
    LDA para_strip_down
    STA (para_write),Y
    INY
    LDA para_strip_x
    STA (para_write),Y
    STA zp_fill_x
    INY
    LDA para_strip_y
    STA (para_write),Y
    STA zp_fill_y
    INY
    LDA para_count
    STA (para_write),Y
    INY
.tile
    JSR para_cache_pointer
    JSR para_copy_tile
    LDA para_strip_down
    BNE down
    INC zp_fill_x
    JMP next
.down
    INC zp_fill_y
.next
    DEC para_count
    BNE tile
    INC para_strips
    TYA                         \ Past the strip
    CLC
    ADC para_write
    STA para_write
    BCC done
    INC para_write + 1
.done
    RTS
}

\ Point para_cache at tile (zp_fill_x, zp_fill_y) in the tile cache.
\ Preserves Y.
.para_cache_pointer
{
    LDA zp_fill_y
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA para_cache + 1
    LDA zp_fill_y
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA para_cache
    LDA zp_fill_x
    AND #TILE_CACHE_SIZE - 1
    ORA para_cache
    STA para_cache
    RTS
}

\ Copy the tile at para_cache (material, shape, light) to the packet at
\ (para_write),Y onwards, advancing Y. A piece is sent as its slot, after
\ its slot's pair if the slot is new (pieces.asm). Adds to para_write if Y
\ would wrap.
.para_copy_tile
{
    STY para_y
    LDY #0
    LDA (para_cache),Y
    STA para_material
    LDA para_cache + 1
    PHA
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA para_cache + 1
    LDA (para_cache),Y
    STA para_shape
    CLC
    LDA para_cache + 1
    ADC #HI(tile_cache_light - tile_cache_shapes)
    STA para_cache + 1
    LDA (para_cache),Y
    STA para_tmp
    PLA
    STA para_cache + 1
    LDY para_y
    LDA para_material
    CMP #FIRST_PIECE
    BCC plain
    CMP #FIRST_PIECE + PIECE_COUNT
    BCS plain
    LDX para_shape
    STY para_y
    JSR piece_slot
    LDY para_y
    BCC slot_held
    LDA #PIECE_COMPOSE          \ A new slot: compose it first
    STA (para_write),Y
    INY
    TXA
    STA (para_write),Y
    INY
    LDA piece_pair
    LSR A
    STA (para_write),Y          \ The piece
    INY
    LDA #0
    ROL A
    STA (para_write),Y          \ The backdrop
    INY
.slot_held
    LDA para_material           \ Its slot, or its backdrop if none
    LDX para_shape
    JSR piece_shown
    STA para_material
    STX para_shape
.plain
    LDA para_material
    STA (para_write),Y
    INY
    LDA para_shape
    STA (para_write),Y
    INY
    LDA para_tmp
    STA (para_write),Y
    INY
    CPY #&100 - PARA_TILE_MOST
    BCC done
    TYA                         \ Keep Y small: move para_write on instead
    CLC
    ADC para_write
    STA para_write
    BCC moved
    INC para_write + 1
.moved
    LDY #0
.done
    RTS
}
PARA_TILE_MOST = 4 + TILE_BYTES_SENT    \ The most a tile takes in a packet
