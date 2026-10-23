\ The pack screen, on the parasite (tools/stratagem/pack.py, which this does
\ exactly). PACK opens the pack and pauses the game: each frame's packet is
\ then the pack's, the kinds shown with their counts and the hand, which the
\ arrow keys move across them. PACK again closes it, and the next frame, the
\ game's, has no input and redraws the view whole.

\ Before the game's frame: return with carry set if the frame was the pack's
\ (its packet sent), carry clear for the game's, TAB having cycled the hand
\ if pressed.
.pack_input
{
    LDA #0
    STA pack_draw
    STA pack_moved
    STA pack_closed
    LDA pack_held               \ Keys pressed since last frame
    EOR #&FF
    AND zp_input
    STA pack_pressed
    LDA zp_input
    STA pack_held
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
    JSR pack_shown              \ The kinds shown, while it is open
    JMP sent
.game
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
    LDA #0                      \ Closed: the game's frame, with no input
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
    CPX pack_index
    BEQ sent
    STX pack_index
    LDA pack_kinds,X
    STA hand
    LDA #&FF
    STA pack_moved
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

\ Set pack_kinds to the kinds shown (those held, and the hand), pack_count
\ to how many, and pack_index to the hand's place among them: on opening,
\ for as long as the pack is open.
.pack_shown
{
    LDY #0
    LDX #0
.loop
    LDA inventory,X
    BNE show
    CPX hand
    BNE next
.show
    CPX hand
    BNE not_hand
    STY pack_index
.not_hand
    TXA
    STA pack_kinds,Y
    INY
.next
    INX
    CPX #KIND_COUNT
    BNE loop
    STY pack_count
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
    JMP para_send
}
