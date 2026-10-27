\ M5PLAY: an experiment in driving the Music 5000 directly, without AMPLE
\ (asm/music5000.asm): it plays a score from the OS's vertical sync event,
\ one tick a frame. M5SCALE plays one voice of long notes, for measuring
\ pitch. M5LOAD plays the overture while it loads a file again and again, to
\ see how the filing system delays the ticks. The board is write-only, so the tests compare the player's own
\ variables with the model's.

INCLUDE "asm/os.asm"

BOOT_READY = &FF                \ As asm/machine.asm

EVNTV = &0220
EVENT_VSYNC = 4

ORG &70
.zp_boot_status     SKIP 1      \ Zero while starting, BOOT_READY when playing
.zp_ptr             SKIP 2
.zp_score           SKIP 2
.zp_loading         SKIP 1      \ Non-zero: load files while it plays

ORG &1900
GUARD &7C00                     \ MODE 7's screen

.m5play
INCLUDE "asm/music5000.asm"

.m5load_start
    LDX #1
    BNE tune                    \ (always)
.m5play_start
    LDX #0
.tune
    LDA #LO(score_overture)
    LDY #HI(score_overture)
    BNE start                   \ (always)
.m5scale_start
    LDX #0
    LDA #LO(score_scale)
    LDY #HI(score_scale)
.start
{
    STX zp_loading
    STA zp_score
    STY zp_score + 1
    LDA #0
    STA zp_boot_status

    JSR music_init

    SEI                         \ The vertical sync event
    LDA EVNTV
    STA old_evntv
    LDA EVNTV + 1
    STA old_evntv + 1
    LDA #LO(event)
    STA EVNTV
    LDA #HI(event)
    STA EVNTV + 1
    CLI
    LDA #14
    LDX #EVENT_VSYNC
    JSR OSBYTE

    LDA #BOOT_READY
    STA zp_boot_status
.*idle
    LDA zp_loading
    BEQ idle
    LDX #LO(load_command)       \ The filing system at work, for M5LOAD
    LDY #HI(load_command)
    JSR OSCLI
.*loaded
    JMP idle
}

LOAD_ADDRESS = &4C00             \ RENDER's 11.6K, below MODE 7's screen
.load_command   EQUS "LOAD RENDER 4C00", 13

.event
{
    CMP #EVENT_VSYNC
    BNE not_ours
    PHA
    TXA
    PHA
    TYA
    PHA
    LDA JIM_COPY                \ The page as it was
    PHA
    JSR music_tick
    PLA
    STA JIM_COPY
    STA JIM_PAGE
    PLA
    TAY
    PLA
    TAX
    PLA
.not_ours
    JMP (old_evntv)
}

.old_evntv          SKIP 2
ASSERT LO(old_evntv) <> &FF     \ JMP (indirect) on the NMOS 6502

INCLUDE "build/generated/m5_overture.asm"
INCLUDE "build/generated/m5_scale.asm"

.m5play_end
ASSERT m5play_end <= LOAD_ADDRESS

SAVE "M5PLAY", m5play, m5play_end, m5play_start
SAVE "M5SCALE", m5play, m5play_end, m5scale_start
SAVE "M5LOAD", m5play, m5play_end, m5load_start
