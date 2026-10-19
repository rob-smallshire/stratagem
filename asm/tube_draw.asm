\ Tube prototype 3: the host draws cells straight from the Tube, as the
\ parasite lists them (tests/test_tube_draw.py). For each cell the parasite
\ gives everything the host needs: its screen address, its graphics' address
\ and its dither masks' (low byte), so that the host only copies. The host
\ reads the list a byte at a time (transfer type 0), as it draws, so a list
\ is as long as it needs to be.
\
MACRO READ_BYTE                 \ The next byte from the parasite
.wait
    BIT TUBE_R3_STATUS
    BPL wait
    LDA TUBE_R3
ENDMACRO

\ Draw the cell at screen from tile through the masks at mask (or copy it, at
\ full light), reading the next entry's first four bytes into the other set
\ as it goes: after lines 7, 5, 3 and 1.
MACRO DRAW_PIPELINED screen, tile, mask, next_screen, next_tile, next_mask
    LDA mask
    CMP #LIGHT_FULL * LIGHT_SCALE
    BCS full
    JMP dim
.full
    LDY #7
    FOR line, 7, 0, -1
        LDA (tile),Y
        STA (screen),Y
        IF line = 7
            LDA TUBE_R3
            STA next_mask
        ELIF line = 5
            LDA TUBE_R3
            STA next_tile
        ELIF line = 3
            LDA TUBE_R3
            STA next_tile + 1
        ELIF line = 1
            LDA TUBE_R3
            STA next_screen
        ENDIF
        IF line > 0
            DEY
        ENDIF
    NEXT
    JMP done
.dim
    LDY #7
    FOR line, 7, 0, -1
        LDA (tile),Y
        AND (mask),Y
        STA (screen),Y
        IF line = 7
            LDA TUBE_R3
            STA next_mask
        ELIF line = 5
            LDA TUBE_R3
            STA next_tile
        ELIF line = 3
            LDA TUBE_R3
            STA next_tile + 1
        ELIF line = 1
            LDA TUBE_R3
            STA next_screen
        ENDIF
        IF line > 0
            DEY
        ENDIF
    NEXT
.done
ENDMACRO

\ OSWRCH commands from the parasite, each followed by its parameter bytes:
\
\   128 MARK n          host notes mark n (tests stop at draw_mark_hit)
\   129 DRAW address    host draws the list at the parasite address: a count,
\                       then per cell: masks (1), graphics (2), screen (2),
\                       and an entry's worth of padding
\
\ The host reads each cell's entry while it draws the cell before, a byte
\ every two lines or so: long enough for the parasite's NMI to put the next
\ byte in R3, so that only the first reads need wait for it.

INCLUDE "asm/os.asm"
INCLUDE "build/generated/light.asm"

WRCHV = &020E
TUBE_ENTRY = &0406
TUBE_R3_STATUS = &FEE4          \ Host side: bit 7 set when R3 holds a byte
TUBE_R3 = &FEE5
TUBE_TYPE_BYTES_TO_HOST = 0     \ Single bytes, parasite to host
TUBE_CLAIM_ID = &0E
TUBE_CLAIM = &C0 + TUBE_CLAIM_ID
TUBE_RELEASE = &80 + TUBE_CLAIM_ID
HOST_ADDRESS = &30000           \ A DFS load address of &FFFFxxxx: the host

COMMAND_MARK = 128
COMMAND_DRAW = 129
CELL_ENTRY_BYTES = 5
LIST_CELLS = 64
DRAW_SCREEN = &3000             \ Where the lists draw: clear of the MODE 7 screen

\ Host

ORG &70
.draw_handler       SKIP 2      \ Takes the next byte of a command, if any
.draw_index         SKIP 1
.draw_a             SKIP 1
.draw_x             SKIP 1
.draw_y             SKIP 1
.draw_mark_id       SKIP 1
.draw_count         SKIP 1
.draw_screen        SKIP 2      \ The cell being drawn: set A
.draw_tile          SKIP 2
.draw_mask          SKIP 2
.draw_screen_b      SKIP 2      \ And set B
.draw_tile_b        SKIP 2
.draw_mask_b        SKIP 2

CLEAR &2000, &3000
ORG &2000
.draw_begin

.draw_install
{
    SEI
    LDA WRCHV
    STA draw_old_wrchv
    LDA WRCHV + 1
    STA draw_old_wrchv + 1
    LDA #LO(draw_wrch)
    STA WRCHV
    LDA #HI(draw_wrch)
    STA WRCHV + 1
    CLI
    LDA #0
    STA draw_handler + 1
    LDA #HI(draw_masks)
    STA draw_mask + 1
    STA draw_mask_b + 1
    RTS
}

.draw_old_wrchv     EQUW 0
.draw_address       EQUD 0      \ The list's parasite address

