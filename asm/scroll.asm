\ The hardware scroll: where the view's top left cell is on the screen.

\ Move zp_screen_start by the planned movement: plan_dx cells and plan_dy
\ rows, wrapped.
.move_screen_start
{
    LDA #0
    STA zp_temp + 1
    LDA zp_plan_dx
    BPL dx_positive
    DEC zp_temp + 1             \ Sign extend
.dx_positive
    LDA zp_plan_dy              \ +1 or -1 rows: +2 or -2 pages
    ASL A
    CLC
    ADC zp_temp + 1
    STA zp_temp + 1             \ High byte of the offset
    LDA zp_plan_dx
    ASL A
    ASL A
    ASL A
    CLC
    ADC zp_screen_start
    STA zp_screen_start
    LDA zp_screen_start + 1
    ADC zp_temp + 1
    JSR wrap_both_ways
    STA zp_screen_start + 1
    RTS
}

\ Wrap a screen address high byte in A, after a signed addition, back into
\ the screen.
.wrap_both_ways
{
    CMP #HI(SCREEN_START)
    BCC below
    CMP #HI(SCREEN_END)
    BCC done
    SBC #HI(SCREEN_END - SCREEN_START)
    RTS
.below
    ADC #HI(SCREEN_END - SCREEN_START)
.done
    RTS
}
