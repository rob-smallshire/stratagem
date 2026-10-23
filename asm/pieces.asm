\ Pieces, on the parasite (docs/tile-set.md, tiles.py): materials drawn
\ whole over a backdrop (the torch, so far). The host composes each pair of
\ piece and backdrop into a slot, once, and draws the slot as an ordinary
\ material, so its renderer is unchanged. Here, each pair in the tile cache
\ is given a slot as its tiles are sent; a new slot's pair goes ahead of the
\ tile in the packet (PIECE_COMPOSE, the slot, the piece, the backdrop),
\ for the host to compose before it reads the tile. When no slot is free,
\ the tile cache is swept, and slots whose pairs are no longer in it are
\ freed. If there are still none, the piece is sent as its backdrop alone.
\
\ A pair is piece index * 2 + backdrop (1 for the sky), + FRONT_PAIR for a
\ piece in front (PIECE_FRONT), which the host composes in the sprite
\ colour group. The light looks a piece tile's slot up to find the
\ graphics the host draws it with, and the slot's visibility
\ (pair_visibility, copied in when the slot is given, the same in front
\ as behind), as it would a material's.

PIECE_NO_SLOT = &FF

\ Free every slot.
.piece_init
{
    LDA #PIECE_NO_SLOT
    LDX #SLOT_COUNT - 1
.slots
    STA slot_pair,X
    DEX
    BPL slots
    LDX #FRONT_PAIR + PIECE_COUNT * 2 - 1
.pairs
    STA pair_slot,X
    DEX
    BPL pairs
    RTS
}

\ The pair of the piece tile with material A and shape X, in A.
.piece_pair_of
{
    SEC
    SBC #FIRST_PIECE
    ASL A
    CPX #PIECE_FRONT            \ In front?
    BCC behind
    ORA #FRONT_PAIR
.behind
    PHA
    TXA
    AND #BACKGROUND_SKY
    CMP #BACKGROUND_SKY         \ Carry: the sky
    PLA
    ADC #0
    RTS
}
ASSERT PIECE_FRONT = &80 AND BACKGROUND_SKY = &40 AND SHAPE_BITS < BACKGROUND_SKY

\ The tile the host shows for the piece tile with material A and shape X:
\ its slot's, in A (material) and X (shape), or its backdrop's if it has no
\ slot. Preserves Y.
.piece_shown
{
    PHA
    JSR piece_pair_of
    STX piece_shape
    TAX
    PLA
    LDA pair_slot,X
    CMP #PIECE_NO_SLOT
    BNE slot_shown
    LDA piece_shape             \ No slot: the backdrop, whole
    AND #BACKGROUND_SKY
    TAX
    BEQ cave
    LDA #TILE_SKY
    RTS
.cave
    LDA #TILE_AIR
    RTS
}

\ The tile the host is sent for slot A: material in A, shape in X.
\ Preserves Y.
.slot_shown
{
    PHA
    AND #3
    TAX
    LDA slot_shapes,X
    STA piece_shape
    PLA
    PHA
    AND #4
    BEQ cave
    LDA #BACKGROUND_SKY
    ORA piece_shape
    STA piece_shape
.cave
    PLA
    LSR A
    LSR A
    LSR A
    CLC
    ADC #SLOT_MATERIAL
    LDX piece_shape
    RTS
}

\ The slot for the piece tile with material A and shape X, giving it one if
\ it has none: in X, with carry set if it is new (the host must compose it),
\ or X = PIECE_NO_SLOT if none can be had.
.piece_slot
{
    JSR piece_pair_of
    STA piece_pair
    TAX
    LDA pair_slot,X
    CMP #PIECE_NO_SLOT
    BEQ give
    TAX
    CLC
    RTS
.give
    JSR slot_find_free
    BCC found
    JSR slot_sweep
    JSR slot_find_free
    BCC found
    LDX #PIECE_NO_SLOT
    CLC
    RTS
.found
    LDA piece_pair
    STA slot_pair,X
    TXA
    LDX piece_pair
    STA pair_slot,X
    TAX
    STX piece_slot_found        \ The slot's visibility, slot * 8 onwards,
    LDA #0                      \ from the pair's, pair * 8 onwards
    STA piece_ptr + 1
    TXA
    ASL A
    ROL piece_ptr + 1
    ASL A
    ROL piece_ptr + 1
    ASL A
    ROL piece_ptr + 1
    CLC
    ADC #LO(slot_visibility_even)
    STA piece_ptr
    LDA piece_ptr + 1
    ADC #HI(slot_visibility_even)
    STA piece_ptr + 1
    LDA piece_pair              \ (The same in front as behind)
    AND #FRONT_PAIR - 1
    ASL A
    ASL A
    ASL A
    ORA #7
    TAX
    LDY #7
.visibility
    LDA pair_visibility_even,X
    STA (piece_ptr),Y
    INC piece_ptr + 1           \ The odd parity's, two pages on
    INC piece_ptr + 1
    LDA pair_visibility_odd,X
    STA (piece_ptr),Y
    DEC piece_ptr + 1
    DEC piece_ptr + 1
    DEX
    DEY
    BPL visibility
    LDX piece_slot_found
    SEC
    RTS
}
ASSERT PIECE_COUNT * 2 * 8 <= &100
ASSERT slot_visibility_odd = slot_visibility_even + &200

\ A free slot in X, carry clear; carry set if there is none.
.slot_find_free
{
    LDX #SLOT_COUNT - 1
.loop
    LDA slot_pair,X
    CMP #PIECE_NO_SLOT
    BEQ found
    DEX
    BPL loop
    SEC
    RTS
.found
    CLC
    RTS
}

\ Free the slots whose pairs have no tile in the tile cache.
.slot_sweep
{
    LDA #0
    LDX #SLOT_COUNT - 1
.clear
    STA slot_mark,X
    DEX
    BPL clear
    FOR page, 0, 3
        LDY #0
    .scan
        LDA tile_cache + page * &100,Y
        CMP #FIRST_PIECE
        BCC next
        CMP #FIRST_PIECE + PIECE_COUNT
        BCS next
        LDX tile_cache_shapes + page * &100,Y
        JSR piece_pair_of
        TAX
        LDA pair_slot,X
        CMP #PIECE_NO_SLOT
        BEQ next
        TAX
        LDA #&FF
        STA slot_mark,X
    .next
        INY
        BNE scan
    NEXT
    LDX #SLOT_COUNT - 1
.free
    LDA slot_mark,X
    BNE kept
    LDY slot_pair,X
    CPY #PIECE_NO_SLOT
    BEQ kept
    LDA #PIECE_NO_SLOT
    STA pair_slot,Y
    STA slot_pair,X
.kept
    DEX
    BPL free
    RTS
}
ASSERT TILE_CACHE_SIZE * TILE_CACHE_SIZE = 4 * &100

.slot_shapes
    SLOT_SHAPES
