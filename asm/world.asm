\ PWORLD, the parasite's world: the placeholder generator, which
\ tools/stratagem/world.py models exactly, and a cache of the store of
\ changed chunks, which the host holds (docs/tube-game.md). A tile is a
\ material and a shape (see tools/stratagem/tiles.py).
\
\ The directory gives each changed chunk's slot in the host's store (from
\ 1). The cache holds CACHE_SLOTS of them: those within a chunk of the tile
\ cache, fetched ahead of need a chunk a frame (cache_prefetch), and any
\ other a tile is asked of, fetched at once (cache_miss). Changes go to the
\ cached chunk and, by the queue (store_emit), to the host's, so a chunk is
\ dropped from the cache without writing it back, once nothing is queued
\ for it.

CLEAR BANK_START, BANK_END
ORG BANK_START
GUARD BANK_END

.world_start
    EQUB 0, 0, 0, 0, 0, 0, 0, 0 \ Not a ROM header: &8007 = 0 and &8001 <> "("

STORE_QUEUE = 32                \ Changes queued for the host (a power of 2)
CACHE_SLOTS = 40                \ Chunks the cache holds: at least the 6 x 6
                                \ within a chunk of the tile cache, and more

\ Return the tile at world (X, Y), y increasing downwards, as changed by the
\ player: the material in A and the shape in zp_world_shape. Preserves X
\ and Y.
.tile_at
{
    STX zp_world_x
    STY zp_world_y
    JSR find_chunk
    BNE changed
    LDX zp_world_x              \ Unchanged: generate it
    LDY zp_world_y
    JMP generate_tile
.changed
    JSR cache_slot_of
    JSR point_at_slot
    JSR offset_in_chunk
    TYA
    ORA #CHUNK_TILES
    TAY
    LDA (zp_world_pointer),Y
    STA zp_world_shape
    TYA
    AND #CHUNK_TILES - 1
    TAY
    LDA (zp_world_pointer),Y
    LDX zp_world_x
    LDY zp_world_y
    RTS
}

\ Change the tile at world (X, Y) to material A and shape zp_world_new_shape,
\ and queue the change for the host's store (store_emit). Return with carry
\ clear, or carry set if the chunk is unchanged so far and the store has no
\ free slot for it, or the queue is full. Preserves X and Y.
.set_tile
{
    STA zp_world_tile
    STX zp_world_target_x
    STY zp_world_target_y
    STX zp_world_x
    STY zp_world_y
    LDA store_tail              \ Room in the queue for a new chunk and the
    SEC                         \ tile: at most STORE_QUEUE - 1 queued
    SBC store_head
    AND #STORE_QUEUE - 1
    CMP #STORE_QUEUE - 3
    BCS done                    \ Full: carry is set
    JSR find_chunk
    BNE have_slot
    LDA world_slots_used
    CMP #WORLD_SLOT_COUNT
    BCS done                    \ Full: carry is set
    INC world_slots_used
    LDA world_slots_used
    STA (zp_world_pointer),Y    \ Y = 0
    STA cache_h                 \ A cache slot for it, filled as generated
    JSR cache_chunk_here
    JSR cache_take
    JSR cache_link
    JSR fill_slot
    LDA world_slots_used        \ The host copies it whole
    LDX #STORE_CHUNK
    JSR store_note
    LDX zp_world_target_x
    LDY zp_world_target_y
    STX zp_world_x
    STY zp_world_y
    JSR find_chunk
.have_slot
    PHA
    JSR cache_slot_of
    JSR point_at_slot
    JSR offset_in_chunk
    LDA zp_world_tile
    STA (zp_world_pointer),Y
    TYA
    TAX
    ORA #CHUNK_TILES
    TAY
    LDA zp_world_new_shape
    STA (zp_world_pointer),Y
    PLA
    JSR store_note
    CLC
.done
    LDX zp_world_target_x
    LDY zp_world_target_y
    RTS
}

