# Platform notes

Facts about the target machines that shape the design. Each is marked
**V** (verified against ROM disassembly, Beebium source or an emulator test)
or **U** (unsure). Sources are the beebium-stratagem session's research
(2026-10-18) and our own tests.

## All targets

- PAGE (OSHWM) is `&1900` with Acorn DFS 2.26 on both the B+128K and the
  Integra-B. **V**
- Free sideways RAM slots, as found by `PROBE`: B+128K 0, 1, 12, 13;
  Integra-B 4-7, all writable by default. **V**

- OSFILE writes the file's catalogue information back into its control
  block, so set the block up afresh for every call. **V**

- The Video ULA's flash bit (`&FE20` bit 0) shows a flashing physical
  colour 8 + c as c when clear and as 7 - c when set, from the moment it
  is written. **U** (as jsbeeb does it, `src/video.js`; not yet seen on
  hardware)
- With interlace off (`*TV 0,1`), a MODE 1 frame is 312 lines of exactly
  64us, and the User VIA's timers count at 1MHz from the same crystal, so a
  free-running timer 1 of 64us stays at the same place in every line. A
  write to `&FE20` at CRTC column c takes effect from about column c - 2,
  so it is unseen from column 82 to column 1 of the next line (in MODE 1:
  128 columns, 80 displayed); a write at 80 shows on the last 8 pixels, one
  at 4 on the first 8. The loading screen, narrowed to 64 columns, writes
  at column 77-78 on the B+ and 71-72 on the Integra-B, whose vertical sync
  comes about 3us later in a line (`docs/loading-screen.md`). **V**
  (Beebium; by moving the writes and comparing frames)
- Beebium draws the flash bit from 0.15.0, from the pixel after the write
  (beebium #226), so a captured frame shows `LOADSCR`'s six colours
  exactly as `stratagem.loading_screen` simulates them. Before, it drew
  flashing colours in their first colour whatever the bit. **V**

## BBC B+ 128K

- The shadow RAM is the screen. The CPU reaches it at `&3000`-`&7FFF` only
  from code at `&C000`-`&DFFF`, or at `&A000`-`&AFFF` while ANDY (ROMSEL
  bit 7) is paged in. **V**
- With shadow on, OSFILE loads to `&3000`-`&7FFF` land in main RAM: the
  DFS byte-move NMI code in page `&0D` is not VDU code. **V**
- MOS 2.00, DFS 2.26 and ANFS 4.18 do not use ANDY, so the plotter can run
  there and write the screen directly. **V**
- Keep `&F4` equal to the ROMSEL value, **including bit 7**, while ANDY is
  paged in. Service calls and the ANFS Econet NMI handler restore ROMSEL
  from `&F4`; plain IRQs do not touch ROMSEL. **V**
- A BRK (error) raised in ANDY code pages in the language ROM without bit 7
  and loses ANDY. Never raise errors from ANDY code. **V**
- The hardware (B+ Service Manual, PAL IC36) latches the VDU-driver flag at
  each opcode fetch, so the opcode's address decides, for the whole
  instruction. Beebium used the live PC until #185 (fixed after 1.x
  releases; check the version in use). **V** So no instruction that touches
  `&3000`-`&7FFF` may straddle `&9FFF`/`&A000`, `&AFFF`/`&B000` or
  `&DFFF`/`&E000`; keep the ANDY plotter a few bytes clear of each end. **V**
- Shadow RAM and ANDY are ordinary 2 MHz accesses in Beebium (no clock
  stretching); probably the same on real hardware. **U**

## Integra-B (Model B, MOS 1.20, IBOS 1.26)

- The video always reads main RAM. The extra 20K is CPU RAM at
  `&3000`-`&7FFF` when RAMSEL.SHEN is set, and ROMSEL bit 7 (MEMSEL)
  switches the CPU back to main RAM (the screen). **V**
  On the Integra-B `&FE34` is RAMSEL, not ACCCON: never let B+ code write
  it. **V**
- Source: IBOS 1.26 source at github.com/kgl2001/IntegraB-OS (`IBOS.asm`,
  which rebuilds byte-for-byte), and the Integra-B User Guide.

- IBOS has MEMSEL set in the OS idle loop, so in Beebium a CPU-address peek
  of `&3000`-`&7FFF` on the Integra-B depends on where the machine stopped.
  Tests read the screen and user RAM through the `main_ram` (screen) and
  `shadow_ram` (user RAM) regions instead. **V** (beebium-stratagem)

### Detection

- IBOS answers OSBYTE `&49` with X=`&FF` by returning X=`&49`; use this
  (`PROBE` does). Its ROM title varies between versions. **V**
