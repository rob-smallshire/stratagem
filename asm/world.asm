\ WORLD: the world bank: the placeholder generator, which
\ tools/stratagem/world.py models exactly, and the store of changed chunks.
\ A tile is a material and a shape (see tools/stratagem/tiles.py).

CLEAR BANK_START, BANK_END
ORG BANK_START
GUARD BANK_END

.world_start
    EQUB 0, 0, 0, 0, 0, 0, 0, 0 \ Not a ROM header: &8007 = 0 and &8001 <> "("

CHUNK_SIZE = 8
CHUNK_TILES = CHUNK_SIZE * CHUNK_SIZE
SLOT_BYTES = 2 * CHUNK_TILES    \ The materials, then the shapes

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

\ Change the tile at world (X, Y) to material A and shape zp_world_new_shape.
\ Return with carry clear, or carry set if the chunk is unchanged so far and
\ there is no free slot for it. Preserves X and Y.
.set_tile
{
    STA zp_world_tile
    STX zp_world_target_x
    STY zp_world_target_y
    STX zp_world_x
    STY zp_world_y
    JSR find_chunk
    BNE have_slot
    LDA world_slots_used
    CMP #WORLD_SLOT_COUNT
    BCS done                    \ Full: carry is set
    INC world_slots_used
    LDA world_slots_used
    STA (zp_world_pointer),Y    \ Y = 0
    JSR fill_slot
    LDX zp_world_target_x
    LDY zp_world_target_y
    STX zp_world_x
    STY zp_world_y
    JSR find_chunk
.have_slot
    JSR point_at_slot
    JSR offset_in_chunk
    LDA zp_world_tile
    STA (zp_world_pointer),Y
    TYA
    ORA #CHUNK_TILES
    TAY
    LDA zp_world_new_shape
    STA (zp_world_pointer),Y
    CLC
.done
    LDX zp_world_target_x
    LDY zp_world_target_y
    RTS
}

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

\ Point zp_world_pointer at slot A (1-based).
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

\ Fill the slot just allocated, slot A, with the generated tiles of the
\ chunk holding (zp_world_target_x, zp_world_target_y).
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

\ Forget every change: clear the directory.
.world_reset
{
    LDA #0
    STA world_slots_used
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

.world_heights
    WORLD_HEIGHTS
.world_perm
    WORLD_PERM

.world_slots_used   EQUB 0

.world_end

\ The changes, which are not saved with the code: a directory entry for
\ each 8 x 8 chunk (zero if unchanged, otherwise its slot), then the slots.
ALIGN &100
.world_directory    SKIP (256 / CHUNK_SIZE) * (256 / CHUNK_SIZE)
.world_slots        SKIP WORLD_SLOT_COUNT * SLOT_BYTES

SAVE "WORLD", world_start, world_end
