# Auditorium: processing after the mix, for Beebium

A proposal for an optional real-time effect in Beebium, applied to all of
the emulator's sound after mixing: the SN76489 and the Music 5000
together, as a machine's audio would sound played through a mixer, an
effects unit and a hall. Off by default, and enabled with something like
`--auditorium`.

The DSP is already worked out offline, as a Python reference chain run on
a recording of Beebium's Music 5000 output: `tools/stratagem/m5_master.py`
in the Stratagem repository (`uv run strat-m5-master`, which writes
`build/features/overture-processed.wav`). The Stratagem author has
listened to that result and likes it. This document describes the same
chain, with the changes it needs to run in real time and on the whole mix.

## Where it goes

- **Input:** the emulator's final stereo mix, after every source has been
  mixed, and after each source's own output filter (for the Music 5000,
  Beebium's second-order low-pass at about 2kHz). It is the last stage
  before the audio device, and before any recording that clients can ask
  to have processed.
- **Mono sources:** the SN76489 arrives in the mix as mono (equal in both
  channels, or however Beebium pans it). The width stage does nothing to
  mono, but the reverb's tail is decorrelated between left and right, so
  even the beeper gains some space.
- **Rate:** whatever rate Beebium's output runs at (the reference uses
  48kHz). Compute every coefficient from the sample rate; nothing here
  depends on one rate. The Music 5000 itself runs at 46875Hz, and the
  SN76489 at 250kHz before Beebium resamples it.
- **Stereo throughout:** every stage keeps left and right separate,
  except where this document says a stage links them.

## The SN76489 in the chain

The reference was tuned on the Music 5000 alone, whose output is filtered
steeply above 2kHz. The SN76489's square waves and noise have far more
energy at the top, so some stages act on it differently:

- **The 3kHz presence boost and the saturation** both brighten. On square
  waves they can make the beeper harsher. Listen to a beeper-heavy game,
  and if it is too harsh, either make the boost smaller (+1dB) or put a
  gentle high-shelf cut above about 8kHz before the saturation. Keep the
  Music 5000's sound as it is: that is the one that has been listened to.
- **The saturation's aliasing:** with full-band square waves, tanh adds
  harmonics above Nyquist. At this mild drive and a third of a mix it is
  probably inaudible, but if it isn't, oversample this one stage by 2x.
- **The reverb send's high-pass at 150Hz** stays. The tail's highs die in
  1.1s, so the beeper's bright edges don't ring on long.
- **The levels:** the SN76489 at full volume is probably much louder in
  Beebium's mix than the Music 5000, whose single channel at full
  amplitude is a sixteenth of full scale. The chain doesn't change the
  balance between them. Whatever balance Beebium mixes them at is the
  balance that is compressed and reverberated, so set the reference level
  against the louder of the two (see "Levels").

## The chain, in order

Unless stated otherwise, levels in dBFS are relative to the chain's
reference level (see "Levels" below).

### 1. Low cut

A second-order Butterworth high-pass at 25Hz. It removes rumble and any DC
offset, like a mixer's low cut.

### 2. EQ

Three biquads, in series, using the formulas in Robert Bristow-Johnson's
*Audio EQ Cookbook*:

| Filter | Frequency | Gain | Shape |
|---|---|---|---|
| Low shelf | 120Hz | +6dB | shelf slope S = 1 |
| Peaking | 250Hz | +2dB | Q = 0.8 |
| Peaking | 3kHz | +2dB | Q = 0.9 |

The shelf adds weight. The 250Hz peak adds warmth. The 3kHz peak adds
presence, which counters the board's steep output filter.

`m5_master.py` has `low_shelf()` and `peaking()`, which follow the
cookbook directly: with A = 10^(dB/40) and w = 2π f / fs, they give the
b and a coefficients, normalised by a0.

### 3. Saturation

A gentle valve- or tape-like stage, mixed in parallel:

    y = (1 - m) x + m P tanh(d x / P) / tanh(d)

with drive d = 2 and mix m = 1/3, applied to each channel separately. P
is the level that counts as "peak".

- **Offline,** P is the whole recording's peak.
- **In real time,** fix P at the reference level (see "Levels").

At this drive, and with the board's content mostly below 2kHz, aliasing is
negligible at 48kHz. Oversampling isn't needed.

### 4. Bus compression

A stereo-linked compressor, of the dbx 160 kind:

1. **Detector:** the mean of the two channels' squares, smoothed by a
   one-pole filter with a time constant of 30ms (k = exp(-1 / (0.03 fs)),
   y += (1 - k)(x - y)). The level is the square root of that.
2. **Static curve:** a threshold of -20dBFS and a ratio of 2.5:1. The gain
   in dB is -max(0, level_dB + 20) × (1 - 1/2.5).
3. **Gain smoothing:** a second one-pole on the gain in dB, with a time
   constant of 200ms, the same in both directions.
4. **Apply:** multiply both channels by 10^(gain_dB / 20).

It lifts the quiet passages and glues the parts together.

- **Offline,** the input is first normalised to a peak of 1.
- **In real time,** the threshold is relative to the reference level
  instead.

Separate attack and release times would be a reasonable refinement. The
reference uses one symmetric smoother, and it sounds right.

### 5. Reverb: the auditorium itself

A concert hall: 2.2s, darker as it decays, a quarter of the mix.

**The send:** feed a second-order Butterworth high-pass at 150Hz into the
reverb, so nothing below 150Hz reaches it (to avoid mud). The dry path
stays full range.

**The impulse response,** as `hall_impulse()` builds it: a 3-second stereo
response, generated once when the effect starts.

