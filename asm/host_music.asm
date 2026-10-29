\ MUSIC: the title's music on the Music 5000, the Stratagem Overture
\ (asm/music5000.asm, tools/stratagem/overture.py), and the loading page.
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

\ The loading page: the keys, and a bar, a step a file.
.show_loading
    LDX #LO(loading_page)
    LDY #HI(loading_page)
    JMP page_string

.show_progress
    LDX #LO(progress_step)
    LDY #HI(progress_step)
    JMP page_string

.show_loaded
    LDX #LO(loaded_line)
    LDY #HI(loaded_line)
\ Write the bytes at YX, up to PAGE_END, to the VDU drivers.
.page_string
{
    STX zp_ptr
    STY zp_ptr + 1
    LDY #0
.loop
    LDA (zp_ptr),Y
    CMP #PAGE_END
    BEQ done
    JSR OSWRCH
    INY
    BNE loop
    INC zp_ptr + 1
    BNE loop
.done
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

TELETEXT_GREEN = &82
TELETEXT_YELLOW = &83
TELETEXT_MAGENTA = &85
TELETEXT_CYAN = &86
TELETEXT_WHITE = &87
TELETEXT_DOUBLE = &8D
TELETEXT_GRAPHICS_GREEN = &92
TELETEXT_BLOCK = &FF
KEYS_TOP = 5
BAR_ROW = 20
BAR_COLUMN = 11
PROGRESS_STEPS = 5              \ RENDER, PWORLD, PLIGHT, PGAME, MAIN
PROGRESS_BLOCKS = 5             \ A step's
PAGE_END = &FE                  \ Ends a string: no character or VDU argument here

\ A line of the keys: the key in white, what it does in cyan.
MACRO KEY_LINE row, key, text
    EQUB 31, 1, row, TELETEXT_WHITE
    EQUS key
    EQUB 31, 9, row, TELETEXT_CYAN
    EQUS text
ENDMACRO

.loading_page
    EQUB 22, 128 + 7            \ Shadow MODE 7
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
    FOR row, 1, 2
        EQUB 31, 13, row, TELETEXT_DOUBLE, TELETEXT_YELLOW
        EQUS "STRATAGEM"
    NEXT
    KEY_LINE KEYS_TOP, "Z X", "left, right"
    KEY_LINE KEYS_TOP + 1, "K", "jump"
    KEY_LINE KEYS_TOP + 2, "L", "dig; with K or M, up or down;"
    EQUB 31, 9, KEYS_TOP + 3, TELETEXT_CYAN
    EQUS "with Z or X too, a slope"
    KEY_LINE KEYS_TOP + 4, "SPACE", "place what's in your hand"
    KEY_LINE KEYS_TOP + 5, "TAB", "the next thing in your hand"
    KEY_LINE KEYS_TOP + 6, "1-9", "a tool from your belt"
    KEY_LINE KEYS_TOP + 7, "0", "show the tool in your hand"
    KEY_LINE KEYS_TOP + 8, "P", "open your pack"
    EQUB 31, 1, BAR_ROW + 2, TELETEXT_MAGENTA
    EQUS "Music: The Stratagem Overture"
    EQUB 31, 1, BAR_ROW, TELETEXT_GREEN
    EQUS "Loading"
    EQUB 31, BAR_COLUMN - 1, BAR_ROW, TELETEXT_GRAPHICS_GREEN, PAGE_END
.progress_step
    FOR block, 1, PROGRESS_BLOCKS
        EQUB TELETEXT_BLOCK
    NEXT
    EQUB PAGE_END
.loaded_line
    EQUB 31, 1, BAR_ROW, TELETEXT_WHITE
    EQUS "Press SPACE to start"
    FOR column, 22, 39
        EQUB ' '
    NEXT
    EQUB PAGE_END
ASSERT BAR_COLUMN + PROGRESS_STEPS * PROGRESS_BLOCKS <= 40

.music_end
SAVE "MUSIC", music_start, music_end
