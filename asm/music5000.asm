\ A player for the Music 5000, driven directly, without AMPLE
\ (tools/stratagem/music5000.py, docs/music-5000.md): music_init clears the
\ board, loads its waves and starts the score at zp_score; music_tick, once
\ a frame, advances each voice, a channel with a stream of notes and rests
\ and an envelope.
\
\ JIM's page register is write-only, and shared: the OS keeps a copy of it
\ at &EE, written before it. music_tick leaves the register page selected;
\ a caller at interrupt time puts back the page it found in &EE.
\
\ The includer declares zp_ptr and zp_score (two bytes each).

JIM_PAGE = &FCFF                \ Write only: a read loads it from the bus
JIM_COPY = &EE                  \ The OS's copy of it, written first
JIM = &FD00
FIRST_PAGE = &30                \ The board's RAM, in eight pages of two
REGISTER_PAGE = &3E             \ The channel registers (normal bank)
FREQ_LOW = JIM + &00            \ Each a row of sixteen, one per channel
FREQ_MIDDLE = JIM + &10
FREQ_HIGH = JIM + &20
WAVE_SELECT = JIM + &50
AMPLITUDE = JIM + &60
CONTROL = JIM + &70
CHANNELS = 16

ATTACK = 0                      \ A voice's phase
DECAY = 1
SUSTAIN = 2
RELEASE = 3

\ Clear the board, load the waves, and start the score at zp_score, all
\ voices silent.
.music_init
{
    \ Zero the board's RAM: every wave, and both banks of registers.
    LDX #FIRST_PAGE
.clear_page
    STX JIM_COPY
    STX JIM_PAGE
    LDA #0
    TAY
.clear
    STA JIM,Y
    INY
    BNE clear
    INX
    INX
    CPX #FIRST_PAGE + 16
    BNE clear_page

    \ The waves, two to a page.
    LDA #LO(waves)
    STA zp_ptr
    LDA #HI(waves)
    STA zp_ptr + 1
    LDX #FIRST_PAGE
.wave_page
    STX JIM_COPY
    STX JIM_PAGE
    LDY #0
.wave
    LDA (zp_ptr),Y
    STA JIM,Y
    INY
    BNE wave
    INC zp_ptr + 1
    INX
    INX
    CPX #FIRST_PAGE + WAVES       \ (an even number)
    BNE wave_page

    \ The score's voices.
    LDY #voice_table_end - voice_table - 1
.copy
    LDA (zp_score),Y
    STA voice_table,Y
    DEY
    BPL copy

    \ Every channel running, silent, so that each latches its amplitude
    \ (the board takes a new one only at a wave wrap); then each voice's
    \ wave and stereo position.
    LDA #REGISTER_PAGE
    STA JIM_COPY
    STA JIM_PAGE
    LDX #CHANNELS - 1
.channel
    LDA #LO(PITCH_FIRST)
    STA FREQ_LOW,X
    LDA #HI(PITCH_FIRST)
    STA FREQ_MIDDLE,X
    LDA #PITCH_FIRST >> 16
    STA FREQ_HIGH,X
    DEX
    BPL channel
    LDX voice_count
    DEX
.voice
    LDA voice_wave,X
    STA WAVE_SELECT,X
    LDA voice_stereo,X
    STA CONTROL,X
    LDA voice_start_low,X
    STA voice_low,X
    LDA voice_start_high,X
    STA voice_high,X
    LDA #1                      \ The first tick fetches
    STA voice_ticks,X
    LDA #0
    STA voice_level,X
    LDA #RELEASE
    STA voice_phase,X
    DEX
    BPL voice

    RTS
}

\ Advance every voice a tick, writing its amplitude, and its pitch when a
\ note starts.
.music_tick
{
    LDA #REGISTER_PAGE
    STA JIM_COPY
    STA JIM_PAGE
    LDX voice_count
    DEX
.voice
    DEC voice_ticks,X
    BNE playing
    LDA voice_low,X             \ The next event
    STA zp_ptr
    LDA voice_high,X
    STA zp_ptr + 1
    LDY #0
    LDA (zp_ptr),Y
    CMP #LOOP
    BNE event
    LDA voice_start_low,X
    STA zp_ptr
    LDA voice_start_high,X
    STA zp_ptr + 1
    LDA (zp_ptr),Y
.event
    INY
    PHA
    LDA (zp_ptr),Y
    STA voice_ticks,X
    CLC
    LDA zp_ptr
    ADC #2
    STA voice_low,X
    LDA zp_ptr + 1
    ADC #0
    STA voice_high,X
    PLA
    CMP #REST
    BEQ release
    STA voice_note,X
    TAY
    LDA pitch_low,Y
    STA FREQ_LOW,X
    LDA pitch_middle,Y
    STA FREQ_MIDDLE,X
    LDA pitch_high,Y
    STA FREQ_HIGH,X
    LDA #ATTACK
    STA voice_phase,X
    BPL envelope                \ (always)
.playing
    LDA voice_ticks,X
    CMP voice_release_ticks,X
    BNE envelope
.release
    LDA #RELEASE
    STA voice_phase,X

.envelope
    LDY voice_phase,X
    BEQ attack
    DEY
    BEQ decay
    DEY
    BEQ write                   \ (sustain)
    LDA voice_level,X           \ Release, to silence
    SEC
    SBC voice_release,X
    BCS store
    LDA #0
    BCC store                   \ (always)
.attack
    LDA voice_level,X
    CLC
    ADC voice_attack,X
    BCS full
    CMP #FULL
    BCC store
.full
    LDA #DECAY
    STA voice_phase,X
    LDA #FULL
    BNE store                   \ (always)
.decay
    LDA voice_level,X
    SEC
    SBC voice_decay,X
    BCC at_sustain
    CMP voice_sustain,X
    BEQ at_sustain
    BCS store
.at_sustain
    LDA #SUSTAIN
    STA voice_phase,X
    LDA voice_sustain,X
.store
    STA voice_level,X
.write
    LDA voice_level,X
    STA AMPLITUDE,X
    DEX
    BMI done
    JMP voice
.done
.*music_tick_end
    RTS
}

INCLUDE "build/generated/m5play.asm"

\ A score's voice table is copied here (stratagem.music5000.score_source).
.voice_table
.voice_count        SKIP 1
.voice_start_low    SKIP MAX_VOICES
.voice_start_high   SKIP MAX_VOICES
.voice_attack       SKIP MAX_VOICES
.voice_decay        SKIP MAX_VOICES
.voice_sustain      SKIP MAX_VOICES
.voice_release      SKIP MAX_VOICES
.voice_release_ticks SKIP MAX_VOICES
.voice_wave         SKIP MAX_VOICES
.voice_stereo       SKIP MAX_VOICES
.voice_table_end
\ Each voice's state
.voice_low          SKIP MAX_VOICES \ Its next event
.voice_high         SKIP MAX_VOICES
.voice_ticks        SKIP MAX_VOICES \ Ticks left of the current one
.voice_level        SKIP MAX_VOICES \ The amplitude written
.voice_phase        SKIP MAX_VOICES
.voice_note         SKIP MAX_VOICES \ The pitch sounding (an index)

