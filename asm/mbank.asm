\ MBANK: the game's music on the Music 5000, in a fourth sideways RAM bank,
\ when there is one (the filing system in ROM): its own copy of the player
\ (asm/music5000.asm) and its piece. STRAT's loader loads it into the bank
\ beneath the loading page, and once the game is set up selects the bank
\ and calls MBANK_START, which starts the piece and points STRAT's
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
GUARD &A000                     \ (The B+ shows code at &A000-&AFFF the shadow)

.mbank_entries
    JMP mbank_start             \ MBANK_START
    JMP music_tick              \ MBANK_TICK: a tick owed (host_music_owed)
ASSERT mbank_entries = MBANK_START

\ Start the piece, and tick it from the vertical sync event: this bank,
\ selected, is the event's ROMSEL; its calls, mbank_event and an RTS.
.mbank_start
{
    LDA #LO(score_overture)
    STA zp_score
    LDA #HI(score_overture)
    STA zp_score + 1
    JSR music_init
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
    JMP music_tick
.owed
    INC HOST_host_ticks_owed
    RTS
}

INCLUDE "asm/music5000.asm"
INCLUDE "build/generated/m5_overture.asm"

.mbank_end
ASSERT mbank_end <= MBANK_START + MBANK_PAGES * 256
SAVE "MBANK", mbank_entries, mbank_end
