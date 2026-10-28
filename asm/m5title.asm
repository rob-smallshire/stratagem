\ M5TITLE: the title screen (as LOADSCR) with music on the Music 5000
\ (asm/music5000.asm). While the title shows, the System VIA's interrupts
\ are off, so there is no vertical sync event; but its flag for the vertical
\ sync is still set each frame, and the main loop watches it and ticks the
\ music, while the line interrupt switches the flash bit as before.

INCLUDE "asm/os.asm"

BOOT_READY = &FF                \ As asm/machine.asm

ORG &70
.zp_boot_status     SKIP 1      \ Zero while starting, BOOT_READY when showing
.zp_ptr             SKIP 2
.zp_score           SKIP 2

ORG &1900
GUARD &3000

.m5title
INCLUDE "asm/loading_screen.asm"
INCLUDE "asm/music5000.asm"

.m5title_start
{
    LDA #0
    STA zp_boot_status

    \ Interlace off, so that every frame is 312 lines, then MODE 1 with the
    \ cursor off.
    LDA #144
    LDX #0
    LDY #1
    JSR OSBYTE
    LDX #0
.vdu_loop
    LDA vdu_setup,X
    JSR OSWRCH
    INX
    CPX #vdu_setup_end - vdu_setup
    BNE vdu_loop

    \ All black while the screen loads.
    LDX #15
.black_loop
    TXA
    ASL A
    ASL A
    ASL A
    ASL A
    ORA #7                      \ Physical colour 0, as the ULA wants it
    STA ULA_PALETTE
    DEX
    BPL black_loop

    LDX #LO(load_command)
    LDY #HI(load_command)
    JSR OSCLI

    LDA #LO(score_scale)
    STA zp_score
    LDA #HI(score_scale)
    STA zp_score + 1
    JSR music_init
    JSR loading_screen_on
    LDA #BOOT_READY
    STA zp_boot_status

.*title_loop
    LDA #VIA_CA1                \ A vertical sync since the last tick?
    BIT SYSTEM_VIA_IFR
    BEQ title_loop
    STA SYSTEM_VIA_IFR          \ (clears it)
    JSR music_tick
    JMP title_loop
}

.vdu_setup
    EQUB 22, 1                  \ MODE 1
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
.vdu_setup_end

.load_command   EQUS "LOAD LSCREEN 3000", 13

INCLUDE "build/generated/m5_scale.asm"

.m5title_end

SAVE "M5TITLE", m5title, m5title_end, m5title_start
