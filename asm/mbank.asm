\ MBANK: the game's music on the Music 5000, in a fourth sideways RAM bank,
\ when there is one (the filing system in ROM): its own copy of the player
\ (asm/music5000.asm), its pieces, and the director that chooses when to
\ play them (docs/musical-direction.md). STRAT's loader loads it into the
\ bank beneath the loading page, and once the game is set up selects the
\ bank and calls MBANK_START, which sets the board up and points STRAT's
\ vertical sync event (music_event) at this bank's tick. Assembled apart
\ from the host (its own copy of the player's labels), with the host's
\ labels from build/generated/labels_host.asm.

INCLUDE "asm/os.asm"
INCLUDE "asm/layout.asm"
INCLUDE "asm/tube_layout.asm"
INCLUDE "build/generated/labels_host.asm"

zp_ptr = HOST_zp_ptr            \ Saved by music_event
zp_score = HOST_zp_temp         \ While music_init runs, before the game

CLEAR BANK_START, BANK_END
ORG MBANK_START
GUARD BANK_END
MBANK_CODE_END = &A000          \ (The B+ shows code at &A000-&AFFF the shadow, where
                                \ MAIN is: the code reads MAIN's variables)

.mbank_entries
    JMP mbank_start             \ MBANK_START
    JMP mbank_tick              \ MBANK_TICK: a tick owed (host_music_owed)
ASSERT mbank_entries = MBANK_START

\ The pieces (docs/musical-direction.md): the musical day's, and the
\ overture, kept for celebration.
PIECE_OVERTURE = 0
PIECE_DAWN = 1
PIECE_DAYLIGHT = 2
PIECE_DUSK = 3
PIECE_NIGHT = 4
PIECE_UNDERGROUND = 5

\ The director: silence, mostly. FIRST_QUIET ticks before the first piece,
\ which plays for certain; after each, QUIET_MIN and up to 255 QUIET_UNITs
\ more; then every CONSIDER_TICKS a chance of PLAY_CHANCE in 256 of the
\ piece for the world as it is (the time, or underground: PACKET_WORLD),
\ half that if it was the last played. A piece, once started, plays to
\ its end.
TICKS_PER_SECOND = 50
FIRST_QUIET = 15 * TICKS_PER_SECOND
QUIET_MIN = 120 * TICKS_PER_SECOND
QUIET_UNIT = 32                 \ (up to 2:43 more)
CONSIDER_TICKS = 30 * TICKS_PER_SECOND
PLAY_CHANCE = 85                \ (a third)

\ Set the board up, silent, and tick the director from the vertical sync
\ event: this bank, selected, is the event's ROMSEL; its calls,
\ mbank_event and an RTS.
.mbank_start
{
    LDA #LO(score_overture)     \ (Any piece: stopped at once)
    STA zp_score
    LDA #HI(score_overture)
    STA zp_score + 1
    JSR music_init
    LDA #0
    STA voice_count
    STA director_playing
    STA director_chance         \ (The first, for certain)
    LDA #LO(FIRST_QUIET)
    STA director_quiet
    LDA #HI(FIRST_QUIET)
    STA director_quiet + 1
    LDA #&FF
    STA director_last
    LDA SYSTEM_VIA_T1_LOW       \ A seed, from the time taken to load
    ORA #1
    STA director_random
    STA director_random + 1
    SEI
    LDA ROMSEL_COPY
    STA HOST_music_romsel
    LDA #LO(mbank_event)
    STA HOST_music_event_tick + 1
    LDA #HI(mbank_event)
    STA HOST_music_event_tick + 2
    LDA #LO(no_frame)
    STA HOST_music_event_animate + 1
    LDA #HI(no_frame)
    STA HOST_music_event_animate + 2
    LDA EVNTV
    STA HOST_music_old_evntv
    LDA EVNTV + 1
    STA HOST_music_old_evntv + 1
    LDA #LO(HOST_music_event)
    STA EVNTV
    LDA #HI(HOST_music_event)
    STA EVNTV + 1
    CLI
    LDA #14                     \ Enable the event
    LDX #EVENT_VSYNC
    JMP OSBYTE
.no_frame                       \ (No loading page)
    RTS
}

\ The event's tick: now, unless the host is waiting for vertical sync, to
\ draw ahead of the beam; then owed, and paid once the frame is drawn
\ (host_music_owed).
.mbank_event
{
    LDA HOST_host_vsync_wait
    BNE owed
    JMP mbank_tick
.owed
    INC HOST_host_ticks_owed
    RTS
}

\ A tick: of the piece playing, or of the director's silence.
.mbank_tick
{
    LDA voice_count
    BEQ silent
    JMP music_tick
.silent
    LDA director_playing        \ A piece just ended: quiet for a while
    BEQ quiet
    LDA #0
    STA director_playing
    JSR random
    STA director_quiet          \ QUIET_MIN + QUIET_UNIT * random
    LDA #0
    STA director_quiet + 1
    LDX #5                      \ (QUIET_UNIT = 32)
.unit
    ASL director_quiet
    ROL director_quiet + 1
    DEX
    BNE unit
    CLC
    LDA director_quiet
    ADC #LO(QUIET_MIN)
    STA director_quiet
    LDA director_quiet + 1
    ADC #HI(QUIET_MIN)
    STA director_quiet + 1
    RTS
.quiet
    LDA director_quiet
    ORA director_quiet + 1
    BEQ consider
    LDA director_quiet
    BNE low
    DEC director_quiet + 1
.low
    DEC director_quiet
    RTS
.consider
    JSR occasion
    LDA director_chance
    BEQ play                    \ (The first)
    JSR random
    CMP director_chance
    BCS later
    CPX director_last
    BNE play
    JSR random                  \ Half the chance, played last
    BMI later
.play
    STX director_last
    LDA #PLAY_CHANCE
    STA director_chance
    LDA #&FF
    STA director_playing
    LDA zp_score                \ (The host's zero page, at interrupt time)
    PHA
    LDA zp_score + 1
    PHA
    LDA piece_scores_low,X
    STA zp_score
    LDA piece_scores_high,X
    STA zp_score + 1
    JSR music_play
    PLA
    STA zp_score + 1
    PLA
    STA zp_score
    RTS
.later
    LDA #LO(CONSIDER_TICKS)
    STA director_quiet
    LDA #HI(CONSIDER_TICKS)
    STA director_quiet + 1
    RTS
}

\ X: the piece for the world as it is (HOST_host_world, HOST_host_time).
.occasion
{
    LDX #PIECE_UNDERGROUND
    LDA HOST_host_world
    BMI done                    \ (WORLD_UNDERGROUND)
    LDX #PIECE_NIGHT
    LDA HOST_host_time
    CMP #DAWN_TIME
    BCC done
    LDX #PIECE_DAWN
    CMP #DAY_TIME
    BCC done
    LDX #PIECE_DAYLIGHT
    CMP #DUSK_TIME
    BCC done
    LDX #PIECE_DUSK
    CMP #NIGHT_TIME
    BCC done
    LDX #PIECE_NIGHT
.done
    RTS
}
ASSERT WORLD_UNDERGROUND = &80

\ A, a random byte: a 16-bit Galois LFSR. Keeps X and Y.
.random
{
    LSR director_random + 1
    ROR director_random
    BCC done
    LDA director_random + 1
    EOR #&B4
    STA director_random + 1
.done
    LDA director_random
    RTS
}

.piece_scores_low
    EQUB LO(score_overture), LO(score_dawn), LO(score_daylight), LO(score_dusk), LO(score_night)
    EQUB LO(score_underground)
.piece_scores_high
    EQUB HI(score_overture), HI(score_dawn), HI(score_daylight), HI(score_dusk), HI(score_night)
    EQUB HI(score_underground)

.director_quiet     EQUW 0      \ Ticks of silence left
.director_chance    EQUB 0      \ Of a piece, in 256, each consideration (0: certain)
.director_last      EQUB 0      \ The piece played last
.director_playing   EQUB 0      \ Non-zero while a piece plays
.director_random    EQUW 0

FULL_ORCHESTRA = TRUE             \ The game's instruments too
INCLUDE "asm/music5000.asm"
ASSERT waves <= MBANK_CODE_END     \ (The player's code is before its tables)
INCLUDE "build/generated/m5_overture.asm"
INCLUDE "build/generated/m5_day.asm"

.mbank_end
ASSERT mbank_end <= MBANK_START + MBANK_PAGES * 256
SAVE "MBANK", mbank_entries, mbank_end
