\ The miner's inventory, modelled by tools/stratagem/inventory.py: a count
\ of each kind carried, up to COUNT_MAX, and the kind in hand.

\ One more of kind A, unless there are COUNT_MAX already.
.inventory_gain
{
    TAX
    LDA inventory,X
    CMP #COUNT_MAX
    BCS full
    INC inventory,X
.full
    RTS
}

\ Move the hand to the next kind after it, in kind order and round again,
\ that is held and places something; leave it if there is none.
.hand_cycle
{
    LDX hand
    LDY #KIND_COUNT
.loop
    INX
    CPX #KIND_COUNT
    BCC in_range
    LDX #0
.in_range
    LDA kind_places,X
    BMI next
    LDA inventory,X
    BNE found
.next
    DEY
    BNE loop
    RTS
.found
    STX hand
    RTS
}

.material_yields                \ The kind each material yields when dug, &FF if none
    MATERIAL_YIELDS
.kind_places                    \ The material each kind places, &FF if none
    KIND_PLACES
