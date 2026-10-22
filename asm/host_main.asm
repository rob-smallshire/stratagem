\ MAIN, for the Tube game: the host's side of each frame, in program RAM.
\ The parasite runs the game and sends a packet a frame (tube_layout.asm);
\ the host reads it, writes the input it reads into the parasite's mailbox,
\ and draws: a new row into the hidden row, then
\ at vertical sync the flip, the new columns ahead of the beam, the changed
\ tile, the light's draw list (read from the Tube as it draws), the sprite
\ and the items.

CLEAR USER_START, USER_END
ORG USER_START
GUARD USER_END

.host_main_start

\ Negative INKEY numbers, as OSBYTE &81 takes them in X
INKEY_Z = &100 - 98
INKEY_X = &100 - 67
INKEY_K = &100 - 71
INKEY_M = &100 - 102
INKEY_L = &100 - 87
INKEY_SPACE = &100 - 99
INKEY_T = &100 - 36

\ The host's start: a clear, narrowed screen.
.host_init
{
    LDA #0
    STA zp_sprite_drawn
    STA zp_columns_width
    STA redraw_tile
    STA host_changes
    STA host_frames
    STA host_expect
    STA host_frame_count
    LDA #LO(SCREEN_START)
    STA zp_screen_start
    LDA #HI(SCREEN_START)
    STA zp_screen_start + 1
    JSR setup_screen
    JSR call_render_clear
    JMP set_crtc_start
}

\ Read and draw the frame in packet buffer host_buffer.
.host_frame
{
    LDY #0                      \ The packet's first part
    LDX #LO(PACKET_BUFFER_0)
    LDA #HI(PACKET_BUFFER_0)
    LDY host_buffer
    BEQ buffer_set
    LDX #LO(PACKET_BUFFER_1)
    LDA #HI(PACKET_BUFFER_1)
.buffer_set
    JSR host_read_from
    READ_BYTE
    STA host_flags
    READ_BYTE
    STA zp_plan_dx
    READ_BYTE
    STA zp_plan_dy
    READ_BYTE
    STA zp_camera_x
    READ_BYTE
    STA zp_camera_x + 1
    READ_BYTE
    STA zp_camera_y
    READ_BYTE
    STA zp_camera_y + 1
    READ_BYTE
    STA zp_player_x
    READ_BYTE
    STA zp_player_x + 1
    READ_BYTE
    STA zp_player_y
    READ_BYTE
    STA zp_player_y + 1
    READ_BYTE
    STA zp_player_frame
    READ_BYTE                   \ New tiles, in strips
    STA host_strips
    BEQ strips_done
.strip
    READ_BYTE
    STA host_down
    READ_BYTE
    STA host_tile_x
    READ_BYTE
    STA host_tile_y
    READ_BYTE
    STA host_count
.strip_tile
    JSR host_read_tile
    LDA host_down
    BNE down
    INC host_tile_x
    JMP strip_next
.down
    INC host_tile_y
.strip_next
    DEC host_count
    BNE strip_tile
    DEC host_strips
    BNE strip
.strips_done
    READ_BYTE                   \ Changed tiles, to redraw at the flip
    STA host_changes
    BEQ changes_done
    LDX #0
.change
    STX host_change
    READ_BYTE
    STA host_tile_x
    STA host_change_x,X
    READ_BYTE
    STA host_tile_y
    STA host_change_y,X
    JSR host_read_tile
    LDX host_change
    INX
    CPX host_changes
    BNE change
.changes_done
    JSR host_store
.*host_stored                   \ (For timing)
    READ_BYTE                   \ A chunk to fetch
    STA host_fetch_slot
    BEQ no_fetch
    READ_BYTE
    STA host_fetch_to
    READ_BYTE
    STA host_fetch_to + 1
.no_fetch
    READ_BYTE                   \ The items to draw
    TAX
    AND #ITEMS_UNTOUCHED
    STA host_items_untouched
    TXA
    AND #&FF - ITEMS_UNTOUCHED
    STA host_items
    BEQ items_read
    LDX #0
.item
    READ_BYTE
    STA host_item_column,X
    READ_BYTE
    STA host_item_line,X
    READ_BYTE
    STA host_item_frame,X
    INX
    CPX host_items
    BNE item
.items_read
    JSR host_release
    LDA host_fetch_slot         \ Copied before the mailbox, so it is there
    BEQ fetched                 \ when the parasite's next frame starts
    JSR host_fetch
.fetched
.*host_fetch_done               \ (For timing)

    JSR read_input              \ The input, to the parasite's mailbox
    INC host_frames
    JSR host_claim
    LDA #LO(MAILBOX_INPUT)
    STA host_transfer
    LDA #0
    STA host_transfer + 1
    LDA #TUBE_BYTES_TO_PARASITE
    LDX #LO(host_transfer)
    LDY #HI(host_transfer)
    JSR TUBE_ENTRY
    LDA zp_input
    JSR host_write_byte
    LDA host_frames
    JSR host_write_byte
    JSR host_release

    LDA host_flags              \ The plan: the whole view, or the new row
    BEQ move                    \ (into the hidden row) and new columns
    JSR draw_view
    JMP flip
.move
    JSR move_screen_start
    LDA zp_plan_dy
    BEQ no_row
    JSR draw_new_row
.no_row
    LDA zp_plan_dx
    BEQ flip
    JSR plan_new_columns

.flip
.*host_before_vsync             \ (For timing)
    LDA #19                     \ Wait for vertical sync
    JSR OSBYTE
.*host_after_vsync
    \ After vertical sync, staying ahead of the beam: the new start address;
    \ the new columns' rows above the sprite, which the beam reaches first;
    \ the changed tile and the light's list, with the items and the sprite
    \ off; the sprite; the rest of the new columns; then the items, last so
    \ as not to delay the columns (they are never drawn where new columns
    \ or rows go: items.asm).
    JSR set_crtc_start
    JSR sprite_split_row
    LDA #0
    LDX zp_split_row
    JSR draw_column_rows
    JSR call_restore_items
    JSR restore_sprite
    JSR host_redraw_changes
    JSR host_light
    JSR draw_sprite
    LDA #VIEW_ROWS
    SEC
    SBC zp_split_row
    TAX
    LDA zp_split_row
    JSR draw_column_rows
    JSR call_render_items
    LDA #0
    STA zp_columns_width
    INC host_frame_count
.*host_frame_shown              \ Tests stop here
    RTS
}

