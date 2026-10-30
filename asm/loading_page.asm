\ The loading page (tools/stratagem/loading_page.py, in MUSIC): a MODE 7
\ page drawn through the VDU drivers, then animated from the vertical sync
\ event (animate, called by music_event in STRAT). Drips form at the
\ stalactite's tip, fall, and fill the pool a sixel each, as the game
\ loads: the pool follows an estimate of the bytes loaded, LOAD_RATE a
\ frame but never past the end of the file being loaded, caught up as each
\ file is done.
\
\ The page is MODE 7, not shadowed: its screen is main RAM at &7C00, which
\ any code can write, and user RAM is main RAM below it (GAME_BUFFER ends
\ there). In a shadow mode the Integra-B's screen is reached only with
\ MEMSEL, and an NMI of the filing system's taken meanwhile would load into
\ the screen rather than user RAM. But its user RAM in a shadow mode is
\ the shadow, where MUSIC was loaded under the title: so it is copied to
\ main RAM first (the palette black meanwhile). And there the game's
\ shadow MODE 2 clears main RAM, so MAIN waits in a bank of the store.

LOAD_RATE = 140                 \ Bytes a frame: DFS loads about 7K a second
LOADING_FILES = 6               \ RENDER, PWORLD, PLIGHT, PGAME, MAIN, MBANK
DRIPS = 6                       \ Falling at once, at most
DRIP_FORMING = 4                \ Frames a drip hangs at the tip
DRIP_SPACING = 4                \ Frames between drips, at least
DRIP_GRAVITY = 54               \ Sixels a frame a frame, in 256ths
IDLE_SPACING = 48               \ Frames between drips once the pool is full
MUSIC_PAGES = 32                \ MUSIC's, at most, for the Integra-B's copy

\ Write the bytes from from_address up to to_address to the VDU drivers.
MACRO WRITE_RANGE from_address, to_address
    LDA #LO(from_address)
    STA zp_ptr
    LDA #HI(from_address)
    STA zp_ptr + 1
    LDA #LO(to_address)
    STA print_end
    LDA #HI(to_address)
    STA print_end + 1
    JSR print_range
ENDMACRO

INCLUDE "build/generated/loading_page.asm"

.loading_variables
.loading_shown      SKIP 1      \ Non-zero once the page is drawn
.print_end          SKIP 2
.file_length_low    SKIP LOADING_FILES
.file_length_high   SKIP LOADING_FILES
.sixel_bytes        SKIP 2      \ Bytes loaded a sixel of the pool stands for
.load_cap           SKIP 2      \ The end of the file loading, in the total
.load_estimate      SKIP 2      \ Bytes loaded, as far as we can tell
.next_sixel_at      SKIP 2      \ The estimate at which the next sixel is owed
.pool_allowed       SKIP 1      \ Sixels of water owed, so far...
.pool_released      SKIP 1      \ ... drips let go for them...
.pool_filled        SKIP 1      \ ... and landed
.release_wait       SKIP 1      \ Frames until the next drip may go
.drip_phase         SKIP DRIPS  \ 0 none; 1 falling; more, forming
.drip_y_low         SKIP DRIPS  \ Its y, in sixels (8.8)
.drip_y_high        SKIP DRIPS
.drip_v_low         SKIP DRIPS  \ Its speed, sixels a frame (8.8)
.drip_v_high        SKIP DRIPS
.drip_bits          SKIP DRIP_CELLS \ The drips' sixels in each drip cell...
.drip_bits_shown    SKIP DRIP_CELLS \ ... and as shown
.loading_variables_end

\ Write the bytes from (zp_ptr) up to print_end to the VDU drivers.
.print_range
{
    LDY #0
.loop
    LDA zp_ptr
    CMP print_end
    BNE more
    LDA zp_ptr + 1
    CMP print_end + 1
    BEQ done
.more
    LDA (zp_ptr),Y
    JSR OSWRCH
    INC zp_ptr
    BNE loop
    INC zp_ptr + 1
    BNE loop
.done
    RTS
}

