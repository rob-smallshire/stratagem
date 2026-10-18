\ STRAT: low RAM, always visible. The resident part holds the paging
\ trampolines and the buffers shared between the game and the renderer; the
\ loader after it runs once, at boot, and is then free for reuse.

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

\ Draw cells cell_first to cell_end - 1 of the cell list (see render_cells).
.call_render_cells
{
    LDA zp_romsel_render
    SELECT_ROMSEL
    JSR render_cells
    LDA zp_romsel_game
    SELECT_ROMSEL
    RTS
}

\ Exclusive-OR the focus marker onto the screen at zp_marker_address.
.call_render_marker
{
    LDA zp_romsel_render
    SELECT_ROMSEL
    JSR render_marker
    LDA zp_romsel_game
    SELECT_ROMSEL
    RTS
}

\ Clear the screen.
.call_render_clear
{
    LDA zp_romsel_render
    SELECT_ROMSEL
    JSR render_clear
    LDA zp_romsel_game
    SELECT_ROMSEL
    RTS
}

\ Return in A the tile at world (X, Y). Preserves X and Y.
.call_tile_at
{
    LDA zp_bank_world
    SELECT_ROMSEL
    JSR tile_at
    PHA
    LDA zp_romsel_game
    SELECT_ROMSEL
    PLA
    RTS
}

\ The cell list, shared by the game, which fills it, and the renderer: the
\ graphics address of each cell, and where to draw them: from cell_base,
\ each cell_step bytes after the last.
.cell_source_low    SKIP MAX_CELLS
.cell_source_high   SKIP MAX_CELLS
.cell_base          SKIP 2
.cell_step          SKIP 2
.cell_first         SKIP 1
.cell_end           SKIP 1

\ ---------------------------------------------------------------------------
\ Loader

.loader
{
    LDA #0
    STA zp_boot_status
    LDA #&77                    \ Close the !BOOT EXEC file
    JSR OSBYTE
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
    CMP #3
    BCS banks_ok
    LDX #LO(message_banks)
    LDY #HI(message_banks)
    JMP fail
.banks_ok
    \ The three highest free banks: render, world and game.
    LDA ram_banks
    ORA #&80
    STA zp_romsel_render
    LDA ram_banks + 1
    STA zp_bank_world
    LDA ram_banks + 2
    STA zp_romsel_game

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
    LDX #LO(file_render)
    LDY #HI(file_render)
    JSR load_file
    LDA zp_romsel_render
    LDX zp_machine
    CPX #MACHINE_B_PLUS
    BEQ copy_render
    AND #&0F
.copy_render
    LDX #HI(RENDER_REGION_END - RENDER_START)
    JSR copy_to_paged

    LDX #LO(file_world)
    LDY #HI(file_world)
    JSR load_file
    LDA zp_bank_world
    LDX #HI(BANK_END - BANK_START)
    JSR copy_to_paged

    LDA zp_romsel_game
    SELECT_ROMSEL
    LDX #LO(file_main)
    LDY #HI(file_main)
    JSR load_file
    JMP main_start

\ Print the message at YX and stop. Returning to BASIC is not safe, as its
\ zero page has been overwritten.
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

\ Load the file named at YX to LOAD_BUFFER (which is also USER_START, where
\ MAIN runs). OSFILE writes the file's catalogue information back into its
\ control block, so the block is set up afresh each time.
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
.file_world     EQUS "WORLD", 13
.file_main      EQUS "MAIN", 13

.message_machine    EQUS "Stratagem needs a BBC B+ 128K or an Integra-B", 13, 0
.message_banks      EQUS "Stratagem needs 48K of free sideways RAM", 13, 0
.message_shadow     EQUS "Stratagem needs shadow RAM", 13, 0

INCLUDE "asm/machine.asm"

.strat_end

SAVE "STRAT", strat_start, strat_end
