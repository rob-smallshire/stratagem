\ WORLD: the world bank. For now just the placeholder generator, which
\ tools/stratagem/world.py models exactly.

CLEAR BANK_START, BANK_END
ORG BANK_START
GUARD BANK_END

.world_start
    EQUB 0, 0, 0, 0, 0, 0, 0, 0 \ Not a ROM header: &8007 = 0 and &8001 <> "("

CHUNK_SIZE = 8
SLOT_BYTES = CHUNK_SIZE * CHUNK_SIZE

\ Return in A the tile at world (X, Y), y increasing downwards, as changed
\ by the player. Preserves X and Y.
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
    LDA (zp_world_pointer),Y
    LDX zp_world_x
    LDY zp_world_y
    RTS
}

\ Change the tile at world (X, Y) to A. Return with carry clear, or carry
\ set if the chunk is unchanged so far and there is no free slot for it.
\ Preserves X and Y.
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
    LSR A                       \ (slot - 1) * 64
    ROR zp_world_pointer
    LSR A
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

\ Fill the slot just allocated, at zp_world_pointer, with the generated
\ tiles of the chunk holding (zp_world_target_x, zp_world_target_y).
.fill_slot
{
    JSR point_at_slot           \ A is the slot
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
    LDA zp_world_pointer        \ generate_tile uses zp_world_* but not
    PHA                         \ zp_world_pointer; keep it safe anyway
    LDA zp_world_pointer + 1
    PHA
    JSR generate_tile
    TAX
    PLA
    STA zp_world_pointer + 1
    PLA
    STA zp_world_pointer
    TXA
    LDY zp_world_index
    STA (zp_world_pointer),Y
    INC zp_world_index
    LDA zp_world_index
    CMP #SLOT_BYTES
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

\ Return in A the generated tile at world (X, Y): the world before any
\ changes. Preserves X and Y.
.generate_tile
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
    STA (zp_fill_pointer),Y
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
