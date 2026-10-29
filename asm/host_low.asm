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
.call_render_pack       RENDER_CALL render_pack
.call_render_pack_marks RENDER_CALL render_pack_marks
.call_render_pack_changed RENDER_CALL render_pack_changed

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
.zp_keys            EQUB 0      \ The second byte of input (KEY_CYCLE)
.zp_tools           EQUB 0      \ The belt key held (1 on), or 0
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
.host_item_column   SKIP ITEMS_DRAWN   \ ... at these view columns
.host_item_line     SKIP ITEMS_DRAWN   \ ... and lines
.host_item_frame    SKIP ITEMS_DRAWN   \ ... these frames
.host_items_untouched EQUB 0    \ ITEMS_UNTOUCHED if nothing is redrawn under them
.host_item_new_low  SKIP ITEMS_DRAWN   \ ... where they go on the screen
.host_item_new_high SKIP ITEMS_DRAWN
.host_items_drawn   EQUB 0      \ Items drawn, to restore...
.host_item_address_low  SKIP ITEMS_DRAWN   \ ... drawn here
.host_item_address_high SKIP ITEMS_DRAWN
.host_item_drawn_frame  SKIP ITEMS_DRAWN   \ ... these frames
.host_items_kept    EQUB 0      \ The first of them left as they are
.host_item_index    EQUB 0
.host_sprite_address EQUW 0     \ The player's sprite's, kept while items are drawn
.host_pack_count    EQUB 0      \ The pack's kinds shown (its packet's)...
.host_pack_index    EQUB 0      \ ... the hand's place among them...
.host_pack_kinds    SKIP KIND_COUNT \ ... them...
.host_pack_counts   SKIP KIND_COUNT \ ... and their counts...
.host_pack_size     EQUB 0      \ ... the grid's size...
.host_pack_grid     SKIP GRID_CELLS \ ... its cells...
.host_pack_made     EQUB 0      \ ... and what it makes (CELL_EMPTY: nothing)...
.host_pack_made_count EQUB 0    \ ... and how many...
.host_pack_belt     SKIP BELT_SLOTS \ ... the belt...
.host_pack_slot     EQUB 0      \ ... and the slot in the tool hand

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
    LDA ROMSEL_COPY
    AND #&7F
    STA zp_romsel_game
    LDA zp_romsel_render        \ The render region is ANDY on the B+, the
    LDX zp_machine              \ render bank on the Integra-B
    CPX #MACHINE_B_PLUS
    BEQ compose
    AND #&0F
.compose
    STA zp_romsel_compose       \ (ANDY on the B+; no MEMSEL on the Integra-B)

    \ The title screen, a shadow MODE 1 with interlace off, so that user
    \ RAM at &3000-&7FFF is not the screen and the picture loads beneath it.
    LDA #144
    LDX #0
    LDY #1
    JSR OSBYTE
    STX old_tv
    STY old_tv + 1
    LDX #title_vdu - vdu_strings
    LDY #title_vdu_end - vdu_strings
    JSR vdu_string
    LDA #&84                    \ HIMEM is &8000 only in a shadow mode
    JSR OSBYTE
    CPY #&80
    BEQ shadow_ok
    LDX #LO(message_shadow)
    LDY #HI(message_shadow)
    JMP fail
.shadow_ok
    JSR show_title
    LDA #BOOT_TITLE
    STA zp_boot_status
    JSR wait_for_space

    \ The loading page, a MODE 7 with the keys, and the music on,
    \ ticked from the vertical sync event, while the game loads beneath it
    \ and until SPACE is pressed again. RENDER and MAIN are loaded clear of
    \ MUSIC, and MAIN copied into place, from a bank, once the music has
    \ stopped and the game's screen is selected (asm/loading_page.asm).
    JSR loading_screen_off
    LDA #144
    LDX old_tv
    LDY old_tv + 1
    JSR OSBYTE
    JSR show_loading
    JSR music_event_on
    LDA #BOOT_LOADING
    STA zp_boot_status

    LDX #0                      \ (Each file's number, as loading_names has it)
    JSR file_starting
    LDX #LO(file_render)
    LDY #HI(file_render)
    JSR load_game_file
    LDA zp_romsel_compose
    LDX #RENDER_PAGES
    LDY #HI(GAME_BUFFER)
    JSR copy_to_paged
    JSR file_loaded

    LDX #1                      \ The parasite's files, into the parasite
    JSR file_starting
    LDX #LO(command_world)
    LDY #HI(command_world)
    JSR OSCLI
    JSR file_loaded
    LDX #2
    JSR file_starting
    LDX #LO(command_light)
    LDY #HI(command_light)
    JSR OSCLI
    JSR file_loaded
    LDX #3
    JSR file_starting
    LDX #LO(command_game)
    LDY #HI(command_game)
    JSR OSCLI
    JSR file_loaded

    LDA zp_romsel_game          \ The host's game code, in program RAM
    SELECT_ROMSEL
    LDX #4
    JSR file_starting
    LDX #LO(file_main)
    LDY #HI(file_main)
    JSR load_game_file
    LDA host_store_banks        \ Kept in the store's bank, empty until the
    LDX #MAIN_PAGES             \ game starts: the Integra-B's shadow MODE 2
    LDY #HI(GAME_BUFFER)        \ clears main RAM
    JSR copy_to_paged
    JSR file_loaded
    JSR show_loaded
    LDA #BOOT_LOADED
    STA zp_boot_status
    JSR wait_to_start

    JSR music_event_off
    JSR music_silence
    LDX #vdu_setup - vdu_strings    \ The game's screen, a shadow MODE 2
    LDY #vdu_setup_end - vdu_strings
    JSR vdu_string
    LDA #HI(USER_START)         \ MAIN into place, over MUSIC
    STA copy_target + 2
    LDA host_store_banks
    LDX #MAIN_PAGES
    LDY #HI(BANK_START)
    JSR copy_pages

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

    LDA #BOOT_READY
    STA zp_boot_status
    JSR host_claim              \ Run the game in the parasite, as *RUN
    LDA #TUBE_EXECUTE           \ would (never returning: the Tube host's
    LDX #LO(pgame_address)      \ idle loop serves the parasite from here
    LDY #HI(pgame_address)      \ on)
    JMP TUBE_ENTRY

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

