\ A player for the Music 5000, driven directly, without AMPLE
\ (tools/stratagem/music5000.py, docs/music-5000.md): music_init clears the
\ board, loads its waves and starts the score at zp_score; music_tick, once
\ a frame, advances each voice, a channel with a stream of notes, rests and
\ changes of instrument and volume, and an envelope.
\
\ JIM's page register is write-only, and shared: the OS keeps a copy of it
\ at &EE, written before it. music_tick leaves the register page selected;
\ a caller at interrupt time puts back the page it found in &EE.
\
\ The includer declares zp_ptr and zp_score (two bytes each), and includes
\ the scores it plays (build/generated/m5_<score>.asm).

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
    \ (the board takes a new one only at a wave wrap). Each voice's stream
    \ starts with its instrument.
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
    LDA voice_start_low,X
    STA voice_low,X
    LDA voice_start_high,X
    STA voice_high,X
    LDA #1                      \ The first tick fetches
    STA voice_ticks,X
    LDA #0
    STA voice_level,X
    STA voice_quieter,X
    STA voice_release,X
    STA voice_detune,X
    STA voice_vibrato,X
    LDA #RELEASE
    STA voice_phase,X
    DEX
    BPL channel
    RTS
}

\ Advance every voice a tick: take its next events when its current one
\ ends; move its pitch for vibrato; and write its amplitude.
\
\ A note's frequency is the pitch table's, detuned by so many units of it
\ shifted right by the instrument's shift; vibrato then moves it a unit a
\ tick, in a triangle of eight ticks (6.25Hz), two units either side, from
\ the instrument's vibrato delay into the note.
.music_tick
{
    LDA #REGISTER_PAGE
    STA JIM_COPY
    STA JIM_PAGE
    LDX voice_count
    DEX
.voice
    DEC voice_ticks,X
    BEQ fetch
    JMP vibrato
.fetch
    LDA voice_low,X
    STA zp_ptr
    LDA voice_high,X
    STA zp_ptr + 1
.next
    LDY #0
    LDA (zp_ptr),Y
    CMP #LOOP
    BNE event
    LDA voice_start_low,X
    STA zp_ptr
    LDA voice_start_high,X
    STA zp_ptr + 1
    JMP next
.event
    PHA
    INY
    LDA (zp_ptr),Y
    STA music_argument
    CLC
    LDA zp_ptr
    ADC #2
    STA zp_ptr
    BCC advanced
    INC zp_ptr + 1
.advanced
    PLA
    CMP #VOLUME
    BNE not_volume
    LDA music_argument
    STA voice_quieter,X
    JMP next
.not_volume
    CMP #PAN
    BNE not_pan
    LDA music_argument
    STA CONTROL,X
    JMP next
.not_pan
    CMP #DETUNE
    BNE not_detune
    LDA music_argument
    STA voice_detune,X
    JMP next
.not_detune
    CMP #INSTRUMENT
    BNE timed
    LDY music_argument
    LDA instrument_attacks,Y
    STA voice_attack,X
    LDA instrument_decays,Y
    STA voice_decay,X
    LDA instrument_sustains,Y
    STA voice_sustain,X
    LDA instrument_releases,Y
    STA voice_release,X
    LDA instrument_waves,Y
    STA WAVE_SELECT,X
    LDA instrument_stereos,Y
    STA CONTROL,X
    LDA instrument_shifts,Y
    STA voice_shift,X
    LDA instrument_vibratos,Y
    STA voice_vibrato,X
    JMP next
.timed
    PHA                         \ A note, HOLD or REST
    LDA zp_ptr
    STA voice_low,X
    LDA zp_ptr + 1
    STA voice_high,X
    LDA music_argument
    STA voice_ticks,X
    PLA
    CMP #REST
    BEQ release
    CMP #HOLD
    BEQ vibrato
    TAY                         \ A note: its pitch...
    LDA pitch_low,Y
    STA voice_freq_low,X
    STA music_unit
    LDA pitch_middle,Y
    STA voice_freq_middle,X
    STA music_unit + 1
    LDA pitch_high,Y
    STA voice_freq_high,X
    STA music_unit + 2
    LDY voice_shift,X           \ ... its unit...
.shift
    LSR music_unit + 2
    ROR music_unit + 1
    ROR music_unit
    DEY
    BNE shift
    LDA music_unit
    STA voice_unit_low,X
    LDA music_unit + 1
    STA voice_unit_high,X
    LDY voice_detune,X          \ ... detuned
    BEQ tuned
    BMI flat
.sharp
    JSR unit_up
    DEY
    BNE sharp
    BEQ tuned                   \ (always)
.flat
    JSR unit_down
    INY
    BNE flat
.tuned
    JSR write_frequency
    LDA voice_vibrato,X
    STA voice_vibrato_count,X
    LDA #0
    STA voice_lfo,X
    LDA #ATTACK
    STA voice_phase,X
    BPL envelope                \ (always)
.release
    LDA #RELEASE
    STA voice_phase,X

.vibrato
    LDA voice_vibrato,X         \ None for this instrument
    BEQ envelope
    LDA voice_vibrato_count,X
    BEQ vibrating
    DEC voice_vibrato_count,X   \ Not yet
    JMP envelope
.vibrating
    LDY voice_lfo,X
    INY
    TYA
    AND #7
    STA voice_lfo,X
    TAY
    LDA vibrato_up,Y
    BEQ down
    JSR unit_up
    JMP vibrated
.down
    JSR unit_down
.vibrated
    JSR write_frequency

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
    LDA voice_level,X           \ The envelope, quieter by the voice's volume
    SEC
    SBC voice_quieter,X
    BCS loud
    LDA #0
.loud
    STA AMPLITUDE,X
    DEX
    BMI done
    JMP voice
.done
.*music_tick_end
    RTS
}