- **The tail:** independent white noise for each channel (which makes the
  two sides uncorrelated), split into three bands, each with its own
  decay:

  | Band | Filter (second-order Butterworth) | RT60 |
  |---|---|---|
  | Low | low-pass at 400Hz | 2.6s |
  | Mid | band-pass 400Hz-3kHz | 2.2s |
  | High | high-pass at 3kHz | 1.1s |

  Each band is multiplied by exp(-6.91 t / RT60), which gives -60dB at t =
  RT60. The three are summed.
- **The build-up:** the tail ramps up linearly over its first 80ms
  (multiplied by min(1, t / 0.08)).
- **Pre-delay:** the tail starts 25ms into the response.
- **Early reflections:** single-sample impulses at absolute times of 11,
  17, 23, 31, 41 and 53ms from the start of the response. They alternate
  sides, starting on the left. Their gains are 0.5, 0.45, 0.35, 0.3, 0.22
  and 0.18 times the tail's peak absolute value.
- **Normalisation:** scale each channel of the response to unit energy
  (the sum of its squares is 1).

The reference uses NumPy's seeded generator (seed 5000). Any good noise
source will do, but seed it, so that every run sounds the same and the
output can be tested.

**The convolution:** run left with left and right with right. 3s at 48kHz
is 144,000 taps per channel, so use partitioned FFT convolution:

- either uniformly partitioned, with a partition of 128-512 samples, which
  adds that many samples of latency;
- or non-uniform, with a direct-form head for zero latency.

Uniform partitions are simpler and cheap enough on any current machine
(two channels at 48kHz cost a few percent of one core). A latency of a few
milliseconds doesn't matter for a wet signal: the pre-delay is 25ms. The
dry path can stay unaligned, or be delayed to match.

**The mix:** out = 0.75 × dry + 0.25 × wet.

- **Offline,** the wet signal is scaled so that its RMS over the whole
  piece matches the dry signal's.
- **In real time,** use a fixed wet gain. With a unit-energy response, a
  broadband input comes out at roughly its own power. So start with a wet
  gain of 1, and adjust it until the real-time output matches the
  reference by ear and by RMS.

**An alternative,** if convolution is unwelcome: a feedback delay network
(for example 8 or 16 lines, with a Householder or Hadamard mixing matrix).
Give each line a damping filter that decays the three bands at the RT60s
above, and add the same pre-delay and early reflections in front of it.
This is cheaper and easier to change, but harder to match to the
reference exactly. Convolution is recommended first.

### 6. Stereo width

Mid/side:

    mid = (L + R) / 2
    side = (L - R) / 2 × 10^(2/20)
    L' = mid + side
    R' = mid - side

The side is raised by 2dB.

### 7. Output level

**Offline,** the whole result is normalised to a peak of -1dBFS.

**In real time,** use a fixed make-up gain, followed by a safety limiter
with a ceiling of -1dBFS:

- either a lookahead peak limiter, with a few milliseconds of lookahead and
  a release of about 100ms;
- or, more simply, a soft clipper that only acts above -3dBFS.

Normal music should never reach it.

## Levels: the one real-time decision

The offline chain normalises three times: before the saturation, before
the compressor and at the end. It can do that because it can see the
whole piece. A real-time chain can't, so it needs one **reference level**:
the mix's level that is treated as 0dBFS.

- **Proposal:** an input trim before stage 1, set so that the loudest
  normal output peaks at about -6dBFS at the input. Find that output from
  both sources: the SN76489 with all four channels at full volume, and a
  loud Music 5000 tutti (the Stratagem overture's, from `*RUN M5PLAY` on
  the Stratagem disc). Then run the chain as above against 0dBFS.
- A machine that plays only through the board will then sound quieter than
  the reference recording, whose input was normalised. The compressor's
  threshold is what lifts it. If that isn't enough, the trim is there.
- Expose the trim as a parameter, along with the wet mix, and keep the
  rest as constants.

## Behaviour in the emulator

- **Reset** clears all filter, compressor and convolution state, so the
  output is silent and nothing rings on.
- **Pause** stops the output; on resume, carry on from the same state.
- **Warp speed, and other times when audio is discarded:** don't process
  audio that is thrown away. On return to real time, clear the reverb's
  state, so a stale tail doesn't play out.
- **Toggling at run time** (if offered): crossfade over about 20ms, so the
  switch doesn't click.
- **Recording:** any audio stream or WAV capture that clients can
  subscribe to should still offer the raw mix, and the processed output
  as a separate choice. Stratagem's tests compare the raw Music 5000
  output with a model, so the raw stream must not change.
- **Determinism:** with a seeded response and fixed parameters, the same
  input gives the same output, sample for sample.

## Checking it

1. **The filters:** feed in a unit impulse. The magnitude response of
   stages 1-2 should match the table: +6dB well below 120Hz, a 2dB bump at
   250Hz and at 3kHz, and -3dB at 25Hz from the low cut.
2. **The compressor's static curve:** feed in steady sines at levels from
   -40 to 0dBFS. Output against input should be 1:1 below -20dBFS and
   2.5:1 above.
3. **The reverb:** feed in an impulse with the dry path muted. Measure the
   RT60 in octave bands (Schroeder backward integration). Expect about
   2.6s at 250Hz, 2.2s at 1kHz and 1.1s at 4-8kHz. Check that the
   reflections arrive at 11-53ms and the tail at 25ms.
4. **The beeper:** play a square wave and noise on the SN76489. Listen for
   harshness and aliasing (a 2x-oversampled saturation is the fix for the
   latter).
5. **Against the reference:** record the overture from M5PLAY raw (as
   `strat-m5-record` does), run it through `strat-m5-master`, and run the
   same raw recording through Beebium's chain offline. Allowing for the
   level differences described above, the long-term spectra should agree
   within about 1dB, and the two should sound alike.