\ The packet's changes to the store of changed chunks (the parasite's
\ store_emit): copy each into the store's banks, slot n (from 1) at &8000 +
\ ((n - 1) MOD 128) * 128 of bank (n - 1) DIV 128, as the parasite holds it.
.host_store
{
    READ_BYTE
    STA host_store_count
    BNE change
    RTS
.change
    READ_BYTE                   \ The slot
    JSR host_chunk_at
    LDA host_chunk
    STA chunk_to + 1
    STA material_to + 1
    ORA #CHUNK_TILES
    STA shape_to + 1
    LDA host_chunk + 1
    STA chunk_to + 2
    STA material_to + 2
    STA shape_to + 2
    READ_BYTE                   \ The offset
    CMP #STORE_CHUNK
    BEQ chunk
    TAY                         \ A tile
    READ_BYTE
.*material_to
    STA &8000,Y
    READ_BYTE
.*shape_to
    STA &8000,Y
    JMP next
.chunk
    LDY #0
.chunk_loop
    READ_BYTE
.*chunk_to
    STA &8000,Y
    INY
    CPY #SLOT_BYTES
    BNE chunk_loop
.next
    DEC host_store_count
    BEQ done
    JMP change
.done
    LDA zp_romsel_game
    SELECT_ROMSEL
    RTS
}

\ Page in the bank of slot A of the store (from 1), and point host_chunk at
\ its chunk.
.host_chunk_at
{
    SEC
    SBC #1
    TAY
    LSR A
    AND #&3F
    ORA #&80
    STA host_chunk + 1
    LDA #0
    ROR A
    STA host_chunk
    TYA
    ASL A
    LDA #0
    ROL A
    TAX
    LDA host_store_banks,X
    SELECT_ROMSEL
    RTS
}