\ Raise and lower voice X's frequency by its unit.
.unit_up
{
    CLC
    LDA voice_freq_low,X
    ADC voice_unit_low,X
    STA voice_freq_low,X
    LDA voice_freq_middle,X
    ADC voice_unit_high,X
    STA voice_freq_middle,X
    LDA voice_freq_high,X
    ADC #0
    STA voice_freq_high,X
    RTS
}

.unit_down
{
    SEC
    LDA voice_freq_low,X
    SBC voice_unit_low,X
    STA voice_freq_low,X
    LDA voice_freq_middle,X
    SBC voice_unit_high,X
    STA voice_freq_middle,X
    LDA voice_freq_high,X
    SBC #0
    STA voice_freq_high,X
    RTS
}

\ Write voice X's frequency to its channel, bit 0 clear (set is phase-set).
.write_frequency
{
    LDA voice_freq_low,X
    AND #&FE
    STA FREQ_LOW,X
    LDA voice_freq_middle,X
    STA FREQ_MIDDLE,X
    LDA voice_freq_high,X
    STA FREQ_HIGH,X
    RTS
}

\ The triangle's steps: up (1) or down (0), into each of its eight ticks.
.vibrato_up
    EQUB 1, 1, 1, 0, 0, 0, 0, 1

INCLUDE "build/generated/music5000.asm"

\ A score's voice table is copied here (stratagem.music5000.score_source).
.voice_table
.voice_count        SKIP 1
.voice_start_low    SKIP MAX_VOICES
.voice_start_high   SKIP MAX_VOICES
.voice_table_end
\ Each voice's state
.voice_low          SKIP MAX_VOICES \ Its next event
.voice_high         SKIP MAX_VOICES
.voice_ticks        SKIP MAX_VOICES \ Ticks left of the current one
.voice_level        SKIP MAX_VOICES \ The envelope's
.voice_phase        SKIP MAX_VOICES
.voice_quieter      SKIP MAX_VOICES \ Steps below the envelope (its volume)
.voice_attack       SKIP MAX_VOICES \ Its instrument's envelope
.voice_decay        SKIP MAX_VOICES
.voice_sustain      SKIP MAX_VOICES
.voice_release      SKIP MAX_VOICES
.voice_shift        SKIP MAX_VOICES \ Its unit's: the pitch shifted right this far
.voice_vibrato      SKIP MAX_VOICES \ Ticks into a note to vibrato, or 0: none
.voice_detune       SKIP MAX_VOICES \ Units (signed)
.voice_freq_low     SKIP MAX_VOICES \ Its frequency
.voice_freq_middle  SKIP MAX_VOICES
.voice_freq_high    SKIP MAX_VOICES
.voice_unit_low     SKIP MAX_VOICES \ Its unit, for detuning and vibrato
.voice_unit_high    SKIP MAX_VOICES
.voice_vibrato_count SKIP MAX_VOICES \ Ticks before vibrato
.voice_lfo          SKIP MAX_VOICES \ The vibrato's tick, 0-7
.music_argument     SKIP 1
.music_unit         SKIP 3
