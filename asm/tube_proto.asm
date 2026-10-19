\ Tube prototype 1: the ways the parasite and the host can exchange data, so
\ that each can be timed (tests/test_tube_proto.py). TUBEH is loaded into
\ the host, where it extends OSWRCH and OSWORD, as Second Processor Elite
\ does; TUBEP is run in the parasite, and drives each kind of exchange
\ between numbered marks.
\
\ OSWRCH commands from the parasite, each followed by its parameter bytes:
\
\   128 MARK n          host notes mark n (tests stop at host_mark_hit)
\   129 STREAM n bytes  host stores n bytes (0 means 256)
\   130 PULL address    host reads 256 bytes from the parasite (type 6)
\   131 PUSH address    host writes 256 bytes to the parasite (type 7)
\
\ OSWORDs (block byte 0: bytes sent, byte 1: bytes returned):
\
\   240 ECHO            host returns bytes 2-127 inverted
\   241 NULL            host does nothing: a bare round trip

INCLUDE "asm/os.asm"

WORDV = &020C
WRCHV = &020E
TUBE_ENTRY = &0406              \ Claim, release, or start a transfer
TUBE_R3 = &FEE5                 \ Host side: the data register for transfers
TUBE_TYPE_TO_HOST = 6           \ 256 bytes, parasite to host
TUBE_TYPE_TO_PARASITE = 7       \ 256 bytes, host to parasite
TUBE_CLAIM_ID = &0E
TUBE_CLAIM = &C0 + TUBE_CLAIM_ID
TUBE_RELEASE = &80 + TUBE_CLAIM_ID
HOST_ADDRESS = &30000           \ A DFS load address of &FFFFxxxx: the host

COMMAND_MARK = 128
COMMAND_STREAM = 129
COMMAND_PULL = 130
COMMAND_PUSH = 131
OSWORD_ECHO = 240
OSWORD_NULL = 241
ECHO_BYTES = 128

\ Host

ORG &70
.host_handler       SKIP 2      \ Takes the next byte of a command, if any
.host_count         SKIP 1
.host_index         SKIP 1
.host_ptr           SKIP 2
.host_a             SKIP 1
.host_x             SKIP 1
.host_y             SKIP 1
.host_mark_id       SKIP 1

CLEAR &2000, &3000
ORG &2000
.host_begin

\ Run once, by *RUN: hook OSWRCH and OSWORD.
.host_install
{
    SEI
    LDA WRCHV
    STA host_old_wrchv
    LDA WRCHV + 1
    STA host_old_wrchv + 1
    LDA #LO(host_wrch)
    STA WRCHV
    LDA #HI(host_wrch)
    STA WRCHV + 1
    LDA WORDV
    STA host_old_wordv
    LDA WORDV + 1
    STA host_old_wordv + 1
    LDA #LO(host_word)
    STA WORDV
    LDA #HI(host_word)
    STA WORDV + 1
    CLI
    LDA #0
    STA host_handler + 1
    LDX #0
.fill
    TXA
    EOR #&A5
    STA host_push_data,X
    INX
    BNE fill
    RTS
}

.host_old_wrchv     EQUW 0
.host_old_wordv     EQUW 0
.host_address       EQUD 0      \ A parasite address, for PULL and PUSH

\ OSWRCH: a command's next byte, a new command, or an ordinary character.
.host_wrch
{
    STA host_a
    STX host_x
    STY host_y
    LDX host_handler + 1
    BEQ command
    JMP (host_handler)
.command
    CMP #COMMAND_MARK
    BCC ordinary
    CMP #COMMAND_PUSH + 1
    BCS ordinary
    SBC #COMMAND_MARK - 1       \ Carry clear: subtracts COMMAND_MARK
    ASL A
    TAX
    LDA host_commands,X
    STA host_handler
    LDA host_commands + 1,X
    STA host_handler + 1
    LDA #0
    STA host_index
    JMP host_return
.ordinary
    JMP (host_old_wrchv)
}

.host_commands
    EQUW host_mark, host_stream, host_pull, host_push

.host_mark
    STA host_mark_id
.host_mark_hit
    JMP host_done

.host_stream
{
    STA host_count
    LDA #LO(host_stream_byte)
    STA host_handler
    JMP host_return
}

.host_stream_byte
{
    LDX host_index
    STA host_stream_buffer,X
    INC host_index
    DEC host_count
    BEQ host_done
    JMP host_return
}

\ Collect the 4 address bytes; carry set when all have come.
.host_address_byte
{
    LDX host_index
    STA host_address,X
    INX
    STX host_index
    CPX #4
    RTS
}

.host_pull
{
    JSR host_address_byte
    BCC host_return
    JSR host_claim
    PHP
    SEI
    LDA #TUBE_TYPE_TO_HOST
    LDX #LO(host_address)
    LDY #HI(host_address)
    JSR TUBE_ENTRY
    JSR host_delay
    LDY #0
.loop
    NOP
    NOP
    NOP
    LDA TUBE_R3
    STA host_pulled,Y
    INY
    BNE loop
    PLP
    JSR host_release
    JMP host_done
}