\ Ready the page: its state cleared, MUSIC in main RAM, and the screen
\ MODE 7, blank. The music ticks meanwhile, from the event: on the
\ Integra-B, all of MUSIC is copied as it plays, then the pages of the
\ player's state again, between two ticks, and from then the event's
\ ticks are of main RAM (music_romsel: MEMSEL), until MODE 7 makes it user
\ RAM.
.prepare_loading
{
    LDA #0
    LDX #loading_variables_end - loading_variables - 1
.clear
    STA loading_variables,X
    DEX
    BPL clear
    LDA zp_machine
    CMP #MACHINE_INTEGRA_B
    BNE mode
    JSR palette_black           \ MUSIC (this) to main RAM, from the shadow,
    LDX #MUSIC_PAGES            \ through a bank of the store
    LDY #HI(music_start)
    JSR copy_music
    SEI
    LDX #HI(music_state_end - 1) - HI(music_state) + 1
    LDY #HI(music_state)
    JSR copy_music
    LDA #&80
    STA music_romsel
    CLI
.mode
    LDA #22
    JSR OSWRCH
    LDA #7
    JSR OSWRCH
    LDX #9
.cursor_loop
    LDA cursor_off,X
    JSR OSWRCH
    DEX
    BPL cursor_loop
    RTS
.cursor_off
    EQUB 0, 0, 0, 0, 0, 0, 0, 0, 1, 23     \ VDU 23, 1, 0;0;0;0; backwards
}

\ Copy X pages of MUSIC from page Y in user RAM (the shadow) to main RAM,
\ through a bank of the store, on the Integra-B.
.copy_music
{
    STX pages
    STY page
    LDA host_store_banks
    JSR copy_to_paged
    LDA page
    STA copy_target + 2
    LDA host_store_banks
    ORA #&80                    \ MEMSEL: main RAM
    LDX pages
    LDY #HI(BANK_START)
    JMP copy_pages
.pages
    SKIP 1
.page
    SKIP 1
}

\ Draw the page, measure the files for the pool, the music ticking meanwhile
\ (the filing system may spin a disc up), then start its animation: not
\ before, or with no sixel_bytes yet the pool would be owed in full.
.show_loading
    WRITE_RANGE loading_page_vdu, loading_page_vdu_end
    JSR measure_files
    DEC loading_shown
    RTS

\ The status line, once the game is loaded; and the pool may fill.
.show_loaded
    LDA #POOL_SIXELS
    STA pool_allowed
    WRITE_RANGE status_loaded, status_loaded_end
    RTS

