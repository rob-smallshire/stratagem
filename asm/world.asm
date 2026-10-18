\ WORLD: the world bank. For now just the placeholder generator, which
\ tools/stratagem/world.py models exactly.

CLEAR BANK_START, BANK_END
ORG BANK_START
GUARD BANK_END

.world_start
    EQUB 0, 0, 0, 0, 0, 0, 0, 0 \ Not a ROM header: &8007 = 0 and &8001 <> "("

\ Return in A the tile at world (X, Y), y increasing downwards. Preserves X
\ and Y.
.tile_at
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

.world_end

SAVE "WORLD", world_start, world_end
