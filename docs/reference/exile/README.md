# Exile disassembly indexes

Indexes of the Level 7 Exile disassemblies, which are kept (uncommitted) in
`docs/local/`:

| Index | Source |
|---|---|
| `enhanced-index.txt` | `docs/local/level-7-exile-enhanced-disassembly.txt` (sideways RAM version) |
| `standard-index.txt` | `docs/local/level-7-exile-standard-disassembly.txt` |
| `disk-protection-and-supervisor-index.txt` | `docs/local/level-7-exile-disk-protection-and-supervisor-disassembly.txt` |

Each index line is `address  L<line>  label  # comment`, with `##` lines for
section headings. Regenerate with:

    uv run python -m stratagem.index_disassembly docs/local/level-7-exile-enhanced-disassembly.txt docs/reference/exile/enhanced-index.txt

## Notes (enhanced version)

Areas of interest, from the disassembly's own technical notes:

- `&0d4d`-`&10cf` sprite plotting: sprites are cut from one 128x81 four-colour
  sheet (`sprite_data`, `&b3ec`), with flipping and palette translation to
  sixteen colours. Colours are split into eight for objects and eight for
  tiles.
- `&1739`-`&19ca` landscape generation: a procedural 256x256 tile world,
  overlaid with a little mapped data (`map_data`, `&afec`).
- `&1a2f`-`&1e4c` physics engine: object lists of 16 primary (on screen),
  32 secondary (remembered off screen) and tertiary (fixed to locations)
  slots.

Screen: `wipe_screen_and_start_game` (L605) clears `&4000`-`&7fff` and sets
CRTC R1 to `&40`, giving 64 character columns (128 MODE 2 pixels) by 32 rows
(256 lines) in 16K. Scrolling uses the CRTC start address
(`set_crtc_start_address`, L6108; `consider_setting_crtc_start_address`,
L6098). The palette is `palette_registers_table` (L3969), and water is
drawn by changing colour 0 mid-frame in the IRQ handler (L4087-4103).