\ Queue a change for the host's copy of the store: slot A, at offset X (a
\ tile, zp_world_tile and zp_world_new_shape), or STORE_CHUNK (the whole
\ chunk, read from the slot when the queue is emitted).
.store_note
{
    LDY store_tail
    STA store_queue_slot,Y
    TXA
    STA store_queue_offset,Y
    LDA zp_world_tile
    STA store_queue_material,Y
    LDA zp_world_new_shape
    STA store_queue_shape,Y
    INY
    TYA
    AND #STORE_QUEUE - 1
    STA store_tail
    RTS
}

\ The cache slot of host slot A, fetching it if it isn't cached.
.cache_slot_of
{
    TAX
    LDA cache_of,X
    BNE cached
    TXA
    JMP cache_miss
.cached
    RTS
}

\ Host slot A, of the chunk holding (zp_world_x, zp_world_y), isn't cached:
\ fetch it now (the host answers once it has drawn the frame it is drawing,
\ if any). Return its cache slot in A.
.cache_miss
{
    STA cache_h
    JSR cache_chunk_here
    JSR cache_take
    JSR cache_link
    LDA cache_p
    JSR point_at_slot
    LDA #0
    STA MAILBOX_FETCHED
    LDA #COMMAND_FETCH
    JSR OSWRCH
    LDA cache_h
    JSR OSWRCH
    LDA zp_world_pointer
    JSR OSWRCH
    LDA zp_world_pointer + 1
    JSR OSWRCH
.wait
    LDA MAILBOX_FETCHED
    BEQ wait
    INC cache_misses            \ Counted, for tests: it shouldn't happen in play
    BNE counted
    DEC cache_misses
.counted
    LDA cache_p
    RTS
}

\ Set cache_cx and cache_cy to the chunk holding (zp_world_x, zp_world_y).
.cache_chunk_here
{
    LDA zp_world_x
    LSR A
    LSR A
    LSR A
    STA cache_cx
    LDA zp_world_y
    LSR A
    LSR A
    LSR A
    STA cache_cy
    RTS
}

\ Cache slot A now holds host slot cache_h, of chunk (cache_cx, cache_cy).
\ Returns A unchanged, in cache_p too.
.cache_link
{
    STA cache_p
    TAY
    LDX cache_h
    STA cache_of,X
    TXA
    STA cache_holds,Y
    LDA cache_cx
    STA cache_chunk_x,Y
    LDA cache_cy
    STA cache_chunk_y,Y
    LDA cache_p
    RTS
}

\ Return in A a cache slot to use: a free one, or else one whose chunk is
\ beyond the wanted chunks (cache_want_*) and has nothing queued for the
\ host, taken in turn; or else (never, with enough slots) any with nothing
\ queued. Its chunk is dropped from the cache.
.cache_take
{
    LDY #CACHE_SLOTS
.free
    LDA cache_holds,Y
    BEQ found
    DEY
    BNE free
    LDA #&FF                    \ First pass: only unwanted chunks
    STA cache_pass
.pass
    LDA #CACHE_SLOTS
    STA cache_tries
    LDY cache_victim
.try
    DEY
    BNE in_range
    LDY #CACHE_SLOTS
.in_range
    LDA cache_pass
    BEQ any
    LDA cache_chunk_x,Y
    CMP cache_want_l
    BCC unwanted
    CMP cache_want_r
    BEQ across
    BCS unwanted
.across
    LDA cache_chunk_y,Y
    CMP cache_want_t
    BCC unwanted
    CMP cache_want_b
    BEQ next                    \ Wanted
    BCC next
.unwanted
.any
    LDA cache_holds,Y           \ Nothing queued for it?
    LDX store_head
.queued
    CPX store_tail
    BEQ evict
    CMP store_queue_slot,X
    BEQ next
    INX
    TXA
    AND #STORE_QUEUE - 1
    TAX
    LDA cache_holds,Y
    JMP queued
.next
    DEC cache_tries
    BNE try
    LDA #0                      \ Second pass: any
    STA cache_pass
    JMP pass
.evict
    STY cache_victim
    TAX
    LDA #0
    STA cache_of,X
    LDA #&FF                    \ It may be wanted again
    STA cache_scan
.found
    TYA
    RTS
}

