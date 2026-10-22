\ Support (docs/tile-set.md, Support; tools/stratagem/support.py): pieces
\ are held up, and what isn't held falls. A small cellular automaton, run
\ only where tiles change.
\
\ A piece's strength is in its shape byte's bits 0-2. Terrain that isn't
\ passable has the span, and holds anything; nothing else holds or has
\ strength. A piece held from below or above takes its holder's strength;
\ one held from the side (SPAN) its holder's less one. Each changed tile and
\ its neighbours are queued to be checked (support_note, from
\ call_set_tile); a check works the tile's strength out again from its
\ neighbours, and if it has changed, stores it, or at 0 lets the piece fall
\ (to sky or cave, as its background), which changes it and so queues its
\ neighbours in turn. A few checks a frame, and a piece falls only every
\ FALL_FRAMES frames, so that a felled tree is seen to come apart. Pieces are clear to light and
\ passable, so a fall changes neither daylight nor the miner's light: the
\ tile is only redrawn.

SUPPORT_QUEUE = 64              \ Tiles to check (a power of 2)
SUPPORT_CHECKS = 6              \ Checks a frame, at most
FALL_FRAMES = 4                 \ Frames from one fall to the next
STRENGTH_BITS = 7

SIDE_BELOW = 0                  \ Where a holder is, from the piece held
SIDE_ABOVE = 1
SIDE_LEFT = 2
SIDE_RIGHT = 3

\ Queue tile (X, Y) and its four neighbours to be checked. Preserves A, X,
\ Y and the carry.
.support_note
{
    PHP
    PHA
    STX support_x
    STY support_y
    JSR push                    \ The tile
    DEX
    JSR push                    \ Left
    INX
    INX
    JSR push                    \ Right
    DEX
    DEY
    JSR push                    \ Above
    INY
    INY
    JSR push                    \ Below
    LDX support_x
    LDY support_y
    PLA
    PLP
    RTS
.push
    STY support_tmp
    LDY support_tail
    TXA
    STA support_queue_x,Y
    LDA support_tmp
    STA support_queue_y,Y
    INY
    TYA
    AND #SUPPORT_QUEUE - 1
    CMP support_head
    BEQ full                    \ Full: dropped (counted, for tests)
    STA support_tail
    LDY support_tmp
    RTS
.full
    INC support_lost
    LDY support_tmp
    RTS
}

\ Check the queued tiles, at most SUPPORT_CHECKS, while the packet has room
\ among its changed tiles.
.support_step
{
    LDA support_wait
    BEQ ready
    DEC support_wait
.ready
    LDA #SUPPORT_CHECKS
    STA support_checks
.check
    LDA para_changes
    CMP #CHANGES_PER_FRAME
    BCS done
    LDX support_head
    CPX support_tail
    BEQ done
    LDA support_queue_x,X
    STA support_x
    LDA support_queue_y,X
    STA support_y
    INX
    TXA
    AND #SUPPORT_QUEUE - 1
    STA support_head
    JSR support_check
    DEC support_checks
    BNE check
.done
    RTS
}