\ Write vdu_strings from offset X up to offset Y to the VDU drivers.
.vdu_string
{
    STY end
.loop
    LDA vdu_strings,X
    JSR OSWRCH
    INX
    CPX end
    BNE loop
    RTS
.end
    SKIP 1
}

\ Load the cover art (LSCREEN, the title screen's 20K) into user RAM, copy
\ it to the screen, load the music (MUSIC) in its place, and start toggling
\ the flash bit every line (asm/loading_screen.asm). Only code at RENDER_CODE sees the screen on the
\ B+ (with ANDY paged in, as on the Integra-B MEMSEL with the render bank),
\ so a small copier is put there, and the picture goes through the render
\ region below it, BOUNCE_PAGES at a time. RENDER, loaded later,
\ overwrites both.
BOUNCE_PAGES = 16
ASSERT (SCREEN_END - LOAD_BUFFER) DIV 256 MOD BOUNCE_PAGES = 0
ASSERT BANK_START + BOUNCE_PAGES * 256 <= RENDER_CODE
.show_title
{
    JSR palette_black           \ All black while it loads
    LDX #LO(file_screen)
    LDY #HI(file_screen)
    JSR load_file

    LDA zp_romsel_compose
    SELECT_ROMSEL
    LDX #screen_copier_end - screen_copier - 1
.copier_loop
    LDA screen_copier,X
    STA RENDER_CODE,X
    DEX
    BPL copier_loop
    LDA zp_romsel_game
    SELECT_ROMSEL

    LDA #HI(LOAD_BUFFER)
    STA page
.chunk
    LDA zp_romsel_compose       \ User RAM to the render region...
    LDX #BOUNCE_PAGES
    LDY page
    JSR copy_to_paged
    LDA #0
    STA zp_temp
    STA zp_ptr
    LDA #HI(BANK_START)
    STA zp_temp + 1
    LDA page
    STA zp_ptr + 1
    LDA zp_romsel_render        \ ... and from there to the screen
    SELECT_ROMSEL
    LDX #BOUNCE_PAGES
    JSR RENDER_CODE
    LDA zp_romsel_game
    SELECT_ROMSEL
    LDA page
    CLC
    ADC #BOUNCE_PAGES
    STA page
    CMP #HI(SCREEN_END)
    BNE chunk

    LDX #LO(file_music)         \ The music, where the picture was
    LDY #HI(file_music)
    JSR load_file
    LDA #LO(score_overture)
    STA zp_score
    LDA #HI(score_overture)
    STA zp_score + 1
    JSR music_init
    JMP loading_screen_on
.page
    SKIP 1
}

\ Play the music until SPACE is pressed, reading the keyboard itself: the
\ OS doesn't, with the System VIA's interrupts off. The music ticks at each
\ vertical sync, whose flag the System VIA still sets.
.wait_for_space
{
    LDA #3                      \ Stop its scanning
    STA SYSTEM_VIA_B
    LDA #&7F                    \ Port A: a key number out, its state in
    STA SYSTEM_VIA_DDRA         \ (bit 7)
.wait
    LDA #VIA_CA1                \ A vertical sync since the last tick?
    BIT SYSTEM_VIA_IFR
    BEQ key
    STA SYSTEM_VIA_IFR          \ (clears it)
    JSR music_tick
.key
    LDA #KEY_SPACE
    STA SYSTEM_VIA_A_NO_HANDSHAKE
    LDA SYSTEM_VIA_A_NO_HANDSHAKE
    BPL wait
    LDA #&0B                    \ Let it scan again
    STA SYSTEM_VIA_B
    RTS
}

\ Copy X pages from (zp_temp) to (zp_ptr). Copied to RENDER_CODE and run
\ there, so position-independent.
.screen_copier
{
    LDY #0
.loop
    LDA (zp_temp),Y
    STA (zp_ptr),Y
    INY
    BNE loop
    INC zp_temp + 1
    INC zp_ptr + 1
    DEX
    BNE loop
    RTS
}
.screen_copier_end

\ Load the file named at YX to LOAD_BUFFER (load_file) or GAME_BUFFER
\ (load_game_file) in the host. OSFILE writes the file's catalogue
\ information back into its control block, so the block is set up afresh
\ each time.
.load_game_file
    LDA #HI(GAME_BUFFER)
    BNE load_file_at
.load_file
    LDA #HI(LOAD_BUFFER)
.load_file_at
{
    STX osfile_block
    STY osfile_block + 1
    STA osfile_block + 3
    LDA #0
    STA osfile_block + 2
    STA osfile_block + 6        \ Load to the address given, not the file's
    LDA #&FF                    \ In the I/O processor
    STA osfile_block + 4
    STA osfile_block + 5
    LDX #LO(osfile_block)
    LDY #HI(osfile_block)
    JMP OSFILE
}

\ Copy X pages from page Y to &8000 (copy_to_paged), or to the page at
\ copy_target + 2 (copy_pages), with ROMSEL value A paged in.
.copy_to_paged
    PHA
    LDA #HI(BANK_START)
    STA copy_target + 2
    PLA
.copy_pages
{
    STY source + 2
    PHA
    LDA ROMSEL_COPY
    STA saved_romsel
    PLA
    SELECT_ROMSEL
    LDY #0
.loop
.source
    LDA &FF00,Y
.*copy_target
    STA &FF00,Y
    INY
    BNE loop
    INC source + 2
    INC copy_target + 2
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
.old_tv
    SKIP 2                      \ *TV's settings before the title screen

.vdu_strings
.title_vdu
    EQUB 22, 128 + 1            \ Shadow MODE 1
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
.title_vdu_end

.vdu_setup
    EQUB 22, 128 + 2            \ Shadow MODE 2
    EQUB 23, 1, 0, 0, 0, 0, 0, 0, 0, 0     \ Cursor off
    FOR logical, 8, 15
        EQUB 19, logical, logical - 8, 0, 0, 0  \ Steady colours, not flashing
    NEXT
.vdu_setup_end
ASSERT vdu_setup_end - vdu_strings < 256

.file_screen    EQUS "LSCREEN", 13
.file_render    EQUS "RENDER", 13
.file_music     EQUS "MUSIC", 13
.file_main      EQUS "MAIN", 13
.command_world  EQUS "LOAD PWORLD", 13
.command_light  EQUS "LOAD PLIGHT", 13
.command_game   EQUS "LOAD PGAME", 13
.pgame_address  EQUD PGAME_START

\ The vertical sync event, while the game loads: a tick of the music and a
\ frame of the loading page (MUSIC), with the zero page they share with the
\ loader kept, JIM's page put back, and ROMSEL's bit 7 clear for them,
\ whatever the loader has paged in. Here, outside user RAM, so that it
\ runs whatever is paged in.
.music_event
{
    CMP #EVENT_VSYNC
    BNE not_ours
    PHA
    TXA
    PHA
    TYA
    PHA
    LDA zp_ptr
    PHA
    LDA zp_ptr + 1
    PHA
    LDA JIM_COPY
    PHA
    LDA ROMSEL_COPY
    PHA
    AND #&7F
    SELECT_ROMSEL
    JSR music_tick
    JSR animate
    PLA
    SELECT_ROMSEL
    PLA
    STA JIM_COPY
    STA JIM_PAGE
    PLA
    STA zp_ptr + 1
    PLA
    STA zp_ptr
    PLA
    TAY
    PLA
    TAX
    PLA
.not_ours
    JMP (music_old_evntv)
}

.music_old_evntv    EQUW 0

\ Every logical colour black.
.palette_black
{
    LDX #15
.loop
    TXA
    ASL A
    ASL A
    ASL A
    ASL A
    ORA #7                      \ Physical colour 0, as the ULA wants it
    STA ULA_PALETTE
    DEX
    BPL loop
    RTS
}
ASSERT LO(music_old_evntv) <> &FF     \ JMP (indirect) on the NMOS 6502

.message_tube       EQUS "Stratagem needs a 6502 second processor", 13, 0
.message_machine    EQUS "Stratagem needs a BBC B+ 128K or an Integra-B", 13, 0
.message_banks      EQUS "Stratagem needs 48K of free sideways RAM", 13, 0
.message_shadow     EQUS "Stratagem needs shadow RAM", 13, 0

INCLUDE "asm/machine.asm"
INCLUDE "asm/loading_screen.asm"

.strat_end

\ The tile cache: the tiles around the view, which the parasite sends.
ALIGN &100
.tile_cache         SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
.tile_cache_shapes  SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE
.tile_cache_light   SKIP TILE_CACHE_SIZE * TILE_CACHE_SIZE

SAVE "STRAT", strat_start, strat_end, strat_start + HOST_ADDRESS, strat_start + HOST_ADDRESS
