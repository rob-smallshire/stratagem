\ LOADSCR: show the loading screen and nothing else (asm/loading_screen.asm),
\ so that it can be looked at and tested apart from the game's loader.

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"

BOOT_READY = &FF                \ As asm/zeropage.asm

ORG &70
.zp_boot_status     SKIP 1      \ Zero while starting, BOOT_READY when showing

ORG &2000
GUARD &3000

.loadscr_start
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

    JSR loading_screen_on
    LDA #BOOT_READY
    STA zp_boot_status
.*idle
    JMP idle
}

INCLUDE "asm/loading_screen.asm"

.vdu_setup
    EQUB 22, 1                  \ MODE 1
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
.vdu_setup_end

.load_command   EQUS "LOAD LSCREEN 3000", 13

.loadscr_end

SAVE "LOADSCR", loadscr_start, loadscr_end
\ LSCREEN is put on the disc with the game's files (asm/host.asm).
