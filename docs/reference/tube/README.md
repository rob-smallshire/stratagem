# Tube sources

Annotated disassemblies of both ends of the Tube, from acornaeology
(<https://acornaeology.uk/>), kept locally in `~/Code/acornaeology/`. Line
numbers below are in each version's `output/*.asm`. The `beebium-stratagem`
session also knows the Tube well, from implementing it in the emulator.

| Source | Local path | Web |
|---|---|---|
| 6502 Tube client 1.10 (the parasite's OS) | `acorn-6502-tube-client/versions/tube-6502-client-1.10/output/tube-6502-client-1.10.asm` | <https://acornaeology.uk/acorn-6502-tube-client/1.10.html> |
| NFS 3.65 (contains a Tube host) | `acorn-nfs/versions/nfs-3.65/output/nfs-3.65.asm` | <https://acornaeology.uk/acorn-nfs/3.65.html> |
| ADFS 1.30 (Tube transfers from disc) | `acorn-adfs/versions/adfs-1.30/output/adfs-1.30.asm` | <https://acornaeology.uk/acorn-adfs/> |
| Master MOS (JGH's Host 3.20) | `~/Code/acorn_mos_disassembly/src/utils.s65` L6251-7029, `tubeHost_brkHandlerAndIdleLoop.s65` | |

Other references: JGH's protocol notes, <http://mdfs.net/Software/Tube/Docs/Protocol>;
6502 Second Processor Elite, <https://elite.bbcelite.com/6502sp/> (its host
extends WRCHV and WORDV inside the standard Tube host).

## Client (parasite), tube-6502-client-1.10

- L146 `reset`: copies the OS into RAM, the vectors, and the startup code.
- L263 `enter_code`, L681 `execute_code`: entering a language or code.
- OS calls over R2: L389 `oswrch_impl` (over R1), L564 `oscli_impl`,
  L724 `osbyte_impl`, L861 `osword_impl` (L1254/L1288 the block lengths),
  L1024 `osargs_impl`, L1069 `osfind_impl`, L1100 `osbget_impl`,
  L1119 `osbput_impl`, L1159 `osfile_impl`, L1207 `osgbpb_impl`.
- L1315 `interrupt_handler`: L1364 `tube_r1_interrupt` (events, escape),
  L1407 `tube_r4_interrupt` (errors from the host; transfers).
- L1460 `data_transfer_setup`: a host-initiated transfer; L1554
  `transfer_256_bytes_from_tube`; NMI handlers L1576-1664 for the
  1- and 2-byte types; L1677-1723 the address and NMI routine tables.
- L1822 `tube_ula_io_window`: the registers at `&FEF8`-`&FEFF`.
- L1881 `default_vector_table`, L1939-2104 the OS entry points.

## Host, nfs-3.65

- L413-425: the registers at `&FEE0`-`&FEE7`.
- L483 `tube_brk_handler`: errors to the parasite over R4 and R2.
- L507 `tube_main_loop`: the idle loop; L511 `tube_handle_wrch` (R1),
  L515 `tube_poll_r2`, L522 `tube_dispatch_cmd` (L903 `tube_dispatch_table`).
- L654 `tube_addr_claim`, L669 `tube_release_claim`, L703
  `tube_transfer_setup`: the `&0406` entry (claim, release, transfer).
- L767 `tube_begin`, L831 `tube_init_reloc`: installing the host code.
- Command handlers: L945 `tube_osbput`, L958 `tube_osbget`,
  L969 `tube_osrdch`, L986 `tube_osfind`, L1007 `tube_osargs`,
  L1072 `tube_oscli`, L1093 `tube_osfile`, L1122 `tube_osgbpb`,
  L1148/L1170 OSBYTE, L1194 `tube_osword`, L1248 `tube_osword_rdln`.
- L1285 `tube_send_r2`, L1298 `tube_send_r4`, L1333 `tube_send_r1`,
  L1345 `tube_read_r2`; L1315 `tube_event_handler`.
- L4640 `tube_transfer`, L4720 `tube_claim_loop`: NFS's own use.

## Host side of a filing system, adfs-1.30

- L978 `claim_tube`, L1005 `release_tube`.
- L1362-1417: starting a transfer, the delays the protocol needs, and
  256-byte read and write loops.
- L854/L882, L11842-11887: NMI-driven Tube transfers from floppy.
