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
.starting_counts                \ The counts the miner starts with
    COUNTS_AT_START

\ The tool in use: the tool hand's, the belt's slot's (or bare hands). Copy
\ its quarters a dig removes, by material, into material_quarters
\ (actions.TOOL_QUARTERS): at the start, when a belt key chooses a slot,
\ when the pack closes and when a tool breaks.
.tool_update
{
    LDY #0                      \ Bare hands: the first row
    LDX belt_slot
    LDA belt,X
    CMP #CELL_EMPTY
    BEQ row
    SEC                         \ Row kind - TOOL_FIRST + 1
    SBC #TOOL_FIRST - 1
    TAX
.times
    TYA
    CLC
    ADC #MATERIAL_COUNT
    TAY
    DEX
    BNE times
.row
    LDX #0
.copy
    LDA tool_quarters,Y
    STA material_quarters,X
    INY
    INX
    CPX #MATERIAL_COUNT
    BNE copy
    RTS
}

\ A dig, not a tree's part's chop (chopped), wears the tool in use, its
\ belt slot's: at its durability'th dig it breaks, and the slot is empty
\ (actions._dug).
.tool_wear
{
    LDA chopped
    BNE done
    LDX belt_slot
    LDY belt,X
    CPY #CELL_EMPTY
    BEQ done
    INC belt_wear,X
    LDA belt_wear,X
    CMP tool_durability - TOOL_FIRST,Y
    BCS broken
.done
    RTS
.broken
    LDA #&FF                    \ Shown (items.asm)
    STA zp_tool_broke
    LDA #CELL_EMPTY
    STA belt,X
    LDA #0
    STA belt_wear,X
    JMP tool_update
}

.tool_quarters                  \ By tool, bare hands first: quarters by material
    TOOL_QUARTERS
.tool_durability                \ By tool: digs before it breaks
    TOOL_DURABILITY