- IBOS takes over OSBYTE `&00`: it returns 2 (as a B+) in the default
  OSMODE 4, and otherwise the OSMODE number. **V**

### Loading and memory

- With SHEN set, DFS 2.26 OSFILE loads to `&3000`-`&7FFF` land in the extra
  20K, as on the B+ they land in main RAM: either way, in user RAM rather
  than on the screen. **V** MMFS and ANFS should behave the same. **U**
- HIMEM (OSBYTE `&84`/`&85`) is `&8000` in shadow modes. PAGE is `&1900`
  with DFS 2.26; IBOS adds nothing. **V**
- Shadow needs OSMODE 1 or higher; the default is OSMODE 4. **D/V** If
  `*SHX` is on (default off), changing between shadow and non-shadow modes
  swaps the two 20K copies. **D/V**

### Paging protocol

- MOS 1.20 saves and restores the whole of `&F4`, and IBOS's vector stub
  (`&0880`-`&08BF`) restores the caller's whole `&F4` to ROMSEL on exit, so
  MEMSEL and PRVEN in `&F4` survive interrupts and OS calls. **V**
- To reach the screen: `SEI : LDA &F4 : ORA #&80 : STA &F4 : STA &FE30 :
  CLI`, the reverse to leave it, keeping the bank (bits 0-3) and bit 6.
  Write `&F4` before `&FE30`, or do both inside SEI/CLI. **V**
- A BRK (error) pages in the language ROM and clears MEMSEL: as on the B+,
  raise errors only from code that doesn't depend on it. **V**
- Alternatively switch SHEN: OSBYTE `&6C` (X=1 screen, X=0 extra RAM), or
  directly with `&037F` (RAMID, the RAM copy) and `&FE34` together. BREAK
  sets SHEN again from the last screen mode. **D/V**

### IBOS workspace

- Private RAM `&8000`-`&83FF` holds IBOS's buffers, settings and
  sideways RAM lists; `&9000`-`&AFFF` is the 8K printer buffer by default
  (moved with `*BUFFER`). `&8400`-`&8FFF` is not referenced by IBOS, but
  there is no documented way to claim private RAM. **V/D/U**
- Main RAM: `&0880`-`&08BF` vector stub, `&037F` RAMID, `&03A5` mode-change
  state, `&0380`-`&03D8` borrowed temporarily, zero page `&A8`-`&AF`
  (saved and restored) and `&BC`/`&BD`. **V**
- IBOS hooks BYTEV, WORDV, WRCHV, RDCHV, INSV, REMV and CNPV (not via
  extended vectors). **V**

### Sideways RAM

- OSBYTE `&44` returns a bitmask of the W-Z banks (bit 0 = W) that are RAM,
  writable, and empty or `*SRDATA`; with the default `*SRSET` mapping W-Z
  are banks 4-7. It returned `&0F` on the default machine. **V**
- OSWORD `&42`/`&43` are supported with B+/Master semantics; there is no
  allocate or free call. **V**
- Write protection is by hardware switches on the V1 board; without the
  (discontinued) switch assembly the RAM is writable. **D**

## Tube (second processor)

- Beebium attaches a parasite with the server option `--tube-65c02` (3 MHz,
  client ROM 1.10, about 2.9 MHz in effect) or `--tube-65c102` (4 MHz,
  client 1.20), added to a preset's extensions. Tests reach it with
  `bbc.connect_coprocessor()`; its debugger has `run_to`, `measure` and
  breakpoints, but the parasite advances only while the host runs.
  `bbc.tube.status` fills in only `enabled` (#205). **V**
- The host side of the Tube comes from DFS 2.26 on both targets. **V**
- B+128K: the Tube is on at boot (`Acorn TUBE 6502 64K`). **V**
- Integra-B: IBOS keeps TUBE/NOTUBE in bit 0 of user register `&0F`, and
  its default (`&2D`) leaves the Tube off, so the host runs BASIC.
  `*CONFIGURE TUBE` (checked with `*STATUS TUBE`) then Ctrl-Break
  (`keyboard.ctrl_break()`) or power-on turns it on, as does `*TUBE ON`
  at once. From Beebium 0.12.0 (#203) an Integra-B launched with a second
  processor starts with TUBE configured. **V** (in Beebium)
- Display: the B+ video reads main or shadow RAM according to `&FE34`
  bit 7, at every character fetch, so the displayed screen can be swapped
  between them. The Integra-B video always reads main RAM, so there it
  cannot. CRTC R12/R13 take effect from the next frame. **V** (Beebium
  source)
- Sources: `docs/reference/tube/` and beebium-stratagem (2026-10-19).