.host_push
{
    JSR host_address_byte
    BCC host_return
    JSR host_claim
    PHP
    SEI
    LDA #TUBE_TYPE_TO_PARASITE
    LDX #LO(host_address)
    LDY #HI(host_address)
    JSR TUBE_ENTRY
    JSR host_delay
    LDY #0
.loop
    NOP
    NOP
    NOP
    LDA host_push_data,Y
    STA TUBE_R3
    INY
    BNE loop
    PLP
    JSR host_release
    JMP host_done
}

.host_done
    LDA #0
    STA host_handler + 1
.host_return
    LDA host_a
    LDX host_x
    LDY host_y
    RTS

.host_claim
{
    LDA #TUBE_CLAIM
    JSR TUBE_ENTRY
    BCC host_claim
    RTS
}

.host_release
    LDA #TUBE_RELEASE
    JMP TUBE_ENTRY

\ Time for the parasite to start its side of a transfer (as ADFS waits).
.host_delay
    JSR host_delay_inner
.host_delay_inner
    JSR host_delay_return
.host_delay_return
    RTS

\ OSWORD: ECHO and NULL, or an ordinary call.
.host_word
{
    CMP #OSWORD_ECHO
    BEQ echo
    CMP #OSWORD_NULL
    BEQ null
    JMP (host_old_wordv)
.echo
    STX host_ptr
    STY host_ptr + 1
    LDY #2
.loop
    LDA (host_ptr),Y
    STA host_word_in,Y
    EOR #&FF
    STA (host_ptr),Y
    INY
    CPY #ECHO_BYTES
    BNE loop
.null
    RTS
}

ALIGN &100
.host_stream_buffer SKIP 256
.host_pulled        SKIP 256
.host_push_data     SKIP 256
.host_word_in       SKIP ECHO_BYTES
.host_end

SAVE "TUBEH", host_begin, host_end, host_install + HOST_ADDRESS, host_begin + HOST_ADDRESS

\ Parasite (a separate address space)

CLEAR &70, &80
ORG &70
.para_ptr           SKIP 2

CLEAR &1000, &2000
ORG &1000
.para_begin

.para_start
{
    LDX #0                      \ The page the host pulls: 3 + 7i
    LDA #3
.fill
    STA para_pull_source,X
    CLC
    ADC #7
    INX
    BNE fill
    LDA #0
.clear
    STA para_push_target,X
    INX
    BNE clear
    LDX #ECHO_BYTES - 1         \ The ECHO block: i
.block
    TXA
    STA para_echo_block,X
    DEX
    BPL block
    LDA #ECHO_BYTES
    STA para_echo_block
    STA para_echo_block + 1
    LDA #2
    STA para_null_block
    STA para_null_block + 1

    LDA #1
    JSR para_mark
    LDA #COMMAND_STREAM
    JSR OSWRCH
    LDA #0
    JSR OSWRCH
    LDX #0
.stream
    TXA
    JSR OSWRCH
    INX
    BNE stream
    LDA #2
    JSR para_mark

    LDA #COMMAND_PULL
    LDX #LO(para_pull_source)
    LDY #HI(para_pull_source)
    JSR para_command
    LDA #3
    JSR para_mark

    LDA #COMMAND_PUSH
    LDX #LO(para_push_target)
    LDY #HI(para_push_target)
    JSR para_command
    LDA #4
    JSR para_mark

    LDA #5
    JSR para_mark
    LDA #OSWORD_ECHO
    LDX #LO(para_echo_block)
    LDY #HI(para_echo_block)
    JSR OSWORD
    LDA #6
    JSR para_mark

    LDA #7
    JSR para_mark
    LDA #64
    STA para_count
.null
    LDA #OSWORD_NULL
    LDX #LO(para_null_block)
    LDY #HI(para_null_block)
    JSR OSWORD
    DEC para_count
    BNE null
    LDA #8
    JSR para_mark

    LDA #9                      \ Back to back: the cost of a mark itself
    JSR para_mark
    LDA #10
    JSR para_mark
    LDA #&FF
    STA para_done
    RTS
}

.para_count         EQUB 0
.para_done          EQUB 0

\ Send mark A.
.para_mark
    PHA
    LDA #COMMAND_MARK
    JSR OSWRCH
    PLA
    JMP OSWRCH

\ Send command A with the parasite address YX.
.para_command
    JSR OSWRCH
    TXA
    JSR OSWRCH
    TYA
    JSR OSWRCH
    LDA #0
    JSR OSWRCH
    JMP OSWRCH

ALIGN &100
.para_pull_source   SKIP 256
.para_push_target   SKIP 256
.para_echo_block    SKIP ECHO_BYTES
.para_null_block    SKIP 2
.para_end

SAVE "TUBEP", para_begin, para_end, para_start, para_begin
