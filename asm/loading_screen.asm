\ The title screen's interrupt, shared by STRAT's loader and LOADSCR: the
\ cover art in MODE 1 with the Video ULA's flash bit toggled every line
\ (tools/stratagem/loading_screen.py).
\
\ Two of the four logical colours are flashing physical colours, so the
\ flash bit swaps each for its complement: cyan and red, yellow and blue.
\ Even lines are drawn with the flash bit clear, odd lines with it set, so
\ lines alternate KWCY and KWRB.
\
\ A write to the control register at CRTC column c takes effect from about
\ column c - 2, so it is unseen from column 82 to column 1 of the next line
\ (of 128; 80 displayed). The User VIA's timer 1 interrupts every 64us, a
\ line, some way ahead of that; the handler waits, watching timer 1, until
\ column 90 or so, then sets the flash bit for the line to come. Other
\ interrupts would delay the handler (a filing system's NMIs, while a file
\ loads beneath it: docs/loading-screen.md); it waits only if it isn't
\ late, so that an interruption already over by the time it is due costs
\ nothing, and one that runs on past it costs only the time it runs on:
\ the start of the next line, drawn in the other palette.
\
\ Which line that is comes from timer 2, left counting down at 1MHz from
\ the start: bit 6 of its count changes every 64us, and as a frame is an
\ even number of lines (312, with interlace off) and the count wraps every
\ 65536us, a multiple of 128, bit 6 gives the line's parity in every
\ frame. It changes just before the handler reads it, at about the end of
\ the line drawn, so that a handler delayed by up to most of a line still
\ sets the flash bit for the line being drawn. Both timers are started
\ once, just after a vertical sync.
\
\ The System VIA's interrupts are switched off while it runs, and nothing
\ in it depends on a particular filing system.

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
\ interrupt, and the count at which the handler stops waiting: together
\ they land the write early in the blanking (unseen from column 82), to
\ leave as much of it as can be for a delay. The handler polls timer 1
\ every 5us or so, so where the write lands depends on the instruction it
\ interrupted: with music playing in the foreground (M5TITLE) it lands at
\ column 85 to 96. The handler waits about 20us of each line, so an
\ interruption of up to that long before it is due costs nothing (a
\ longer wait would take more of the CPU from the loading).
FIRST_LINE_DELAY = 48
SWITCH_COUNT = 28               \ Wait while timer 1's count is at least this
\ Timer 2's first count: it puts the change in bit 6 about 5us before the
\ handler reads it (it reads the wrong line's parity from &12).
T2_START = &0D

\ Show the loading screen's palette and start toggling the flash bit every
\ line, with only this interrupt from the VIAs. The screen must be MODE 1
\ with interlace off.
.loading_screen_on
{
    SEI
    LDA SYSTEM_VIA_IER
    STA loading_system_ier
    LDA USER_VIA_IER
    STA loading_user_ier
    LDA USER_VIA_ACR
    STA loading_user_acr
    LDA #&7F                    \ Only our interrupt, from here on
    STA SYSTEM_VIA_IER
    STA USER_VIA_IER
    LDA IRQ1V
    STA loading_old_irq1v
    LDA IRQ1V + 1
    STA loading_old_irq1v + 1
    LDA #LO(loading_irq)
    STA IRQ1V
    LDA #HI(loading_irq)
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
    LDA #T2_START
    STA USER_VIA_T2C_L
    LDA #&FF
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
    RTS
}

\ Stop toggling the flash bit, and give the VIAs back to the OS as they
\ were.
.loading_screen_off
{
    SEI
    LDA #&7F
    STA USER_VIA_IER
    LDA loading_user_acr
    STA USER_VIA_ACR
    LDA loading_old_irq1v
    STA IRQ1V
    LDA loading_old_irq1v + 1
    STA IRQ1V + 1
    LDA loading_system_ier
    ORA #&80
    STA SYSTEM_VIA_IER
    LDA loading_user_ier
    ORA #&80
    STA USER_VIA_IER
    CLI
    RTS
}

\ Timer 1, every line: wait until timer 1's count is below SWITCH_COUNT,
\ then set the flash bit for the line to come, from bit 6 of timer 2's
\ count. Only timer 1 can interrupt from the User VIA.
.loading_irq
{
    LDA USER_VIA_IFR
    BPL not_ours
.wait
    LDA USER_VIA_T1C_L          \ (Clears the interrupt)
    CMP #SWITCH_COUNT
    BCS wait
    LDA #LOADING_CONTROL
    BIT USER_VIA_T2C_L
    BVC write
    LDA #LOADING_CONTROL + 1
.write
    STA ULA_CONTROL
.*control_written
    LDA IRQ_A
    RTI
.not_ours
    JMP (loading_old_irq1v)
}

.loading_old_irq1v  SKIP 2
ASSERT LO(loading_old_irq1v) <> &FF \ JMP (indirect) on the host's NMOS 6502
.loading_system_ier SKIP 1      \ The VIAs' interrupts and User VIA's ACR, as
.loading_user_ier   SKIP 1      \ the OS had them
.loading_user_acr   SKIP 1

INCLUDE "build/generated/loading_screen.asm"
