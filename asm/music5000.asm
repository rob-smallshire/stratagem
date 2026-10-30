\ A player for the Music 5000, driven directly, without AMPLE
\ (tools/stratagem/sequencer.py has its score format and its model,
\ docs/music-5000.md the story): music_init clears the board, loads its
\ waves and starts the piece at zp_score; music_tick, once a frame,
\ advances the piece's clock and, at each step, its conductor and each of
\ its voices, a channel with a stream of notes, rests and changes, calling
\ the piece's patterns; and every voice's envelope and vibrato.
\
\ The clock adds the piece's tempo (steps a tick, in 65536ths) each tick:
\ a carry is a step. A voice reads its next events when its current one's
\ steps are over, and releases a note when its gap is all that is left.
\ The conductor's level, which slopes a little each step, makes every
\ voice quieter.
\
\ JIM's page register is write-only, and shared: the OS keeps a copy of it
\ at &EE, written before it. music_tick leaves the register page selected;
\ a caller at interrupt time puts back the page it found in &EE.
\
\ The includer includes asm/os.asm (JIM_PAGE, JIM_COPY), declares zp_ptr
\ and zp_score (two bytes each), and includes the pieces it plays
\ (build/generated/m5_<name>.asm).

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

\ The byte at zp_ptr, into A, and zp_ptr moves on (Y is 0).
MACRO MUSIC_BYTE
    LDY #0
    LDA (zp_ptr),Y
    INC zp_ptr
    BNE done
    INC zp_ptr + 1
.done
ENDMACRO

ATTACK = 0                      \ A voice's phase
DECAY = 1
SUSTAIN = 2
RELEASE = 3

\ Clear the board, load the waves, and start the piece at zp_score, all
\ voices silent (music_play: only start the piece).
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

    \ The piece's table, and the addresses of its patterns' tables, into
    \ the instructions that read them.
.*music_play
    LDY #piece_table_end - piece_table - 1
.copy
    LDA (zp_score),Y
    STA piece_table,Y
    DEY
    BPL copy
    LDY #piece_table_end - piece_table
    LDA (zp_score),Y
    STA read_pattern_low + 1
    INY
    LDA (zp_score),Y
    STA read_pattern_low + 2
    INY
    LDA (zp_score),Y
    STA read_pattern_high + 1
    INY
    LDA (zp_score),Y
    STA read_pattern_high + 2

    \ The clock a hair short of a step, so that the first tick reads the
    \ first events.
    LDA #&FF
    STA music_clock
    STA music_clock + 1
    LDA conductor_start
    STA conductor_low
    LDA conductor_start + 1
    STA conductor_high
    LDA #1
    STA conductor_steps
    LDA #0
    STA music_level
    STA music_level + 1
    STA music_slope
    STA music_slope + 1

    \ Every channel running, silent, so that each latches its amplitude
    \ (the board takes a new one only at a wave wrap).
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
    LDA #1
    STA voice_steps,X
    LDA #0
    STA voice_release_at,X
    STA voice_gap,X
    STA voice_pitch,X
    STA voice_depth,X
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

\ Silence every channel (each takes amplitude 0 at its next wave wrap).
.music_silence
{
    LDA #REGISTER_PAGE
    STA JIM_COPY
    STA JIM_PAGE
    LDA #0
    LDX #CHANNELS - 1
.channel
    STA AMPLITUDE,X
    DEX
    BPL channel
    RTS
}