\ Copy chunk host_fetch_slot of the store to the parasite, at host_fetch_to.
.host_fetch
{
    JSR host_claim
    LDA host_fetch_to
    STA host_transfer
    LDA host_fetch_to + 1
    STA host_transfer + 1
    LDA #TUBE_BYTES_TO_PARASITE
    LDX #LO(host_transfer)
    LDY #HI(host_transfer)
    JSR TUBE_ENTRY
    LDA host_fetch_slot
    JSR host_chunk_at
    LDA host_chunk
    STA from + 1
    LDA host_chunk + 1
    STA from + 2
    LDY #0
.loop
.from
    LDA &8000,Y
    JSR host_write_byte
    INY
    CPY #SLOT_BYTES
    BNE loop
    LDA zp_romsel_game
    SELECT_ROMSEL
    JMP host_release
}

\ Tell the parasite that the chunk it asked for at once is there.
.host_fetched
{
    JSR host_claim
    LDA #MAILBOX_FETCHED
    STA host_transfer
    LDA #0
    STA host_transfer + 1
    LDA #TUBE_BYTES_TO_PARASITE
    LDX #LO(host_transfer)
    LDY #HI(host_transfer)
    JSR TUBE_ENTRY
    LDA #&FF
    JSR host_write_byte
    JMP host_release
}

\ Redraw the changed tiles.
.host_redraw_changes
{
    LDX #0
.loop
    CPX host_changes
    BEQ done
    STX host_change
    LDA host_change_x,X
    STA target_x
    LDA host_change_y,X
    STA target_y
    JSR redraw_target
    LDX host_change
    INX
    BNE loop
.done
    RTS
}

\ Draw the light's draw list, in the list buffer for host_buffer, read from
\ the Tube as it is drawn.
.host_light
{
    LDX #LO(LIST_BUFFER_0)
    LDA #HI(LIST_BUFFER_0)
    LDY host_buffer
    BEQ buffer_set
    LDX #LO(LIST_BUFFER_1)
    LDA #HI(LIST_BUFFER_1)
.buffer_set
    JSR host_read_from
    JSR call_render_light
    JMP host_release
}

\ Claim the Tube and start reading bytes from parasite address AX.
.host_read_from
{
    STX host_transfer
    STA host_transfer + 1
    JSR host_claim
    LDA #TUBE_BYTES_TO_HOST
    LDX #LO(host_transfer)
    LDY #HI(host_transfer)
    JMP TUBE_ENTRY
}

\ Write A to the parasite, when there is room.
.host_write_byte
{
.wait
    BIT TUBE_R3_STATUS
    BVC wait
    STA TUBE_R3
    RTS
}

\ Read a tile (material, shape, light) into the tile cache at
\ (host_tile_x, host_tile_y).
.host_read_tile
{
    LDA host_tile_y             \ tile_cache + (y MOD 32) * 32 + (x MOD 32)
    AND #TILE_CACHE_SIZE - 1
    LSR A
    LSR A
    LSR A
    CLC
    ADC #HI(tile_cache)
    STA zp_ptr + 1
    LDA host_tile_y
    ASL A
    ASL A
    ASL A
    ASL A
    ASL A
    STA zp_ptr
    LDA host_tile_x
    AND #TILE_CACHE_SIZE - 1
    ORA zp_ptr
    STA zp_ptr
    LDY #0
    READ_BYTE
    CMP #PIECE_COMPOSE          \ A slot to compose first?
    BNE material
    JSR host_compose
    LDY #0
    READ_BYTE
.material
    STA (zp_ptr),Y
    LDA zp_ptr + 1
    CLC
    ADC #HI(tile_cache_shapes - tile_cache)
    STA zp_ptr + 1
    READ_BYTE
    STA (zp_ptr),Y
    LDA zp_ptr + 1
    CLC
    ADC #HI(tile_cache_light - tile_cache_shapes)
    STA zp_ptr + 1
    READ_BYTE
    STA (zp_ptr),Y
    RTS
}

