\ The pack screen, on the parasite (tools/stratagem/pack.py, which this does
\ exactly). PACK opens the pack and pauses the game: each frame's packet is
\ then the pack's, the kinds shown with their counts and the hand, which the
\ Z X K M move across them, and the crafting grid (crafting.asm), whose
\ keys come in the second byte of input. PACK again closes it, emptying the
\ grid back into the counts, and the next frame, the game's, has no input
\ and redraws the view whole.

\ The pack closed, the grid empty and the book too, at the start. Returns
\ A = 0.
.pack_init
{
    LDA #0                      \ Each kind of tool unworn
    LDX #KIND_COUNT - TOOL_FIRST - 1
.unworn
    STA tool_digs,X
    DEX
    BPL unworn
    LDA #CELL_EMPTY
    LDX #GRID_CELLS - 1
.empty
    STA craft_grid,X
    DEX
    BPL empty
    LDX #BELT_SLOTS - 1
.each_slot
    STA belt,X
    DEX
    BPL each_slot
    STA tool_last
    LDA #KIND_SOIL
    STA hand_kind
    LDA #RECIPE_COUNT - 1
    STA craft_copied
    LDA #0
    STA belt_slot
    STA tools_held
    STA zp_place_wait
    JSR tool_update             \ Bare hands
    LDA #0
    STA craft_book
    STA craft_repeat
    STA pack_open
    STA pack_held
    STA pack_keys_held
    RTS
}

\ Before the game's frame: return with carry set if the frame was the pack's
\ (its packet sent), carry clear for the game's, TAB having cycled the hand
\ if pressed.
.pack_input
{
    LDA #0
    STA pack_draw
    STA pack_moved
    STA pack_changed
    STA pack_closed
    LDA pack_held               \ Keys pressed since last frame
    EOR #&FF
    AND zp_input
    STA pack_pressed
    LDA zp_input
    STA pack_held
    LDA MAILBOX_KEYS            \ A cell's key, if not held last frame
    AND #KEY_CELL
    STA pack_cell
    LDA pack_keys_held
    AND #KEY_CELL
    CMP pack_cell
    BNE cell
    LDA #0
    STA pack_cell
.cell
    LDA MAILBOX_TOOLS           \ A function key, if not held last frame
    CMP tools_held
    STA tools_held
    BNE tool
    LDA #0
.tool
    STA tool_pressed
    LDA pack_keys_held          \ And of the second byte
    EOR #&FF
    AND MAILBOX_KEYS
    STA pack_keys_pressed
    LDA MAILBOX_KEYS
    STA pack_keys_held
    LDA pack_open
    BNE open
    BIT pack_pressed            \ INPUT_PACK is bit 7
    BPL game
    LDA #&FF
    STA pack_open
    STA pack_draw
    JSR craft_station           \ At a workbench?
    LDA #0                      \ The kinds shown, from those held now
    LDX #KIND_COUNT - 1
.unseen
    STA pack_seen,X
    DEX
    BPL unseen
    JSR pack_shown
    JMP sent
.game
    LDX tool_pressed            \ A function key: its slot in the tool hand
    BEQ no_tool
    DEX
    STX belt_slot
    JSR tool_update
.no_tool
    LDA pack_keys_pressed       \ TAB: the hand to the next kind
    AND #KEY_CYCLE
    BEQ play
    JSR hand_cycle
.play
    CLC
    RTS
.open
    BIT pack_pressed
    BPL moves
    JSR craft_clear             \ Closed: the grid back into the counts,
    JSR tool_update             \ the tool in use as it now is,
    LDA #0                      \ and the game's frame, with no input
    STA pack_open
    STA zp_input
    LDA #&FF
    STA pack_closed
    CLC
    RTS
.moves
    LDX pack_index
    LDA pack_pressed
    AND #INPUT_LEFT
    BEQ not_left
    TXA
    BEQ not_left
    DEX
.not_left
    LDA pack_pressed
    AND #INPUT_RIGHT
    BEQ not_right
    INX
    CPX pack_count
    BCC not_right
    DEX
.not_right
    LDA pack_pressed
    AND #INPUT_UP
    BEQ not_up
    CPX #PACK_COLUMNS
    BCC not_up
    TXA
    SBC #PACK_COLUMNS           \ (Carry set)
    TAX
.not_up
    LDA pack_pressed
    AND #INPUT_DOWN
    BEQ not_down
    TXA
    CLC
    ADC #PACK_COLUMNS
    CMP pack_count
    BCS not_down
    TAX
.not_down
    LDA pack_keys_pressed       \ TAB: the next kind, round again
    AND #KEY_NEXT
    BEQ not_next
    INX
    CPX pack_count
    BCC not_next
    LDX #0
.not_next
    CPX pack_index
    BEQ keys
    LDA pack_kinds,X
    STA hand
    LDA #&FF
    STA pack_moved
.keys
    JSR craft_keys
    LDA pack_count              \ A kind gained joins those shown: draw the
    PHA                         \ panel again
    JSR pack_shown
    PLA
    CMP pack_count
    BEQ sent
    LDA #&FF
    STA pack_draw
.sent
    JSR pack_send
    SEC
    RTS
}

\ Plan the camera; if the pack closed this frame, redraw the view whole.
.pack_plan_camera
{
    JSR plan_camera
    LDA pack_closed
    BEQ done
    LDA #&FF
    STA zp_redraw
    LDA #0
    STA zp_plan_dx
    STA zp_plan_dy
.done
    RTS
}