\ Bring the wanted chunks (those within a chunk of the tile cache) up to
\ date, and fetch the first changed one that isn't cached: write to the
\ packet at para_write its host slot and the address to copy it to, or 0
\ if there is none to fetch. The host copies it before it writes the
\ mailbox, so it is there when the next frame starts.
.cache_prefetch
{
    LDX #3                      \ The wanted chunks: left, right, top, bottom
.edge
    LDA cached_left,X
    LSR A
    LSR A
    LSR A
    TAY
    TXA
    LSR A                       \ Carry set for right and bottom
    TYA
    BCS far
    BEQ edge_set                \ Left and top: one less, from 0
    SEC
    SBC #1
    JMP edge_set
.far
    CMP #CHUNKS_ACROSS - 1      \ Right and bottom: one more, to the last
    BCS edge_set
    ADC #1
.edge_set
    CMP cache_want_l,X
    BEQ same
    STA cache_want_l,X
    LDA #&FF
    STA cache_scan
.same
    DEX
    BPL edge
    LDA cache_scan              \ Look only when something may be missing
    BEQ none
    LDA cache_want_t
    STA cache_cy
.row
    LDA cache_cy                \ The directory's row: cy * 32 + l
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(world_directory)
    STA zp_world_pointer + 1
    LDA cache_cy
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    ORA cache_want_l
    STA zp_world_pointer
    LDA cache_want_l
    STA cache_cx
    LDY #0
.chunk
    LDA (zp_world_pointer),Y
    BEQ unchanged
    TAX
    LDA cache_of,X
    BEQ fetch
.unchanged
    INY
    INC cache_cx
    LDA cache_cx
    CMP cache_want_r
    BEQ chunk
    BCC chunk
    INC cache_cy
    LDA cache_cy
    CMP cache_want_b
    BEQ row
    BCC row
    LDA #0                      \ All there
    STA cache_scan
.none
    LDY #0
    STA (para_write),Y
    RTS
.fetch
    STX cache_h
    JSR cache_take
    JSR cache_link
    JSR point_at_slot
    LDY #0
    LDA cache_h
    STA (para_write),Y
    INY
    LDA zp_world_pointer
    STA (para_write),Y
    INY
    LDA zp_world_pointer + 1
    STA (para_write),Y
    RTS
}
CHUNKS_ACROSS = 256 / CHUNK_SIZE
ASSERT cached_right = cached_left + 1 AND cached_top = cached_left + 2 AND cached_bottom = cached_left + 3
ASSERT cache_want_r = cache_want_l + 1 AND cache_want_t = cache_want_l + 2 AND cache_want_b = cache_want_l + 3

\ Point zp_world_pointer at the directory entry of the chunk holding
\ (zp_world_x, zp_world_y), and return it in A, with Y = 0 and Z set if the
\ chunk is unchanged.
.find_chunk
{
    LDA zp_world_y              \ Entry (y >> 3) * 32 + (x >> 3)
    LSR A
    LSR A
    LSR A
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(world_directory)
    STA zp_world_pointer + 1
    LDA zp_world_y
    AND #&38
    ASL A
    ASL A
    STA zp_world_pointer
    LDA zp_world_x
    LSR A
    LSR A
    LSR A
    ORA zp_world_pointer
    STA zp_world_pointer
    LDY #0
    LDA (zp_world_pointer),Y
    RTS
}

\ Point zp_world_pointer at cache slot A (1-based).
.point_at_slot
{
    SEC
    SBC #1
    LDY #0
    STY zp_world_pointer
    LSR A                       \ (slot - 1) * 128
    ROR zp_world_pointer
    CLC
    ADC #HI(world_slots)
    STA zp_world_pointer + 1
    RTS
}

