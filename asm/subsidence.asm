\ Subsidence (stratagem.subsidence, docs/building.md): soil, grass
\ included, is held from below only, with no strength sideways, and fails
\ slowly and by chance, from below upwards. A loose tile is at risk while
\ the tile under it is open. Tiles at risk wait in a queue, each once;
\ every changed tile notes those it may have put at risk (subsidence_target,
\ from change_target, once the tile cache has the change: support's falls
\ are of pieces, passable already). Each frame a few are taken from the
\ queue's head and rolled for (subsidence_step); one that fails is gone, as
\ if dug (change_target), at most one a frame, and only when the frame has
\ no other changed tile. It happens only in the tile cache, whose tiles are
\ quick to read (subside_material): a tile outside it is solid and not
\ loose, isn't noted, and if queued waits.

\ The queue, and the random generator, empty and seeded.
.subsidence_init
{
    LDA #0
    STA subside_head
    STA subside_tail
    STA subside_count
    LDA #LO(SUBSIDE_SEED)
    STA subside_random
    LDA #HI(SUBSIDE_SEED)
    STA subside_random + 1
    RTS
}

\ The tile at target_x/y changed (change_target).
.subsidence_target
{
    LDX target_x
    LDY target_y
    JMP subsidence_note
}

\ Tile (X, Y) changed: the tiles it may have put at risk join the queue
\ (stratagem.subsidence.noted): itself (put down over a drop), and the tile
\ above it (undermined). Preserves A, X, Y and the flags.
.subsidence_note
{
    PHP
    PHA
    JSR subside_candidate       \ Itself
    DEY
    JSR subside_candidate       \ Above
    INY
    PLA
    PLP
    RTS
}

\ Tile (X, Y) joins the queue if there's room, it isn't there already, and
\ it is at risk. Preserves X and Y.
.subside_candidate
{
    STX subside_x
    STY subside_y
    LDA subside_count
    CMP #SUBSIDE_QUEUE
    BCS out
    STA subside_i
    LDY subside_head
.scan
    LDA subside_i
    BEQ new
    LDA subside_queue_x,Y
    CMP subside_x
    BNE next
    LDA subside_queue_y,Y
    CMP subside_y
    BEQ out
.next
    INY
    TYA
    AND #SUBSIDE_QUEUE - 1
    TAY
    DEC subside_i
    JMP scan
.new
    LDX subside_x
    LDY subside_y
    JSR subside_at_risk
    BCC out
    JSR subside_push
.out
    LDX subside_x
    LDY subside_y
    RTS
}

\ Put (subside_x, subside_y) at the queue's tail.
.subside_push
{
    LDY subside_tail
    LDA subside_x
    STA subside_queue_x,Y
    LDA subside_y
    STA subside_queue_y,Y
    INY
    TYA
    AND #SUBSIDE_QUEUE - 1
    STA subside_tail
    INC subside_count
    RTS
}

\ Carry set if tile (X, Y) is at risk: soil or grass, with the tile under it
\ open. Preserves X and Y.
.subside_at_risk
{
    JSR subside_material
    CMP #TILE_SOIL
    BEQ loose
    CMP #TILE_GRASS
    BNE held
.loose
    INY                         \ Open below
    JSR subside_open
    DEY
    RTS
.held
    CLC
    RTS
}

\ Carry set if tile (X, Y) is open (passable). Preserves X and Y.
.subside_open
{
    JSR subside_material
    STX subside_t
    TAX
    LDA material_passable,X
    LDX subside_t
    CMP #1                      \ Carry: passable (non-zero)
    RTS
}

\ A frame: up to SUBSIDE_CHECKS tiles taken from the queue's head. One
\ outside the tile cache goes to the back; one no longer at risk is dropped; one that can't fail now goes to the back
\ unrolled; otherwise a roll: one that survives goes to the back, one that
\ fails is gone, and the frame's rolling with it.
.subsidence_step
{
    LDA subside_count           \ min(SUBSIDE_CHECKS, the queue's length)
    BEQ done
    CMP #SUBSIDE_CHECKS
    BCC checks_set
    LDA #SUBSIDE_CHECKS
.checks_set
    STA subside_checks
.check
    LDX subside_head
    LDA subside_queue_x,X
    STA subside_x
    LDA subside_queue_y,X
    STA subside_y
    INX
    TXA
    AND #SUBSIDE_QUEUE - 1
    STA subside_head
    DEC subside_count
    LDA subside_x               \ Outside the tile cache: it waits
    STA zp_fill_x
    LDA subside_y
    STA zp_fill_y
    JSR in_tile_cache
    BCC back
    LDX subside_x
    LDY subside_y
    JSR subside_at_risk
    BCC next                    \ Held again, or gone: dropped
    LDA redraw_tile             \ It can fail only if the frame's changed tile
    BNE back                    \ is free
    JSR subside_roll
    BCC fail
.back
    JSR subside_push
.next
    DEC subside_checks
    BNE check
.done
    RTS
.fail
    LDA subside_x               \ Gone: sky or cave, by its background, as
    STA target_x                \ if dug
    LDA subside_y
    STA target_y
    JSR target_background
    STA zp_world_new_shape      \ (SHAPE_FULL is 0)
    BEQ cave
    LDA #TILE_SKY
    BNE change                  \ (Always)
.cave
    LDA #TILE_AIR
.change
    JMP change_target
}
ASSERT SHAPE_FULL = 0

\ Roll: the random generator (MBANK's LFSR) stepped SUBSIDE_ROLL_STEPS
\ times; carry clear if its 16 bits are under SUBSIDE_THRESHOLD: the tile
\ fails.
.subside_roll
{
    LDY #SUBSIDE_ROLL_STEPS
.step
    LSR subside_random + 1
    ROR subside_random
    BCC stepped
    LDA subside_random + 1
    EOR #&B4
    STA subside_random + 1
.stepped
    DEY
    BNE step
    LDA subside_random
    CMP #LO(SUBSIDE_THRESHOLD)
    LDA subside_random + 1
    SBC #HI(SUBSIDE_THRESHOLD)
    RTS
}

\ The material of tile (X, Y), from the tile cache, in A; outside it,
\ TILE_STONE (solid, and not loose). Preserves X and Y.
.subside_material
{
    CPY cached_top
    BCC outside
    CPY cached_bottom
    BEQ rows_in
    BCS outside
.rows_in
    CPX cached_left
    BCC outside
    CPX cached_right
    BEQ inside
    BCS outside
.inside
    STX subside_t
    TYA                         \ tile_cache + (y MOD 32) * 32 + x MOD 32
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA load + 2
    TYA
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA subside_t3
    TXA
    AND #TILE_CACHE_SIZE - 1
    ORA subside_t3
    TAX
.load
    LDA tile_cache,X            \ (Its page set above)
    LDX subside_t
    RTS
.outside
    LDA #TILE_STONE
    RTS
}
ASSERT TILE_CACHE_SIZE = 32 AND LO(tile_cache) = 0
