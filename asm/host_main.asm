\ MAIN, for the Tube game: the host's side of each frame, in program RAM.
\ The parasite runs the game and sends a packet a frame (tube_layout.asm);
\ the host reads it, writes the input it reads into the parasite's mailbox,
\ and draws as the host-only game does: a new row into the hidden row, then
\ at vertical sync the flip, the new columns ahead of the beam, the changed
\ tile, the light's draw list (read from the Tube as it draws), and the
\ sprite.

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

\ The host's start: a clear, narrowed screen.
.host_init
{
    LDA #0
    STA zp_sprite_drawn
    STA zp_columns_width
    STA redraw_tile
    STA host_frames
    STA host_expect_buffer
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
    READ_BYTE                   \ A changed tile, to redraw at the flip
    BEQ changes_done
    READ_BYTE
    STA host_tile_x
    STA redraw_tile_x
    READ_BYTE
    STA host_tile_y
    STA redraw_tile_y
    JSR host_read_tile
    LDA #&FF
    STA redraw_tile
.changes_done
    JSR host_release

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
    LDA #19                     \ Wait for vertical sync
    JSR OSBYTE
    \ After vertical sync, staying ahead of the beam: the new start address;
    \ the new columns' rows above the sprite, which the beam reaches first;
    \ the changed tile and the light's list, with the sprite off; the
    \ sprite; then the rest of the new columns.
    JSR set_crtc_start
    JSR sprite_split_row
    LDA #0
    LDX zp_split_row
    JSR draw_column_rows
    JSR restore_sprite
    JSR redraw_queued_tile
    JSR host_light
    JSR draw_sprite
    LDA #VIEW_ROWS
    SEC
    SBC zp_split_row
    TAX
    LDA zp_split_row
    JSR draw_column_rows
    LDA #0
    STA zp_columns_width
    INC host_frame_count
.*host_frame_shown              \ Tests stop here
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

.host_main_end

SAVE "MAIN", host_main_start, host_main_end