\ The grid's keys this frame: a cell's (pack_cell), DELETE, L (again
\ every MAKE_REPEAT frames while held, after MAKE_DELAY) and COPY. Set
\ pack_changed if the counts or the grid changed.
.craft_keys
{
    LDX #KIND_COUNT - 1         \ The counts and the grid, as they were
.counts
    LDA inventory,X
    STA pack_before,X
    DEX
    BPL counts
    LDX #GRID_CELLS - 1
.grid
    LDA craft_grid,X
    STA pack_before + KIND_COUNT,X
    DEX
    BPL grid
    LDX #BELT_SLOTS - 1
.each_slot
    LDA belt,X
    STA pack_before + KIND_COUNT + GRID_CELLS,X
    DEX
    BPL each_slot
    LDX tool_pressed            \ A function key, with a tool in hand: into
    BEQ no_tool                 \ its slot, or out if there already
    LDA hand
    CMP #TOOL_FIRST
    BCC no_tool
    DEX
    CMP belt,X
    BNE load
    LDA #CELL_EMPTY
.load
    STA belt,X
.no_tool
    LDX pack_cell               \ A cell's key, if it is in the grid
    BEQ no_cell
    DEX
    LDA grid_row,X
    CMP pack_size
    BCS no_cell
    LDA grid_column,X
    CMP pack_size
    BCS no_cell
    JSR craft_put
.no_cell
    LDA pack_keys_pressed
    AND #KEY_CLEAR
    BEQ no_clear
    JSR craft_clear
.no_clear
    LDA MAILBOX_KEYS
    AND #KEY_MAKE
    BEQ no_make
    LDA pack_keys_pressed
    AND #KEY_MAKE
    BEQ make_held
    LDA #MAKE_DELAY
    STA craft_repeat
    BNE make                    \ Always branches
.make_held
    DEC craft_repeat
    BNE no_make
    LDA #MAKE_REPEAT
    STA craft_repeat
.make
    JSR craft_make
.no_make
    LDA pack_keys_pressed
    AND #KEY_BOOK
    BEQ no_copy
    JSR craft_copy
.no_copy
    LDX #KIND_COUNT - 1         \ Changed?
.counts_changed
    LDA inventory,X
    CMP pack_before,X
    BNE changed
    DEX
    BPL counts_changed
    LDX #GRID_CELLS - 1
.grid_changed
    LDA craft_grid,X
    CMP pack_before + KIND_COUNT,X
    BNE changed
    DEX
    BPL grid_changed
    LDX #BELT_SLOTS - 1
.belt_changed
    LDA belt,X
    CMP pack_before + KIND_COUNT + GRID_CELLS,X
    BNE changed
    DEX
    BPL belt_changed
    RTS
.changed
    LDA #&FF
    STA pack_changed
    RTS
}

\ Set pack_kinds to the kinds shown (those held, and those shown since
\ opening: pack_seen), pack_count to how many, and pack_index to the
\ hand's place among them; if the hand isn't among them, it moves to the
\ first (pack_index 0, whether or not any are shown).
.pack_shown
{
    LDY #0
    STY pack_index
    STY pack_i
    LDX #0
.loop
    LDA inventory,X
    BNE show
    LDA pack_seen,X
    BEQ next
.show
    LDA #&FF
    STA pack_seen,X
    CPX hand
    BNE not_hand
    STY pack_index
    STA pack_i                  \ (Non-zero: the hand is shown)
.not_hand
    TXA
    STA pack_kinds,Y
    INY
.next
    INX
    CPX #KIND_COUNT
    BNE loop
    STY pack_count
    LDA pack_i
    BNE done
    TYA
    BEQ done                    \ Nothing shown: the hand stays
    LDA pack_kinds
    STA hand
.done
    RTS
}

\ Write the pack's packet (tube_layout.asm) and send it.
.pack_send
{
    LDA para_sent               \ This frame's buffer
    LSR A
    BCS second
    LDA #LO(PACKET_BUFFER_0)
    STA para_packet
    LDA #HI(PACKET_BUFFER_0)
    BNE buffer_set              \ Always branches
.second
    LDA #LO(PACKET_BUFFER_1)
    STA para_packet
    LDA #HI(PACKET_BUFFER_1)
.buffer_set
    STA para_packet + 1
    LDY #0
    LDA pack_moved
    AND #PACKET_PACK_MOVED
    STA pack_i
    LDA pack_changed
    AND #PACKET_PACK_CHANGED
    ORA pack_i
    STA pack_i
    LDA pack_draw
    AND #PACKET_PACK_DRAW
    ORA pack_i
    ORA #PACKET_PACK
    STA (para_packet),Y
    INY
    LDA pack_count
    STA (para_packet),Y
    INY
    LDA pack_index
    STA (para_packet),Y
    INY
    LDX #0
.loop
    CPX pack_count
    BEQ done
    STX pack_i
    LDA pack_kinds,X
    STA (para_packet),Y
    INY
    TAX
    LDA inventory,X
    STA (para_packet),Y
    INY
    LDX pack_i
    INX
    BNE loop                    \ Always branches
.done
    LDA pack_size               \ The grid's size and cells
    STA (para_packet),Y
    INY
    LDX #0
.grid
    LDA craft_grid,X
    STA (para_packet),Y
    INY
    INX
    CPX #GRID_CELLS
    BNE grid
    STY pack_i                  \ What it makes and how many, if anything
    JSR craft_match
    BNE made
    LDX #RECIPE_COUNT           \ (Nothing: CELL_EMPTY and 0)
.made
    LDY pack_i
    LDA recipe_makes,X
    STA (para_packet),Y
    INY
    LDA recipe_count,X
    STA (para_packet),Y
    INY
    LDX #0                      \ The belt, and the slot in the tool hand
.each_slot
    LDA belt,X
    STA (para_packet),Y
    INY
    INX
    CPX #BELT_SLOTS
    BNE each_slot
    LDA belt_slot
    STA (para_packet),Y
    JMP para_send
}
