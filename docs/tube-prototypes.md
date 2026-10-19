# Tube prototypes

Prototypes for deciding how Stratagem uses a 65C02 second processor
alongside the expanded host (see
`docs/hardware-requirements-and-capabilities.md`). Each answers one question
by measurement, on both targets in Beebium.

1. Tube plumbing: what each way of moving data costs the host.
2. Light on the parasite: per-cell light centred on the miner's exact
   position, and how many cells change per frame.
3. Host drawing with the memory freed: masked, pre-dithered, dark fills.
4. Double buffering (B+ only: the Integra-B's video reads only main RAM)
   against a single screen with raster-timed updates.

## 1. Tube plumbing

`asm/tube_proto.asm` (`TUBEH` in the host at `&2000`, `TUBEP` in the
parasite at `&1000`), measured by `tests/test_tube_proto.py` (run with `-s`).
The host extends OSWRCH and OSWORD as Second Processor Elite does, and
pulls and pushes 256-byte blocks through `&0406` as ADFS does (three NOPs
per byte: the parasite's polled loop must keep up).

Host cycles (2 MHz), 3 MHz 65C02 parasite, Beebium 0.11.0:

| Exchange | B+128K | Integra-B |
|---|---|---|
| OSWRCH stream, per byte (idle loop, WRCHV, handler) | 90.5 | 91.9 |
| Host pulls 256 bytes (type 6), with claim and release | 6,108 | 6,108 |
| Host pushes 256 bytes (type 7), with claim and release | 5,844 | 5,844 |
| OSWORD, 128 bytes each way | 8,907 | 9,079 |
| Empty OSWORD round trip | 263 | 266 |
| A 2-byte OSWRCH command | 167 | 167 |

- Bulk data costs about 20 host cycles a byte by block transfer (plus about
  900 for claim, set-up and release), against about 90 through OSWRCH and
  35 each way through OSWORD.
- OSWRCH suits commands: up to 24 bytes queue in R1 without stopping the
  parasite. Anything larger stalls the parasite while the host catches up.
- During a block transfer the parasite is in its interrupt handler, so
  both processors are busy for its duration (about 3 ms).