\ Work out the strength of the piece at (support_x, support_y) from its
\ neighbours (support.strengths, one step), and store it, or let it fall.
.support_check
{
    LDX support_x
    LDY support_y
    JSR tile_at
    STA support_material
    TAX
    LDA support_rule,X
    STA support_held_rule
    AND #7
    BNE piece
    RTS                         \ Not a piece that can fall
.piece
    STA support_held
    LDA zp_world_shape
    STA support_shape
    LDA #0
    STA support_best
    LDX #SIDE_BELOW             \ Each side the piece can be held from
.side
    STX support_side
    LDY support_held
    LDA side_allowed - 1,Y
    AND side_bit,X
    BEQ next
    JSR support_given
    CMP support_best
    BCC next
    STA support_best
.next
    LDX support_side
    INX
    CPX #4
    BNE side
    LDA support_shape           \ Changed?
    AND #STRENGTH_BITS
    CMP support_best
    BNE changed
    RTS
.changed
    LDA #0                      \ Nothing dropped, unless it falls
    STA support_drops
    LDA support_best
    BEQ fall
    LDA support_shape           \ A new strength
    AND #&FF - STRENGTH_BITS
    ORA support_best
    STA zp_world_new_shape
    LDA support_material
    JMP change
.fall
    LDA support_wait            \ Not yet: checked again first, next frame
    BEQ falls
    LDA support_head
    SEC
    SBC #1
    AND #SUPPORT_QUEUE - 1
    STA support_head
    LDA #1
    STA support_checks
    RTS
.falls
    LDA support_material        \ It may drop something
    STA support_drops
    LDA #FALL_FRAMES
    STA support_wait
    LDA support_shape           \ Sky or cave, as its background
    AND #BACKGROUND_SKY
    STA zp_world_new_shape
    BEQ cave
    LDA #TILE_SKY
    BNE change
.cave
    LDA #TILE_AIR
.change
    STA support_material
    LDX support_x
    LDY support_y
    JSR call_set_tile
    BCC set
    RTS                         \ The store is full: left as it was
.set
    LDA support_best            \ Fallen: what it drops, if anything
    BNE kept
    LDA support_drops
    LDX support_x
    LDY support_y
    JSR item_drop
.kept
    LDA support_x               \ In the tile cache too, and sent if it fell
    STA zp_fill_x
    LDA support_y
    STA zp_fill_y
    JSR in_tile_cache
    BCC done
    JSR para_cache_pointer
    LDY #0
    LDA support_material
    STA (para_cache),Y
    LDA para_cache + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA para_cache + 1
    LDA zp_world_new_shape
    STA (para_cache),Y
    LDA support_best
    BNE done
    JSR para_emit_change
.done
    RTS
}

\ The strength the neighbour on side support_side gives the piece being
\ checked, in A: its strength (less one from the side, for SPAN) if it
\ holds the piece there, else 0.
.support_given
{
    LDX support_x
    LDY support_y
    LDA support_side
    BEQ below
    CMP #SIDE_ABOVE
    BEQ above
    CMP #SIDE_LEFT
    BEQ left
    INX
    JMP look
.left
    DEX
    JMP look
.above
    DEY
    JMP look
.below
    INY
.look
    JSR tile_at
    TAX
    LDA support_rule,X          \ What it holds
    LSR A
    LSR A
    LSR A
    AND #3
    BEQ none
    CMP #SUPPORT_BEARS_ALL
    BEQ holds
    STA support_tmp
    LDA support_rule,X          \ Its own family and none other
    EOR support_held_rule
    AND #&E0
    BNE none
    LDA support_tmp
    CMP #SUPPORT_BEARS_UP
    BEQ up
    LDY support_held            \ FAMILY: the way the family is held
    LDA family_ways - 1,Y
    LDY support_side
    AND side_bit,Y
    BEQ none
    BNE holds
.up
    LDA support_side            \ UP: only what is above it
    BNE none
.holds
    LDA support_rule,X          \ Its strength: the span for terrain, else
    AND #7                      \ its shape's
    BNE piece
    LDA #SUPPORT_SPAN
    BNE strength
.piece
    LDA zp_world_shape
    AND #STRENGTH_BITS
.strength
    LDY support_held            \ Less one from the side, held by SPAN
    CPY #SUPPORT_HELD_SPAN
    BNE given
    LDY support_side
    CPY #SIDE_LEFT
    BCC given
    SEC
    SBC #1
    BCS given
.none
    LDA #0
.given
    RTS
}

\ Carry set if (zp_fill_x, zp_fill_y) is in the tile cache.
.in_tile_cache
{
    LDA zp_fill_y
    CMP cached_top
    BCC out
    LDA cached_bottom
    CMP zp_fill_y
    BCC out
    LDA zp_fill_x
    CMP cached_left
    BCC out
    LDA cached_right
    CMP zp_fill_x
    RTS                         \ Carry set if inside
.out
    CLC
    RTS
}

.side_bit
    EQUB 1, 2, 4, 8             \ Below, above, left, right
.side_allowed                   \ The sides each way of being held looks at
    EQUB 1, 2, 1 + 4 + 8, 15    \ Below, above, span, any
.family_ways                    \ The sides a family holds its own from
    EQUB 1, 2, 1 + 4 + 8, 0