\ Each file's length (OSFILE 5), and the bytes a sixel of the pool stands
\ for: the total's POOL_SIXELSth, rounded down, so all of them are reached.
.measure_files
{
    LDA #0
    STA total
    STA total + 1
    LDX #LOADING_FILES - 1
    LDA ram_bank_count          \ (MBANK only if there's a bank for it)
    CMP #MUSIC_BANK_INDEX + 1
    BCS file
    DEX
.file
    STX index
    LDA loading_names_low,X
    STA osfile_block
    LDA loading_names_high,X
    STA osfile_block + 1
    LDA #5
    LDX #LO(osfile_block)
    LDY #HI(osfile_block)
    JSR OSFILE
    LDX index
    LDA osfile_block + 10
    STA file_length_low,X
    CLC
    ADC total
    STA total
    LDA osfile_block + 11
    STA file_length_high,X
    ADC total + 1
    STA total + 1
    DEX
    BPL file
.divide
    LDA total
    SEC
    SBC #POOL_SIXELS
    TAX
    LDA total + 1
    SBC #0
    BCC divided
    STX total
    STA total + 1
    INC sixel_bytes
    BNE divide
    INC sixel_bytes + 1
    BNE divide
.divided
    LDA sixel_bytes
    STA next_sixel_at
    LDA sixel_bytes + 1
    STA next_sixel_at + 1
    RTS
.index
    SKIP 1
.total
    SKIP 2
}

\ File X is loading: the estimate may run on to its end.
.file_starting
    SEI
    CLC
    LDA load_cap
    ADC file_length_low,X
    STA load_cap
    LDA load_cap + 1
    ADC file_length_high,X
    STA load_cap + 1
    CLI
    RTS

\ It has loaded: the estimate catches up.
.file_loaded
    SEI
    LDA load_cap
    STA load_estimate
    LDA load_cap + 1
    STA load_estimate + 1
    CLI
    RTS

\ A frame of the page, from music_event: main RAM paged in, zp_ptr free.
.animate
{
    LDA loading_shown
    BNE shown
    RTS
.shown
    CLC                         \ The estimate, on by LOAD_RATE, to the cap
    LDA load_estimate
    ADC #LO(LOAD_RATE)
    STA load_estimate
    LDA load_estimate + 1
    ADC #HI(LOAD_RATE)
    STA load_estimate + 1
    BCS cap
    LDA load_cap
    CMP load_estimate
    LDA load_cap + 1
    SBC load_estimate + 1
    BCS allow
.cap
    LDA load_cap
    STA load_estimate
    LDA load_cap + 1
    STA load_estimate + 1
.allow                          \ A sixel more for each sixel_bytes reached
    LDA pool_allowed
    CMP #POOL_SIXELS
    BCS release
    LDA load_estimate
    CMP next_sixel_at
    LDA load_estimate + 1
    SBC next_sixel_at + 1
    BCC release
    INC pool_allowed
    CLC
    LDA next_sixel_at
    ADC sixel_bytes
    STA next_sixel_at
    LDA next_sixel_at + 1
    ADC sixel_bytes + 1
    STA next_sixel_at + 1
    BCC allow
    LDA #POOL_SIXELS            \ (Past the top: the rest are the load's end)
    STA pool_allowed

.release                        \ A drip, if one is owed (or now and then,
    LDA release_wait            \ once the pool is full)
    BEQ owed
    DEC release_wait
    JMP fall
.owed
    LDA pool_released
    CMP pool_allowed
    BCC owed_one
    CMP #POOL_SIXELS
    BCC fall
    LDY #IDLE_SPACING
    BNE release_one
.owed_one
    LDY #DRIP_SPACING
.release_one
    LDX #DRIPS - 1
.find
    LDA drip_phase,X
    BEQ found
    DEX
    BPL find
    BMI fall                    \ (None free: it waits)
.found
    STY release_wait
    CPY #DRIP_SPACING
    BNE idle
    INC pool_released
.idle
    LDA #DRIP_FORMING + 1
    STA drip_phase,X
    LDA #DRIP_TOP
    STA drip_y_high,X
    LDA #0
    STA drip_y_low,X
    STA drip_v_low,X
    STA drip_v_high,X

.fall                           \ Each drip forms, then falls, faster
    LDX #DRIPS - 1
.drip
    LDA drip_phase,X
    BEQ next
    CMP #1
    BEQ falling
    DEC drip_phase,X
    BNE next
.falling
    CLC
    LDA drip_v_low,X
    ADC #DRIP_GRAVITY
    STA drip_v_low,X
    BCC faster
    INC drip_v_high,X
.faster
    CLC
    LDA drip_y_low,X
    ADC drip_v_low,X
    STA drip_y_low,X
    LDA drip_y_high,X
    ADC drip_v_high,X
    STA drip_y_high,X
    CMP #POOL_TOP
    BCC next
    LDA #0                      \ In the pool
    STA drip_phase,X
    JSR fill_pool
.next
    DEX
    BPL drip

    LDX #DRIP_CELLS - 1         \ Where they are now, in each drip cell
    LDA #0
.clear
    STA drip_bits,X
    DEX
    BPL clear
    LDX #DRIPS - 1
.place
    LDA drip_phase,X
    BEQ placed
    LDA drip_y_high,X
    SEC
    SBC #DRIP_TOP
    TAY
    JSR drip_sixel
    LDA drip_v_high,X           \ Falling fast: a streak
    BEQ placed
    DEY
    BMI placed
    JSR drip_sixel
.placed
    DEX
    BPL place

    LDX #DRIP_CELLS - 1         \ Write the cells that changed
.cell
    LDA drip_bits,X
    CMP drip_bits_shown,X
    BEQ same
    STA drip_bits_shown,X
    ORA #MOSAIC
    PHA
    LDA drip_cell_low,X
    STA zp_ptr
    LDA drip_cell_high,X
    STA zp_ptr + 1
    PLA
    LDY #0
    STA (zp_ptr),Y
.same
    DEX
    BPL cell
    RTS
}

\ Set the sixel at y = DRIP_TOP + Y in drip_bits. Keeps X and Y.
.drip_sixel
{
    STY sixel
    LDA drip_y_cell,Y
    TAY
    LDA drip_bits,Y
    STY cell
    LDY sixel
    ORA drip_y_bit,Y
    LDY cell
    STA drip_bits,Y
    LDY sixel
    RTS
.sixel
    SKIP 1
.cell
    SKIP 1
}

\ A sixel more water in the pool, until it is full. Keeps X.
.fill_pool
{
    LDY pool_filled
    CPY #POOL_SIXELS
    BCS full
    INC pool_filled
    LDA pool_cell_low,Y
    STA zp_ptr
    LDA pool_cell_high,Y
    STA zp_ptr + 1
    LDA pool_cell_byte,Y
    LDY #0
    STA (zp_ptr),Y
.full
    RTS
}

.loading_names_low
    EQUB LO(file_render), LO(command_world + 5), LO(command_light + 5), LO(command_game + 5)
    EQUB LO(file_main), LO(file_mbank)
.loading_names_high
    EQUB HI(file_render), HI(command_world + 5), HI(command_light + 5), HI(command_game + 5)
    EQUB HI(file_main), HI(file_mbank)
