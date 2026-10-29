\ MUSIC: the title's music on the Music 5000, the Stratagem Overture
\ (asm/music5000.asm, tools/stratagem/overture.py), and the loading page
\ (asm/loading_page.asm).
\ STRAT loads it into user RAM once the title's picture is on the (shadow)
\ screen, plays it while the title shows, then shows the loading page and
\ plays on, from the vertical sync event (music_event, in STRAT), while
\ the game loads and until SPACE is pressed. Then it silences the board,
\ and MAIN, loaded at GAME_BUFFER, is copied over it. On a machine without
\ the board its writes go nowhere.

CLEAR USER_START, USER_END
ORG USER_START
GUARD GAME_BUFFER
.music_start
INCLUDE "asm/music5000.asm"
INCLUDE "build/generated/m5_overture.asm"

\ Tick the music from the vertical sync event (music_event), or stop.
.music_event_on
{
    SEI
    LDA EVNTV
    STA music_old_evntv
    LDA EVNTV + 1
    STA music_old_evntv + 1
    LDA #LO(music_event)
    STA EVNTV
    LDA #HI(music_event)
    STA EVNTV + 1
    CLI
    LDA #14                     \ Enable the event
    LDX #EVENT_VSYNC
    JMP OSBYTE
}

.music_event_off
{
    LDA #13                     \ Disable the event
    LDX #EVENT_VSYNC
    JSR OSBYTE
    SEI
    LDA music_old_evntv
    STA EVNTV
    LDA music_old_evntv + 1
    STA EVNTV + 1
    CLI
    RTS
}

\ Wait for SPACE to be up, then down, through the OS (INKEY -99).
.wait_to_start
{
.up
    JSR space_down
    BEQ up
.down
    JSR space_down
    BNE down
    LDA #15                     \ Forget the keys pressed meanwhile
    LDX #0
    JMP OSBYTE
.space_down                     \ Z set if SPACE is down
    LDA #&81
    LDX #&FF - 98               \ INKEY -99: SPACE
    LDY #&FF
    JSR OSBYTE
    INX
    RTS
}

INCLUDE "asm/loading_page.asm"

.music_end
ASSERT music_end <= music_start + MUSIC_PAGES * 256
SAVE "MUSIC", music_start, music_end