.draw_wrch
{
    STA draw_a
    STX draw_x
    STY draw_y
    LDX draw_handler + 1
    BEQ command
    JMP (draw_handler)
.command
    CMP #COMMAND_MARK
    BEQ mark
    CMP #COMMAND_DRAW
    BEQ draw
    JMP (draw_old_wrchv)
.mark
    LDA #LO(draw_mark)
    LDX #HI(draw_mark)
    BNE handler
.draw
    LDA #LO(draw_list)
    LDX #HI(draw_list)
.handler
    STA draw_handler
    STX draw_handler + 1
    LDA #0
    STA draw_index
    JMP draw_return
}

.draw_mark
    STA draw_mark_id
.draw_mark_hit
    JMP draw_done

\ Collect the list's address (two bytes), then draw it.
.draw_list
{
    LDX draw_index
    STA draw_address,X
    INX
    STX draw_index
    CPX #2
    BEQ claim
    JMP draw_return
.claim
    LDA #TUBE_CLAIM
    JSR TUBE_ENTRY
    BCC claim
    LDA #TUBE_TYPE_BYTES_TO_HOST
    LDX #LO(draw_address)
    LDY #HI(draw_address)
    JSR TUBE_ENTRY
    READ_BYTE
    STA draw_count
    READ_BYTE                   \ The first cell's entry
    STA draw_mask
    READ_BYTE
    STA draw_tile
    READ_BYTE
    STA draw_tile + 1
    READ_BYTE
    STA draw_screen
    READ_BYTE
    STA draw_screen + 1
.cell_a
    DRAW_PIPELINED draw_screen, draw_tile, draw_mask, draw_screen_b, draw_tile_b, draw_mask_b
    DEC draw_count
    BNE more_a
    JMP done
.more_a
    READ_BYTE
    STA draw_screen_b + 1
    DRAW_PIPELINED draw_screen_b, draw_tile_b, draw_mask_b, draw_screen, draw_tile, draw_mask
    DEC draw_count
    BNE more_b
    JMP done
.more_b
    READ_BYTE
    STA draw_screen + 1
    JMP cell_a
.done
    LDA #TUBE_RELEASE
    JSR TUBE_ENTRY
    JMP draw_done
}

.draw_done
    LDA #0
    STA draw_handler + 1
.draw_return
    LDA draw_a
    LDX draw_x
    LDY draw_y
    RTS

ALIGN &100
.draw_masks
    LIGHT_MASKS
.draw_graphics                  \ Stand-in cell graphics: 32 cells
FOR n, 0, 255
    EQUB (n * 37 + 11) AND &FF
NEXT
.draw_end

SAVE "TDRAWH", draw_begin, draw_end, draw_install + HOST_ADDRESS, draw_begin + HOST_ADDRESS

\ Parasite (a separate address space)

CLEAR &1000, &2000
ORG &1000
.dp_begin

.dp_start
{
    LDA #1
    JSR dp_mark
    LDX #LO(dp_list_one)
    LDY #HI(dp_list_one)
    JSR dp_draw
    LDA #2
    JSR dp_mark
    LDX #LO(dp_list_dim)
    LDY #HI(dp_list_dim)
    JSR dp_draw
    LDA #3
    JSR dp_mark
    LDX #LO(dp_list_full)
    LDY #HI(dp_list_full)
    JSR dp_draw
    LDA #4
    JSR dp_mark
    LDA #5                      \ Back to back: the cost of a mark itself
    JSR dp_mark
    LDA #&FF
    STA dp_done
    RTS
}

.dp_done            EQUB 0

.dp_mark
    PHA
    LDA #COMMAND_MARK
    JSR OSWRCH
    PLA
    JMP OSWRCH

\ Draw the list at YX.
.dp_draw
    LDA #COMMAND_DRAW
    JSR OSWRCH
    TXA
    JSR OSWRCH
    TYA
    JMP OSWRCH

\ A list of one cell, then LIST_CELLS cells at dim levels (0-14), then
\ LIST_CELLS at full light, each with an entry's padding after (read ahead): cell n at DRAW_SCREEN + 8n, its graphics the
\ n-th of draw_graphics' 32 cells, its parity that of n.
.dp_list_one
    EQUB 1
    EQUB 7 * LIGHT_SCALE
    EQUW draw_graphics, DRAW_SCREEN + 8 * 3 * LIST_CELLS
    SKIP CELL_ENTRY_BYTES
.dp_list_dim
    EQUB LIST_CELLS
FOR n, 0, LIST_CELLS - 1
    EQUB (n MOD 15) * LIGHT_SCALE + 8 * (n AND 1)
    EQUW draw_graphics + 8 * (n AND 31), DRAW_SCREEN + 8 * n
NEXT
    SKIP CELL_ENTRY_BYTES
.dp_list_full
    EQUB LIST_CELLS
FOR n, 0, LIST_CELLS - 1
    EQUB LIGHT_FULL * LIGHT_SCALE + 8 * (n AND 1)
    EQUW draw_graphics + 8 * (n AND 31), DRAW_SCREEN + 8 * (LIST_CELLS + n)
NEXT
    SKIP CELL_ENTRY_BYTES
.dp_end

SAVE "TDRAWP", dp_begin, dp_end, dp_start, dp_begin