\ Return in Y the offset of (zp_world_x, zp_world_y) within its chunk.
.offset_in_chunk
{
    LDA zp_world_y
    AND #CHUNK_SIZE - 1
    ASL A
    ASL A
    ASL A
    STA zp_world_temp
    LDA zp_world_x
    AND #CHUNK_SIZE - 1
    ORA zp_world_temp
    TAY
    RTS
}

\ Fill cache slot A with the generated tiles of the chunk holding
\ (zp_world_target_x, zp_world_target_y).
.fill_slot
{
    JSR point_at_slot
    LDA #0
    STA zp_world_index
.loop
    LDA zp_world_target_x       \ x = chunk left + (index AND 7)
    AND #&F8
    STA zp_world_x
    LDA zp_world_index
    AND #CHUNK_SIZE - 1
    ORA zp_world_x
    TAX
    LDA zp_world_target_y       \ y = chunk top + (index >> 3)
    AND #&F8
    STA zp_world_y
    LDA zp_world_index
    LSR A
    LSR A
    LSR A
    ORA zp_world_y
    TAY
    JSR generate_tile           \ Uses zp_world_* but not zp_world_pointer
    LDY zp_world_index
    STA (zp_world_pointer),Y
    TYA
    ORA #CHUNK_TILES
    TAY
    LDA zp_world_shape
    STA (zp_world_pointer),Y
    INC zp_world_index
    LDA zp_world_index
    CMP #CHUNK_TILES
    BNE loop
    RTS
}

\ Forget every change: clear the directory and the cache.
.world_reset
{
    LDA #0
    STA world_slots_used
    STA store_head
    STA store_tail
    STA cache_misses
    TAX
.cache
    STA cache_of,X
    INX
    BNE cache
    LDX #CACHE_SLOTS
.slots
    STA cache_holds,X
    DEX
    BPL slots
    STX cache_want_l            \ (&FF) No tile cache yet
    STX cache_scan
    LDA #CACHE_SLOTS
    STA cache_victim
    LDA #0
    TAY
    LDX #HI(world_directory)
    STX zp_world_pointer + 1
    STY zp_world_pointer
.loop
    STA (zp_world_pointer),Y
    INY
    BNE loop
    INC zp_world_pointer + 1
    LDX zp_world_pointer + 1
    CPX #HI(world_directory) + 4
    BNE loop
    RTS
}

\ Return the generated tile at world (X, Y), the world before any changes:
\ the material in A and the shape in zp_world_shape. A diggable tile has its
\ corner rounded off where it borders open space (see world.py), and every
\ tile at or above its column's surface has BACKGROUND_SKY. Preserves X and
\ Y.
.generate_tile
{
    STX zp_generate_x
    STY zp_generate_y
    JSR generate_material
    STA zp_generate_material
    LDA #SHAPE_FULL
    STA zp_world_shape
    LDA zp_generate_material    \ Diggable: GRASS to GEM
    SEC
    SBC #TILE_GRASS
    CMP #TILE_GEM - TILE_GRASS + 1
    BCS background
    LDX zp_generate_x
    LDA world_heights,X
    CMP zp_generate_y
    BNE underground
    \ On the surface: slope down towards one lower neighbouring column.
    LDA zp_generate_y
    CMP world_heights - 1,X     \ Carry clear if the left column is lower
    ROL zp_generate_open        \ Bit 1: left not lower
    CMP world_heights + 1,X
    ROL zp_generate_open        \ Bit 0: right not lower
    LDA zp_generate_open
    AND #3
    CMP #1                      \ Left lower, right not
    BNE not_left_lower
    LDA #SHAPE_RAMP_TOP_LEFT
    BNE shaped
.not_left_lower
    CMP #2                      \ Right lower, left not
    BNE background
    LDA #SHAPE_RAMP_TOP_RIGHT
    BNE shaped
.underground
    \ Round a corner with open space on one side and above or below.
    DEX
    JSR open_at_x
    ROL zp_generate_open        \ Bit 1: left open
    LDX zp_generate_x
    INX
    JSR open_at_x
    ROL zp_generate_open        \ Bit 0: right open
    LDA zp_generate_open
    AND #3
    BEQ background              \ Neither side open
    CMP #3
    BEQ background              \ Both sides open
    LDX zp_generate_x
    LDY zp_generate_y
    DEY
    JSR open_at
    BCC not_above
    LDA zp_generate_open
    AND #2
    BEQ ramp_top_right
    LDA #SHAPE_RAMP_TOP_LEFT
    BNE shaped
.ramp_top_right
    LDA #SHAPE_RAMP_TOP_RIGHT
    BNE shaped
.not_above
    LDX zp_generate_x
    LDY zp_generate_y
    INY
    JSR open_at
    BCC background
    LDA zp_generate_open
    AND #2
    BEQ ramp_bottom_right
    LDA #SHAPE_RAMP_BOTTOM_LEFT
    BNE shaped
.ramp_bottom_right
    LDA #SHAPE_RAMP_BOTTOM_RIGHT
.shaped
    STA zp_world_shape
.background
    LDX zp_generate_x           \ Sky behind tiles at or above the surface
    LDA world_heights,X
    CMP zp_generate_y
    BCC done
    LDA zp_world_shape
    ORA #BACKGROUND_SKY
    STA zp_world_shape
.done
    LDA zp_generate_material
    LDX zp_generate_x
    LDY zp_generate_y
    RTS
}

