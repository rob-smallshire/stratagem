\ STRAT, for the Tube game: the host's low RAM, always visible. The paging
\ trampolines for the renderer, the hook on OSWRCH by which the parasite
\ asks for each frame, the host's variables, and the loader (run by !BOOT
\ on the host), which sets the host up, loads the parasite's files into the
\ parasite, and runs the game there.

ORG LOW_START
GUARD LOW_END

.strat_start
    JMP loader

\ ---------------------------------------------------------------------------
\ Resident

\ Page in ROMSEL value A, keeping the MOS's RAM copy in step first so that an
\ interrupt that restores ROMSEL from it restores this value.
MACRO SELECT_ROMSEL
    STA ROMSEL_COPY
    STA ROMSEL
ENDMACRO

MACRO RENDER_CALL routine
    LDA zp_romsel_render
    SELECT_ROMSEL
    JSR routine
    LDA zp_romsel_game
    SELECT_ROMSEL
    RTS
ENDMACRO

.call_render_row        RENDER_CALL render_row
.call_render_columns    RENDER_CALL render_columns
.call_render_sprite     RENDER_CALL render_sprite
.call_render_restore    RENDER_CALL render_restore
.call_render_clear      RENDER_CALL render_clear
.call_render_light      RENDER_CALL render_light
.call_render_items      RENDER_CALL render_items
.call_restore_items     RENDER_CALL restore_items

\ OSWRCH: a command from the parasite and its arguments (COMMAND_FRAME and
\ its buffer, or COMMAND_FETCH, a slot and an address), or an ordinary
\ character. A command runs with ROMSEL's bit 7 clear (program RAM at
\ &3000-&7FFF on the Integra-B), and ROMSEL as it was afterwards.
.host_wrch
{
    STA host_a
    STX host_x
    STY host_y
    LDX host_expect
    BNE argument
    LDX #1
    CMP #COMMAND_FRAME
    BEQ command
    LDX #3
    CMP #COMMAND_FETCH
    BEQ command
    LDX host_x
    JMP (host_old_wrchv)
.command
    STA host_command
    STX host_expect
    JMP return
.argument                       \ (The last argument goes first in host_args)
    DEX
    STA host_args,X
    STX host_expect
    BNE return
    LDA ROMSEL_COPY
    PHA
    AND #&7F
    STA zp_romsel_game
    SELECT_ROMSEL
    LDA host_command
    CMP #COMMAND_FRAME
    BNE fetch
    LDA host_args
    STA host_buffer
    JSR host_frame
    JMP done
.fetch
    LDA host_args + 2
    STA host_fetch_slot
    LDA host_args + 1
    STA host_fetch_to
    LDA host_args
    STA host_fetch_to + 1
    JSR host_fetch
    JSR host_fetched
.done
    PLA
    SELECT_ROMSEL
.return
    LDA host_a
    LDX host_x
    LDY host_y
    RTS
}

\ Claim the Tube for a transfer (waiting while another claim is held), and
\ release it.
.host_claim
{
    LDA #TUBE_CLAIM
    JSR TUBE_ENTRY
    BCC host_claim
    RTS
}

.host_release
    LDA #TUBE_RELEASE
    JMP TUBE_ENTRY

