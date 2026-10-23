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

.material_yields                \ The kind each material yields when dug, &FF if none
    MATERIAL_YIELDS
.kind_places                    \ The material each kind places, &FF if none
    KIND_PLACES