\ Return carry set if the generated material at (X, zp_generate_y) is open
\ (passable), clear if not.
.open_at_x
{
    LDY zp_generate_y
    \ Fall through
}

\ Return carry set if the generated material at (X, Y) is open (passable),
\ clear if not: AIR, or WATER or SKY.
.open_at
{
    JSR generate_material
    CMP #TILE_AIR
    BEQ open
    CMP #TILE_WATER             \ WATER and SKY are the last materials
    RTS
.open
    SEC
    RTS
}

\ Return in A the generated material at world (X, Y). Preserves X and Y.
.generate_material
{
    STX zp_world_x
    STY zp_world_y
    CPX #0
    BEQ bedrock
    CPX #255
    BEQ bedrock
    CPY #255
    BEQ bedrock
    TYA
    SEC
    SBC world_heights,X         \ Depth below the surface
    BCC sky
    BEQ grass
    STA zp_world_depth
    LDA world_perm,X            \ Fine hash: perm[perm[x] EOR y]
    EOR zp_world_y
    TAX
    LDA world_perm,X
    STA zp_world_fine
    AND #3
    CLC
    ADC #WORLD_SOIL_DEPTH
    CMP zp_world_depth
    BCS soil                    \ Soil while depth <= SOIL_DEPTH + (fine AND 3)
    LDA zp_world_y              \ Coarse hash: perm[(x >> 2) EOR perm[y >> 1]]
    LSR A
    TAX
    LDA world_perm,X
    STA zp_world_temp
    LDA zp_world_x
    LSR A
    LSR A
    EOR zp_world_temp
    TAX
    LDA world_perm,X
    CMP #WORLD_CAVE_THRESHOLD
    BCC cave
    LDA zp_world_fine
    CMP #WORLD_ORE_THRESHOLD
    BCC ore
    CMP #WORLD_GEM_THRESHOLD
    BCC gem
    LDA #TILE_STONE
    BNE done
.cave
    LDA zp_world_y
    CMP #WORLD_WATER_DEPTH
    BCS water
.air
    LDA #TILE_AIR
    BEQ done
.sky
    LDA #TILE_SKY
    BNE done
.water
    LDA #TILE_WATER
    BNE done
.grass
    LDA #TILE_GRASS
    BNE done
.soil
    LDA #TILE_SOIL
    BNE done
.ore
    LDA #TILE_ORE
    BNE done
.gem
    LDA #TILE_GEM
    BNE done
.bedrock
    LDA #TILE_BEDROCK
.done
    LDX zp_world_x
    LDY zp_world_y
    RTS
}

