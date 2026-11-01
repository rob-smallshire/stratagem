\ Subsidence (stratagem.subsidence, docs/building.md): soil, grass
\ included, is held from below only, with no strength sideways, and drops
\ slowly and by chance, a tile at a time, from below upwards. A loose tile
\ is at risk while the tile under it is empty (air or sky). One that fails
\ drops into it, as soil, never onto the miner, over two frames: the tile
\ below becomes soil, then (subside_pending) the tile itself empties, to
\ sky if the tile above it is sky, otherwise to cave. Tiles at risk wait in a queue, each once;
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
    STA subside_pending
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

\ Carry set if tile (X, Y) is at risk: soil or grass (loose), with the tile
\ under it empty. Preserves X and Y.
.subside_at_risk
{
    JSR subside_loose
    BCC held
    INY                         \ Empty below
    JSR subside_material
    DEY
    CMP #TILE_AIR
    BEQ risky
    CMP #TILE_SKY
    BEQ risky
.held
    CLC
    RTS
.risky
    SEC
    RTS
}

\ Carry set if tile (X, Y) is loose: soil or grass. Preserves X and Y.
.subside_loose
{
    JSR subside_material
    CMP #TILE_SOIL
    BEQ loose
    CMP #TILE_GRASS
    BEQ loose
    CLC
    RTS
.loose
    SEC
    RTS
}

\ A frame. A drop half done is finished, if the frame's changed tile is
\ free, and nothing else is done. Otherwise up to SUBSIDE_CHECKS tiles are
\ taken from the queue's head: one outside the tile cache goes to the back;
\ one no longer at risk is dropped; one that can't fail now (the frame's
\ changed tile taken, or the miner in the tile below) goes to the back
\ unrolled; otherwise a roll: one that survives goes to the back, one that
\ fails drops, and the frame's rolling stops.
.subsidence_step
{
    LDA subside_pending
    BEQ rolling
    LDA redraw_tile
    BNE waiting
    LDA #0
    STA subside_pending
    LDX subside_pending_x
    LDY subside_pending_y
    JSR subside_loose
    BCS emptying
.waiting
    RTS                         \ (Or mined meanwhile)
.emptying
    STX target_x
    STY target_y
    JSR target_background       \ Sky above the surface, or below sky
    BNE sky
    LDX target_x
    LDY target_y
    DEY
    JSR subside_material
    CMP #TILE_SKY
    BNE cave
.sky
    LDA #BACKGROUND_SKY
    STA zp_world_new_shape      \ (SHAPE_FULL is 0)
    LDA #TILE_SKY
    JMP change_target
.cave
    LDA #0
    STA zp_world_new_shape
    LDA #TILE_AIR
    JMP change_target
.rolling
    LDA subside_count           \ min(SUBSIDE_CHECKS, the queue's length)
    BEQ done
    CMP #SUBSIDE_CHECKS
    BCC checks_set
    LDA #SUBSIDE_CHECKS
.checks_set
    STA subside_checks
    JSR subside_miner
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
    BNE back                    \ is free, and the miner isn't below it
    INY
    JSR subside_clear
    BCC back
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
    LDA subside_x               \ It drops: the tile below is soil, and next
    STA target_x                \ the tile itself empties
    STA subside_pending_x
    LDY subside_y
    STY subside_pending_y
    INY
    STY target_y
    JSR target_background
    STA zp_world_new_shape      \ (SHAPE_FULL is 0)
    LDA #&FF
    STA subside_pending
    LDA #TILE_SOIL
    JMP change_target
}
ASSERT SHAPE_FULL = 0

\ The tiles the miner is in: subside_left to subside_right across,
\ subside_top to subside_bottom down (actions.overlaps_player).
.subside_miner
{
    JSR player_pixels
    LDA zp_box_x + 1            \ px >> 3
    STA subside_t
    LDA zp_box_x
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    STA subside_left
    CLC                         \ (px + PLAYER_WIDTH - 1) >> 3
    LDA zp_box_x
    ADC #PLAYER_WIDTH - 1
    STA subside_t3
    LDA zp_box_x + 1
    ADC #0
    STA subside_t
    LDA subside_t3
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    STA subside_right
    LDA zp_box_y + 1            \ py >> 4
    STA subside_t
    LDA zp_box_y
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    STA subside_top
    CLC                         \ (py + PLAYER_HEIGHT - 1) >> 4
    LDA zp_box_y
    ADC #PLAYER_HEIGHT - 1
    STA subside_t3
    LDA zp_box_y + 1
    ADC #0
    STA subside_t
    LDA subside_t3
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    LSR subside_t
    ROR A
    STA subside_bottom
    RTS
}
ASSERT TILE_WIDTH = 8 AND TILE_HEIGHT = 16

\ Carry set if tile (X, Y) is clear of the miner. Preserves X and Y.
.subside_clear
{
    CPX subside_left
    BCC clear
    CPX subside_right
    BEQ across
    BCS clear
.across
    CPY subside_top
    BCC clear
    CPY subside_bottom
    BEQ in
    BCS clear
.in
    CLC
    RTS
.clear
    SEC
    RTS
}

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
