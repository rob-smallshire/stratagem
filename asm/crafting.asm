\ Crafting, on the parasite (tools/stratagem/crafting.py, which this does
\ exactly): the grid, GRID_MAX cells square by rows, a kind or CELL_EMPTY each,
\ whose contents have been taken from the counts; the recipes, each a shape
\ (build/generated/crafting.asm); and the recipe book, a bit for each recipe made.

\ A cell's key, cell X: the hand's kind into it, from its count; the same
\ kind back out; or another kind back out and the hand's in, if there is
\ one to put.
.craft_put
{
    STX craft_cell
    LDA craft_grid,X
    CMP #CELL_EMPTY
    BEQ put
    PHA
    JSR inventory_gain
    LDX craft_cell
    LDA #CELL_EMPTY
    STA craft_grid,X
    PLA
    CMP hand
    BEQ done
.put
    LDY hand
    LDA inventory,Y
    BEQ done
    TYA
    TAX
    DEC inventory,X
    LDX craft_cell
    STA craft_grid,X
.done
    RTS
}

\ DELETE: everything in the grid back to the counts.
.craft_clear
{
    LDX #GRID_CELLS - 1
.loop
    STX craft_cell
    LDA craft_grid,X
    CMP #CELL_EMPTY
    BEQ next
    JSR inventory_gain
    LDX craft_cell
    LDA #CELL_EMPTY
    STA craft_grid,X
.next
    DEX
    BPL loop
    RTS
}

\ Lay recipe X's shape out in the empty grid from its top left, each cell
\ from the counts, left empty if its kind has run out.
.craft_lay_out
{
    LDA recipe_width,X
    STA craft_width
    LDA recipe_height,X
    STA craft_height
    LDA recipe_first,X          \ craft_k: the recipe's cell in recipe_shapes
    STA craft_k
    LDA #0
    STA craft_row
.row
    LDA craft_row
    ASL A                       \ The row's first grid cell: row * 3
    ADC craft_row               \ (Carry clear)
    STA craft_cell
    LDA craft_width
    STA craft_column
.cell
    LDX craft_k
    LDY recipe_shapes,X
    CPY #CELL_EMPTY
    BEQ next
    LDA inventory,Y
    BEQ next
    TYA
    TAX
    DEC inventory,X
    LDX craft_cell
    STA craft_grid,X
.next
    INC craft_k
    INC craft_cell
    DEC craft_column
    BNE cell
    INC craft_row
    LDA craft_row
    CMP craft_height
    BNE row
    RTS
}
ASSERT GRID_MAX = 3

\ Return in X the recipe the grid lays out, if any can be made at the
\ station (pack_station), with the zero flag clear; otherwise set.
.craft_match
{
    LDA #GRID_MAX               \ The rows and columns with anything in them
    STA craft_top
    STA craft_left
    LDA #0
    STA craft_bottom
    STA craft_right
    LDX #GRID_CELLS - 1
.find
    LDA craft_grid,X
    CMP #CELL_EMPTY
    BEQ found
    LDA grid_row,X
    CMP craft_top
    BCS not_top
    STA craft_top
.not_top
    CMP craft_bottom
    BCC not_bottom
    STA craft_bottom
.not_bottom
    LDA grid_column,X
    CMP craft_left
    BCS not_left
    STA craft_left
.not_left
    CMP craft_right
    BCC found
    STA craft_right
.found
    DEX
    BPL find
    LDA craft_top
    CMP #GRID_MAX
    BEQ none                    \ The grid is empty
    LDA craft_bottom            \ The shape's size
    SEC
    SBC craft_top
    STA craft_height
    INC craft_height
    LDA craft_right
    SEC
    SBC craft_left
    STA craft_width
    INC craft_width
    LDX #0
.recipe
    LDA recipe_station,X
    CMP pack_station
    BEQ station
    BCS next
.station
    LDA recipe_width,X
    CMP craft_width
    BNE next
    LDA recipe_height,X
    CMP craft_height
    BNE next
    STX craft_recipe
    JSR craft_compare
    LDX craft_recipe
    BCS matched
.next
    INX
    CPX #RECIPE_COUNT
    BNE recipe
.none
    LDA #0                      \ Zero flag set
    RTS
.matched
    LDA #&FF                    \ Zero flag clear
    RTS
}

\ Return with carry set if the grid, trimmed (craft_top, craft_left,
\ craft_width, craft_height), is recipe X's shape.
.craft_compare
{
    LDA recipe_first,X
    STA craft_k
    LDA craft_top
    STA craft_row
.row
    LDA craft_row               \ The row's first cell: row * 3 + left
    ASL A
    ADC craft_row               \ (Carry clear)
    ADC craft_left
    STA craft_cell
    LDA craft_width
    STA craft_column
.cell
    LDX craft_cell
    LDA craft_grid,X
    LDX craft_k
    CMP recipe_shapes,X
    BNE differs
    INC craft_k
    INC craft_cell
    DEC craft_column
    BNE cell
    INC craft_row
    LDA craft_row
    SEC
    SBC craft_top
    CMP craft_height
    BNE row
    SEC
    RTS
.differs
    CLC
    RTS
}

\ L (make): if the grid lays out a recipe, make it: its count of what it
\ makes, into the counts; put it in the book; and lay its shape out again
\ from the counts.
.craft_make
{
    JSR craft_match
    BEQ done
    STX craft_recipe
    LDA recipe_count,X
    STA craft_k
.gain
    LDX craft_recipe
    LDA recipe_makes,X
    JSR inventory_gain
    DEC craft_k
    BNE gain
    LDX craft_recipe
    LDA craft_book
    ORA recipe_bit,X
    STA craft_book
    LDA #CELL_EMPTY                  \ The ingredients were spent: the grid empty
    LDY #GRID_CELLS - 1
.empty
    STA craft_grid,Y
    DEY
    BPL empty
    JMP craft_lay_out
.done
    RTS
}

\ COPY: the grid emptied, and the next recipe in the book after the one
\ last copied (round again) that the station makes laid out from the
\ counts, unless there is none.
.craft_copy
{
    LDX craft_copied
    LDY #RECIPE_COUNT
.loop
    INX
    CPX #RECIPE_COUNT
    BCC in_range
    LDX #0
.in_range
    LDA craft_book
    AND recipe_bit,X
    BEQ next
    LDA recipe_station,X
    CMP pack_station
    BEQ found
    BCC found
.next
    DEY
    BNE loop
    RTS
.found
    STX craft_copied
    JSR craft_clear
    LDX craft_copied
    JMP craft_lay_out
}

.grid_row
    FOR cell, 0, GRID_CELLS - 1
        EQUB cell DIV GRID_MAX
    NEXT
.grid_column
    FOR cell, 0, GRID_CELLS - 1
        EQUB cell MOD GRID_MAX
    NEXT
.recipe_bit
    FOR recipe, 0, RECIPE_COUNT - 1
        EQUB 1 << recipe
    NEXT
.grid_sizes                     \ By station
    GRID_SIZES
.recipe_width                   \ By recipe: its shape's size...
    RECIPE_WIDTHS
.recipe_height
    RECIPE_HEIGHTS
.recipe_makes                   \ ... what it makes, and how many...
    RECIPE_MAKES
    EQUB CELL_EMPTY             \ (After the recipes: nothing)
.recipe_count
    RECIPE_COUNTS
    EQUB 0
.recipe_station                 \ ... where...
    RECIPE_STATIONS
.recipe_first                   \ ... and its first cell in recipe_shapes
    RECIPE_FIRSTS
.recipe_shapes                  \ Each recipe's cells, by rows
    RECIPE_SHAPES
