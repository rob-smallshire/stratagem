\ LOADSCR: show the loading screen, the cover art in MODE 1 with the flash
\ bit toggled every line, and nothing else (tools/stratagem/loading_screen.py).
\
\ Two of the four logical colours are flashing physical colours, so the
\ Video ULA's flash bit swaps each for its complement: cyan and red, yellow
\ and blue. Even lines are drawn with the flash bit clear, odd lines with it
\ set, so lines alternate KWCY and KWRB.
\
\ The User VIA's timer 1 interrupts every 64us, a line, in the horizontal
\ blanking; the handler sets the flash bit for the line to come. Which line
\ that is comes from timer 2, left counting down at 1MHz from the start:
\ bit 6 of its count changes every 64us, and as a frame is an even number
\ of lines (312, with interlace off) and the count wraps every 65536us, a
\ multiple of 128, bit 6 gives the line's parity in every frame. A late
\ interrupt so costs only the line it was late for. Both timers are started
\ once, just after a vertical sync.
\
\ The System VIA's interrupts are switched off, so that nothing delays the
\ handler: the program sets zp_boot_status to BOOT_READY and idles.

INCLUDE "asm/os.asm"

IRQ1V = &0204                   \ The OS's first interrupt vector
IRQ_A = &FC                     \ Where the OS keeps A when it takes an interrupt

ULA_CONTROL = &FE20
ULA_PALETTE = &FE21

SYSTEM_VIA_IFR = &FE4D
SYSTEM_VIA_IER = &FE4E
VIA_CA1 = &02                   \ The System VIA's CA1 is the vertical sync

USER_VIA_T1C_L = &FE64
USER_VIA_T1C_H = &FE65
USER_VIA_T1L_L = &FE66
USER_VIA_T1L_H = &FE67
USER_VIA_T2C_L = &FE68
USER_VIA_T2C_H = &FE69
USER_VIA_ACR = &FE6B
USER_VIA_IFR = &FE6D
USER_VIA_IER = &FE6E
ACR_T1_CONTINUOUS = &40         \ Timer 1 free-running, timer 2 one-shot
IER_T1 = &C0                    \ Enable timer 1's interrupt

LINE_MICROSECONDS = 64
\ Microseconds from the vertical sync being seen to timer 1's first
\ interrupt: it lands the write to the control register in the
\ horizontal blanking, about 52us into a line.
FIRST_LINE_DELAY = 75

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

    SEI
    LDA #&7F                    \ Only our interrupt, from here on
    STA SYSTEM_VIA_IER
    STA USER_VIA_IER
    LDA IRQ1V
    STA old_irq1v
    LDA IRQ1V + 1
    STA old_irq1v + 1
    LDA #LO(irq_handler)
    STA IRQ1V
    LDA #HI(irq_handler)
    STA IRQ1V + 1
    LDA #ACR_T1_CONTINUOUS
    STA USER_VIA_ACR

    \ Wait for a vertical sync, then start both timers.
    LDA #VIA_CA1
    STA SYSTEM_VIA_IFR
.wait_for_sync
    BIT SYSTEM_VIA_IFR
    BEQ wait_for_sync
    LDA #LO(FIRST_LINE_DELAY)
    STA USER_VIA_T1C_L
    LDA #HI(FIRST_LINE_DELAY)
    STA USER_VIA_T1C_H          \ Starts timer 1
    LDA #&FF
    STA USER_VIA_T2C_L
    STA USER_VIA_T2C_H          \ Starts timer 2
    LDA #LO(LINE_MICROSECONDS - 2)
    STA USER_VIA_T1L_L
    LDA #HI(LINE_MICROSECONDS - 2)
    STA USER_VIA_T1L_H          \ Then a line between interrupts
    LDA #IER_T1
    STA USER_VIA_IER

    LDX #15
.palette_loop
    LDA loading_palette,X
    STA ULA_PALETTE
    DEX
    BPL palette_loop
    CLI

    LDA #BOOT_READY
    STA zp_boot_status
.*idle
    JMP idle
}

\ Timer 1, every line: the flash bit for the line to come is bit 6 of timer
\ 2's count. Only timer 1 can interrupt from the User VIA.
.irq_handler
{
    LDA USER_VIA_IFR
    BPL not_ours
    LDA USER_VIA_T2C_L
    ASL A
    ASL A                       \ Bit 6 into carry
    LDA #LOADING_CONTROL
    ADC #0
    STA ULA_CONTROL
.*control_written
    LDA USER_VIA_T1C_L          \ Clears the interrupt
    LDA IRQ_A
    RTI
.not_ours
    JMP (old_irq1v)
}

.old_irq1v      SKIP 2

.vdu_setup
    EQUB 22, 1                  \ MODE 1
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
.vdu_setup_end

.load_command   EQUS "LOAD LSCREEN 3000", 13

INCLUDE "build/generated/loading_screen.asm"

.loadscr_end

SAVE "LOADSCR", loadscr_start, loadscr_end
PUTFILE "build/generated/loading_screen.bin", "LSCREEN", &3000