\ The host's variables (zero page is in host_zeropage.asm)
.zp_boot_status     EQUB 0      \ BOOT_READY once loaded
.zp_machine         EQUB 0
.zp_redraw          EQUB 0
.zp_input           EQUB 0
.redraw_tile        EQUB 0      \ A changed tile to redraw at the flip...
.redraw_tile_x      EQUB 0
.redraw_tile_y      EQUB 0
.target_x           EQUB 0      \ ... and while it is drawn
.target_y           EQUB 0
.host_a             EQUB 0
.host_x             EQUB 0
.host_y             EQUB 0
.host_expect        EQUB 0      \ A command's arguments still to come...
.host_command       EQUB 0      \ ... for this command
.host_args          SKIP 3      \ ... last first
.host_buffer        EQUB 0      \ The packet's buffer
.host_frames        EQUB 0      \ Packets read
.host_old_wrchv     EQUW 0
.host_flags         EQUB 0
.host_strips        EQUB 0
.host_count         EQUB 0
.host_down          EQUB 0
.host_tile_x        EQUB 0
.host_tile_y        EQUB 0
.host_transfer      EQUD 0      \ A parasite address, for a transfer
.host_frame_count   EQUB 0      \ Frames drawn (for tests)
.host_changes       EQUB 0      \ Changed tiles to redraw at the flip...
.host_change        EQUB 0
.host_change_x      SKIP CHANGES_PER_FRAME  \ ... and where
.host_change_y      SKIP CHANGES_PER_FRAME
.zp_romsel_compose  EQUB 0      \ The render bank without the screen
.host_slot_pair     SKIP SLOT_COUNT \ Each slot's pair, piece * 2 + backdrop
.host_store_banks   SKIP STORE_BANKS    \ The store's banks (host_store)
.host_store_count   EQUB 0
.host_chunk         EQUW 0      \ A chunk in the store (host_chunk_at)
.host_fetch_slot    EQUB 0      \ A chunk to copy to the parasite, or 0...
.host_fetch_to      EQUW 0      \ ... to here
.host_items         EQUB 0      \ Items to draw (the packet's)...
.host_item_column   SKIP ITEM_MAX   \ ... at these view columns
.host_item_line     SKIP ITEM_MAX   \ ... and lines
.host_item_frame    SKIP ITEM_MAX   \ ... these frames
.host_items_untouched EQUB 0    \ ITEMS_UNTOUCHED if nothing is redrawn under them
.host_item_new_low  SKIP ITEM_MAX   \ ... where they go on the screen
.host_item_new_high SKIP ITEM_MAX
.host_items_drawn   EQUB 0      \ Items drawn, to restore...
.host_item_address_low  SKIP ITEM_MAX   \ ... drawn here
.host_item_address_high SKIP ITEM_MAX
.host_item_drawn_frame  SKIP ITEM_MAX   \ ... these frames
.host_items_kept    EQUB 0      \ The first of them left as they are
.host_item_index    EQUB 0

\ ---------------------------------------------------------------------------
\ Loader

.loader
{
    LDA #0
    STA zp_boot_status
    LDA #&77                    \ Close the !BOOT EXEC file
    JSR OSBYTE
    LDA #&EA                    \ A second processor?
    LDX #0
    LDY #&FF
    JSR OSBYTE
    CPX #0
    BNE tube_ok
    LDX #LO(message_tube)
    LDY #HI(message_tube)
    JMP fail
.tube_ok
    JSR detect_machine
    LDA zp_machine
    CMP #MACHINE_INTEGRA_B
    BEQ machine_ok
    CMP #MACHINE_B_PLUS
    BEQ machine_ok
    LDX #LO(message_machine)
    LDY #HI(message_machine)
    JMP fail
.machine_ok
    JSR find_ram_banks
    LDA ram_bank_count
    CMP #1 + STORE_BANKS        \ The render bank and the store's
    BCS banks_ok
    LDX #LO(message_banks)
    LDY #HI(message_banks)
    JMP fail
.banks_ok
    LDA ram_banks               \ The render bank (the B+ uses ANDY)
    ORA #&80
    STA zp_romsel_render
    LDA ram_banks + 1           \ The store of changed chunks (host_store)
    STA host_store_banks
    LDA ram_banks + 2
    STA host_store_banks + 1

    \ A shadow MODE 2, so that user RAM at &3000-&7FFF is not the screen.
    LDX #0
.vdu_loop
    LDA vdu_setup,X
    JSR OSWRCH
    INX
    CPX #vdu_setup_end - vdu_setup
    BNE vdu_loop
    LDA #&84                    \ HIMEM is &8000 only in a shadow mode
    JSR OSBYTE
    CPY #&80
    BEQ shadow_ok
    LDX #LO(message_shadow)
    LDY #HI(message_shadow)
    JMP fail
.shadow_ok

    \ The render region is ANDY on the B+, the render bank on the Integra-B.
    LDA ROMSEL_COPY
    AND #&7F
    STA zp_romsel_game
    LDX #LO(file_render)
    LDY #HI(file_render)
    JSR load_file
    LDA zp_romsel_render
    LDX zp_machine
    CPX #MACHINE_B_PLUS
    BEQ copy_render
    AND #&0F
.copy_render
    STA zp_romsel_compose       \ (ANDY on the B+; no MEMSEL on the Integra-B)
    LDX #HI(RENDER_REGION_END - RENDER_START)
    JSR copy_to_paged

    LDA zp_romsel_game          \ The host's game code, in program RAM
    SELECT_ROMSEL
    LDX #LO(file_main)
    LDY #HI(file_main)
    JSR load_file
    JSR host_init

    SEI                         \ Hook OSWRCH
    LDA WRCHV
    STA host_old_wrchv
    LDA WRCHV + 1
    STA host_old_wrchv + 1
    LDA #LO(host_wrch)
    STA WRCHV
    LDA #HI(host_wrch)
    STA WRCHV + 1
    CLI

    LDX #LO(command_world)      \ The parasite's files, into the parasite,
    LDY #HI(command_world)      \ and run the game there (never returning)
    JSR OSCLI
    LDX #LO(command_light)
    LDY #HI(command_light)
    JSR OSCLI
    LDA #BOOT_READY
    STA zp_boot_status
    LDX #LO(command_game)
    LDY #HI(command_game)
    JMP OSCLI

\ Print the message at YX and stop.
.fail
    STX zp_ptr
    STY zp_ptr + 1
    LDY #0
.message_loop
    LDA (zp_ptr),Y
    BEQ message_done
    JSR OSASCI
    INY
    BNE message_loop
.message_done
    JMP message_done
}

\ Load the file named at YX to LOAD_BUFFER in the host. OSFILE writes the
\ file's catalogue information back into its control block, so the block is
\ set up afresh each time.
.load_file
{
    STX osfile_block
    STY osfile_block + 1
    LDA #LO(LOAD_BUFFER)
    STA osfile_block + 2
    LDA #HI(LOAD_BUFFER)
    STA osfile_block + 3
    LDA #&FF                    \ In the I/O processor
    STA osfile_block + 4
    STA osfile_block + 5
    LDA #0                      \ Load to the address given, not the file's
    STA osfile_block + 6
    LDA #&FF
    LDX #LO(osfile_block)
    LDY #HI(osfile_block)
    JMP OSFILE
}

\ Copy X pages from LOAD_BUFFER to &8000 with ROMSEL value A paged in.
.copy_to_paged
{
    PHA
    LDA ROMSEL_COPY
    STA saved_romsel
    PLA
    SELECT_ROMSEL
    LDA #HI(LOAD_BUFFER)
    STA source + 2
    LDA #HI(BANK_START)
    STA target + 2
    LDY #0
.loop
.source
    LDA &FF00,Y
.target
    STA &FF00,Y
    INY
    BNE loop
    INC source + 2
    INC target + 2
    DEX
    BNE loop
    LDA saved_romsel
    SELECT_ROMSEL
    RTS
.saved_romsel
    SKIP 1
}

.osfile_block
    SKIP 18

.vdu_setup
    EQUB 22, 128 + 2            \ Shadow MODE 2
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
    FOR logical, 8, 15
        EQUB 19, logical, logical - 8, 0, 0, 0  \ Steady colours, not flashing
    NEXT
.vdu_setup_end

.file_render    EQUS "RENDER", 13
.file_main      EQUS "MAIN", 13
.command_world  EQUS "LOAD PWORLD", 13
.command_light  EQUS "LOAD PLIGHT", 13
.command_game   EQUS "RUN PGAME", 13

.message_tube       EQUS "Stratagem needs a 6502 second processor", 13, 0
.message_machine    EQUS "Stratagem needs a BBC B+ 128K or an Integra-B", 13, 0
.message_banks      EQUS "Stratagem needs 48K of free sideways RAM", 13, 0
.message_shadow     EQUS "Stratagem needs shadow RAM", 13, 0

INCLUDE "asm/machine.asm"

.strat_end

\ The tile cache: the tiles around the view, which the parasite sends.
ALIGN &100
.tile_cache         SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
.tile_cache_shapes  SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
.tile_cache_light   SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE

SAVE "STRAT", strat_start, strat_end, strat_start + HOST_ADDRESS, strat_start + HOST_ADDRESS