\ Fill zp_fill_count tiles of the tile cache from world tile (zp_fill_x,
\ zp_fill_y), along the row, or down the column if zp_fill_down is non-zero.
.fill_cache
{
.loop
    LDX zp_fill_x
    LDY zp_fill_y
    JSR tile_at
    PHA
    TYA                         \ tile_cache + (y MOD 32) * 32 + (x MOD 32)
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA zp_fill_pointer + 1
    TYA
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_fill_pointer
    TXA
    AND #TILE_CACHE_SIZE - 1
    ORA zp_fill_pointer
    STA zp_fill_pointer
    LDY #0
    PLA
    STA (zp_fill_pointer),Y     \ The material
    LDA zp_fill_pointer + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA zp_fill_pointer + 1
    LDA zp_world_shape
    STA (zp_fill_pointer),Y     \ The shape
    LDA zp_fill_pointer + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache_shapes)
    STA zp_fill_pointer + 1
    JSR fixed_light
    STA (zp_fill_pointer),Y     \ The light
    LDA zp_fill_down
    BNE down
    INC zp_fill_x
    JMP next
.down
    INC zp_fill_y
.next
    DEC zp_fill_count
    BNE loop
    RTS
}

\ The light at (zp_fill_x, zp_fill_y), times LIGHT_SCALE: a stand-in for
\ daylight (lighting.fixed_light). Full down to the surface, then a level
\ less each tile deeper, down to LIGHT_FIXED_FLOOR. Preserves Y.
.fixed_light
{
    ASSERT LIGHT_SCALE = 16
    LDX zp_fill_x
    LDA zp_fill_y
    SEC
    SBC world_heights,X         \ The depth below the surface
    BCC full                    \ Above it
    BEQ full                    \ At it
    CMP #LIGHT_FULL - LIGHT_FIXED_FLOOR
    BCS floor
    STA zp_world_temp
    LDA #LIGHT_FULL
    SEC
    SBC zp_world_temp
    JMP scale
.floor
    LDA #LIGHT_FIXED_FLOOR
    JMP scale
.full
    LDA #LIGHT_FULL
.scale
    ASL A
    ASL A
    ASL A
    ASL A
    RTS
}

.world_heights
    WORLD_HEIGHTS
.world_perm
    WORLD_PERM

.world_slots_used   EQUB 0      \ Slots used in the host's store
.cache_want_l       EQUB 0      \ The wanted chunks, inclusive (in the order of
.cache_want_r       EQUB 0      \ cached_left, cached_right, cached_top and
.cache_want_t       EQUB 0      \ cached_bottom)
.cache_want_b       EQUB 0
.cache_scan         EQUB 0      \ Non-zero if a wanted chunk may be uncached
.cache_misses       EQUB 0      \ Chunks fetched at once (at most 255)
.cache_victim       EQUB CACHE_SLOTS    \ Where cache_take looks next
.cache_pass         EQUB 0
.cache_tries        EQUB 0
.cache_h            EQUB 0      \ A host slot...
.cache_p            EQUB 0      \ ... its cache slot
.cache_cx           EQUB 0      \ ... and its chunk
.cache_cy           EQUB 0

.world_end

\ The changes, which are not saved with the code: a directory entry for
\ each 8 x 8 chunk (zero if unchanged, otherwise its slot), then the slots.
ALIGN &100
.world_directory    SKIP (256 / CHUNK_SIZE) * (256 / CHUNK_SIZE)
.cache_of           SKIP 256    \ Each host slot's cache slot, or 0
.world_slots        SKIP CACHE_SLOTS * SLOT_BYTES   \ The cache's slots
.cache_holds        SKIP CACHE_SLOTS + 1    \ Each cache slot's host slot, or 0
.cache_chunk_x      SKIP CACHE_SLOTS + 1    \ ... and its chunk
.cache_chunk_y      SKIP CACHE_SLOTS + 1
.world_tables_end