\ A tick: the clock, then at a step the conductor and each voice's next
\ events or its release; each voice's vibrato and envelope; and its
\ amplitude, the envelope's, quieter by the voice's level and the
\ conductor's.
\
\ A note's frequency is the pitch table's, detuned by so many units of it
\ shifted right by the instrument's shift; vibrato then moves it a unit a
\ tick, in a triangle of eight ticks (6.25Hz), two units either side, from
\ the instrument's vibrato delay into the note.
.music_tick
{
    LDA voice_count             \ A piece played once, over (END)
    BNE playing
    RTS
.playing
    LDA #REGISTER_PAGE
    STA JIM_COPY
    STA JIM_PAGE
    CLC
    LDA music_clock
    ADC piece_tempo
    STA music_clock
    LDA music_clock + 1
    ADC piece_tempo + 1
    STA music_clock + 1
    LDA #0
    ROL A
    STA music_stepped
    BEQ conducted
    JSR conduct
.conducted
    LDX voice_count
    BNE voices
    RTS                         \ (It ended this step)
.voices
    DEX
.voice
    LDA music_stepped
    BEQ vibrato
    DEC voice_steps,X
    BNE not_over
    JSR read
    BCC vibrato
    JMP envelope                \ (a note started: no vibrato yet)
.not_over
    LDA voice_steps,X
    CMP voice_release_at,X
    BNE vibrato
    LDA #RELEASE                \ All that's left is the note's gap
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
    CLC                         \ (unit_up and write_frequency, inline: a
    LDA voice_freq_low,X        \ tick vibrates most voices)
    ADC voice_unit_low,X
    STA voice_freq_low,X
    AND #&FE
    STA FREQ_LOW,X
    LDA voice_freq_middle,X
    ADC voice_unit_high,X
    STA voice_freq_middle,X
    STA FREQ_MIDDLE,X
    BCC envelope                \ (the high byte as it was)
    INC voice_freq_high,X
    LDA voice_freq_high,X
    STA FREQ_HIGH,X
    JMP envelope
.down
    SEC                         \ (unit_down and write_frequency, inline)
    LDA voice_freq_low,X
    SBC voice_unit_low,X
    STA voice_freq_low,X
    AND #&FE
    STA FREQ_LOW,X
    LDA voice_freq_middle,X
    SBC voice_unit_high,X
    STA voice_freq_middle,X
    STA FREQ_MIDDLE,X
    BCS envelope
    DEC voice_freq_high,X
    LDA voice_freq_high,X
    STA FREQ_HIGH,X

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
    CLC                         \ Quieter by the voice's level and the
    LDA voice_quieter,X         \ conductor's (each signed), if that's
    ADC music_level + 1         \ quieter at all
    BVS overflowed
    BPL quieter
    LDA #0
    BEQ quieter                 \ (always)
.overflowed
    BMI quieter                 \ (both quieter: 128 to 254)
    LDA #0
.quieter
    STA music_argument
    LDA voice_level,X
    SEC
    SBC music_argument
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

\ A step for the conductor: its level slopes, and when its wait is over
\ it reads on to its next.
.conduct
{
    CLC
    LDA music_level
    ADC music_slope
    STA music_level
    LDA music_level + 1
    ADC music_slope + 1
    STA music_level + 1
    DEC conductor_steps
    BNE done
    LDA conductor_low
    STA zp_ptr
    LDA conductor_high
    STA zp_ptr + 1
.next
    MUSIC_BYTE
    CMP #END
    BNE not_end
    LDA #0                      \ No voices: the piece is over
    STA voice_count
    RTS
.not_end
    CMP #LOOP
    BNE not_loop
    LDA conductor_start
    STA zp_ptr
    LDA conductor_start + 1
    STA zp_ptr + 1
    JMP next
.not_loop
    CMP #WAIT
    BNE level
    MUSIC_BYTE
    STA conductor_steps
    LDA zp_ptr
    STA conductor_low
    LDA zp_ptr + 1
    STA conductor_high
.done
    RTS
.level
    PHA                         \ LEVEL or SLOPE, eight bits and eight
    MUSIC_BYTE
    STA music_argument
    MUSIC_BYTE
    TAY
    PLA
    CMP #LEVEL
    BNE slope
    LDA music_argument
    STA music_level
    STY music_level + 1
    JMP next
.slope
    LDA music_argument
    STA music_slope
    STY music_slope + 1
    JMP next
}

\ Voice X's events, to its next note, hold or rest; carry set if a note
\ started.
.read
{
    LDA voice_low,X
    STA zp_ptr
    LDA voice_high,X
    STA zp_ptr + 1
.next
    MUSIC_BYTE
    CMP #&80
    BCS not_note
    PHA                         \ A note: an interval, -8 to +7, in bits
    AND #SLOTS - 1              \ 6-3, and a slot from the piece's
    TAY
    LDA piece_slots,Y
    STA music_slot
    PLA
    LSR A
    LSR A
    LSR A
    SEC
    SBC #8
    JMP note
.not_note
    CMP #PAN
    BCS not_gap
    AND #7
    STA voice_gap,X
    JMP next
.not_gap
    CMP #DETUNE
    BCS not_pan
    SBC #PAN - 1                \ (carry clear)
    STA CONTROL,X
    JMP next
.not_pan
    CMP #INSTRUMENT
    BCS not_detune
    SBC #DETUNE - 1             \ (carry clear)
    CMP #8
    BCC detune
    ORA #&F0                    \ (-8 to -1)
.detune
    STA voice_detune,X
    JMP next
.not_detune
    CMP #INSTRUMENT + MAX_INSTRUMENTS
    BCS not_instrument
    SBC #INSTRUMENT - 1         \ (carry clear)
    TAY
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
.not_instrument
    CMP #RETURN
    BNE not_return
    LDA voice_depth,X           \ Back where the pattern was called
    SEC
    SBC #CHANNELS
    STA voice_depth,X
    TXA
    CLC
    ADC voice_depth,X
    TAY
    LDA voice_returns_low,Y
    STA zp_ptr
    LDA voice_returns_high,Y
    STA zp_ptr + 1
    JMP next
.not_return
    CMP #LOOP
    BNE not_loop
    LDA voice_start_low,X
    STA zp_ptr
    LDA voice_start_high,X
    STA zp_ptr + 1
    JMP next
.not_loop
    PHA                         \ The rest have an argument
    MUSIC_BYTE
    STA music_argument
    PLA
    CMP #CALL
    BNE not_call
    TXA                         \ Where to come back to...
    CLC
    ADC voice_depth,X
    TAY
    LDA zp_ptr
    STA voice_returns_low,Y
    LDA zp_ptr + 1
    STA voice_returns_high,Y
    LDA voice_depth,X
    CLC
    ADC #CHANNELS
    STA voice_depth,X
    LDY music_argument          \ ... and the pattern
.*read_pattern_low
    LDA &FFFF,Y                 \ (the piece's table of patterns, by music_init)
    STA zp_ptr
.*read_pattern_high
    LDA &FFFF,Y
    STA zp_ptr + 1
    JMP next
.not_call
    CMP #QUIETER
    BNE not_quieter
    LDA music_argument
    STA voice_quieter,X
    JMP next
.not_quieter
    CMP #PITCH
    BNE not_pitch
    LDA music_argument
    STA voice_pitch,X
    JMP next
.not_pitch
    CMP #NOTE
    BNE timed
    MUSIC_BYTE
    STA music_slot
    LDA music_argument
    JMP note
.timed
    TAY                         \ A REST or a HOLD
    LDA music_argument
    STA voice_steps,X
    LDA #0
    STA voice_release_at,X
    CPY #REST
    BNE kept
    LDA #RELEASE
    STA voice_phase,X
.kept
    JSR keep_place
    CLC
    RTS

    \ A note, A semitones from the last, for music_slot steps
.note
    CLC
    ADC voice_pitch,X
    STA voice_pitch,X
    TAY
    LDA music_slot
    STA voice_steps,X
    LDA voice_gap,X
    STA voice_release_at,X
    JSR keep_place
    LDA pitch_low,Y             \ Its pitch...
    STA voice_freq_low,X
    STA music_unit
    LDA pitch_middle,Y
    STA voice_freq_middle,X
    STA music_unit + 1
    LDA pitch_high,Y
    STA voice_freq_high,X
    STA music_unit + 2
    LDY voice_shift,X           \ ... its unit (the pitch's top two bytes,
    BEQ unit                    \ shifted right a further shift - 8)...
.shift
    LSR music_unit + 2
    ROR music_unit + 1
    DEY
    BNE shift
.unit
    LDA music_unit + 1
    STA voice_unit_low,X
    LDA music_unit + 2
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
    SEC
    RTS
}

\ Voice X's place in its stream, kept for its next events.
.keep_place
{
    LDA zp_ptr
    STA voice_low,X
    LDA zp_ptr + 1
    STA voice_high,X
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

\ A piece's table is copied here (stratagem.sequencer.piece_source).
.piece_table
.voice_count        SKIP 1
.voice_start_low    SKIP MAX_VOICES
.voice_start_high   SKIP MAX_VOICES
.conductor_start    SKIP 2
.piece_tempo        SKIP 2      \ Steps a tick, in 65536ths
.piece_slots        SKIP SLOTS  \ Its notes' commonest lengths, in steps
.piece_table_end

.music_state                    \ What a tick changes
\ The clock and the conductor
.music_clock        SKIP 2      \ The fraction of a step
.music_stepped      SKIP 1      \ 1 if this tick is a step
.conductor_low      SKIP 1      \ Its next event
.conductor_high     SKIP 1
.conductor_steps    SKIP 1      \ Steps left of its wait
.music_level        SKIP 2      \ Steps quieter for every voice (8.8, signed)
.music_slope        SKIP 2      \ Added to it a step
\ Each voice's state
.voice_low          SKIP MAX_VOICES \ Its next event
.voice_high         SKIP MAX_VOICES
.voice_steps        SKIP MAX_VOICES \ Steps left of the current one
.voice_release_at   SKIP MAX_VOICES \ Release the note with this many left (0: none)
.voice_gap          SKIP MAX_VOICES \ Its notes' gap, in steps
.voice_pitch        SKIP MAX_VOICES \ Its last note, in the pitch table
.voice_depth        SKIP MAX_VOICES \ Its patterns called, times CHANNELS
.voice_level        SKIP MAX_VOICES \ The envelope's
.voice_phase        SKIP MAX_VOICES
.voice_quieter      SKIP MAX_VOICES \ Steps below the envelope (signed)
.voice_attack       SKIP MAX_VOICES \ Its instrument's envelope
.voice_decay        SKIP MAX_VOICES
.voice_sustain      SKIP MAX_VOICES
.voice_release      SKIP MAX_VOICES
.voice_shift        SKIP MAX_VOICES \ Its unit's: the pitch shifted right 8 and this far
.voice_vibrato      SKIP MAX_VOICES \ Ticks into a note to vibrato, or 0: none
.voice_detune       SKIP MAX_VOICES \ Units (signed)
.voice_freq_low     SKIP MAX_VOICES \ Its frequency
.voice_freq_middle  SKIP MAX_VOICES
.voice_freq_high    SKIP MAX_VOICES
.voice_unit_low     SKIP MAX_VOICES \ Its unit, for detuning and vibrato
.voice_unit_high    SKIP MAX_VOICES
.voice_vibrato_count SKIP MAX_VOICES \ Ticks before vibrato
.voice_lfo          SKIP MAX_VOICES \ The vibrato's tick, 0-7
.voice_returns_low  SKIP MAX_DEPTH * MAX_VOICES \ Where each call came from,
.voice_returns_high SKIP MAX_DEPTH * MAX_VOICES \ a row of voices a depth
.music_argument     SKIP 1
.music_slot         SKIP 1
.music_unit         SKIP 3
.music_state_end