\ Read a slot, a piece and a backdrop from the parasite, and compose the
\ piece over the backdrop into the slot's graphics (tiles.compose): the
\ backdrop where the piece's mask is set, and the piece. The slots are in
\ the render bank, paged in without the screen, so that the library here in
\ program RAM can be read. Preserves zp_ptr.
.host_compose
{
    READ_BYTE                   \ The slot's graphics: SLOT_GRAPHICS + slot * 64
    STA host_compose_slot
    LSR A
    LSR A
    CLC
    ADC #HI(SLOT_GRAPHICS)
    STA zp_screen + 1
    LDA host_compose_slot
    ROR A                       \ (Carry clear from the ADC)
    ROR A
    ROR A
    AND #&C0
    STA zp_screen
    READ_BYTE                   \ The piece: piece_library + piece * 128
    STA host_compose_pair
    LSR A
    TAX
    LDA #0
    ROR A
    STA zp_tile
    STA zp_mask
    TXA
    CLC
    ADC #HI(piece_library)
    STA zp_tile + 1
    STA zp_mask + 1
    LDA zp_mask                 \ ... its mask, 64 bytes on
    ORA #64
    STA zp_mask
    READ_BYTE                   \ The backdrop: backdrop_library + backdrop * 64
    TAX
    ASL host_compose_pair       \ The pair, for tests
    ORA host_compose_pair
    LDY host_compose_slot
    STA host_slot_pair,Y
    TXA
    LSR A
    ROR A
    ROR A
    STA zp_screen_lower
    LDA #HI(backdrop_library)
    STA zp_screen_lower + 1
.*host_compose_start            \ (For timing)
    LDA zp_romsel_compose
    STA ROMSEL_COPY
    STA ROMSEL
    LDY #63
.loop
    LDA (zp_screen_lower),Y
    AND (zp_mask),Y
    ORA (zp_tile),Y
    STA (zp_screen),Y
    DEY
    BPL loop
    LDA zp_romsel_game
    STA ROMSEL_COPY
    STA ROMSEL
.*host_compose_end
    RTS
}
ASSERT LO(piece_library) = 0 AND LO(backdrop_library) = 0
SLOT_GRAPHICS = HOST_MATERIAL_PAGES + SLOT_MATERIAL * &200

.host_compose_slot  EQUB 0
.host_compose_pair  EQUB 0

\ ---------------------------------------------------------------------------
\ Input

.read_input
{
    LDA #0
    STA zp_input
    LDX #INKEY_Z
    LDA #INPUT_LEFT
    JSR read_key
    LDX #INKEY_X
    LDA #INPUT_RIGHT
    JSR read_key
    LDX #INKEY_K
    LDA #INPUT_UP
    JSR read_key
    LDX #INKEY_M
    LDA #INPUT_DOWN
    JSR read_key
    LDX #INKEY_L
    LDA #INPUT_ACTION
    JSR read_key
    LDX #INKEY_SPACE
    LDA #INPUT_PLACE
    JSR read_key
    LDX #INKEY_T
    LDA #INPUT_TORCH
    \ Fall through
}

\ If the key with negative INKEY number X is pressed, set bits A in zp_input.
.read_key
{
    PHA
    LDA #&81
    LDY #&FF
    JSR OSBYTE
    PLA
    CPX #&FF
    BNE done
    ORA zp_input
    STA zp_input
.done
    RTS
}

INCLUDE "asm/pixels.asm"
INCLUDE "asm/scroll.asm"
INCLUDE "asm/view.asm"

\ The pieces' graphics (data then mask, 128 bytes each) and the backdrops'
\ (64 each), which host_compose composes into slots.
ALIGN &100
.piece_library
    PIECE_LIBRARY
ALIGN &100
.backdrop_library
    BACKDROP_LIBRARY

.host_main_end

SAVE "MAIN", host_main_start, host_main_end
