\ Machine identification and sideways RAM discovery.

MACHINE_MODEL_B   = 0           \ Values of zp_machine
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS    = 2
MACHINE_MASTER    = 3
BOOT_READY = &FF                \ zp_boot_status once a program is ready (the
                                \ tests wait for it)
BOOT_TITLE = &01                \ STRAT's, while it shows the title screen...
BOOT_LOADING = &02              \ ... while it loads the game...
BOOT_LOADED = &03               \ ... and once loaded, waiting for SPACE

\ Set zp_machine by looking for IBOS, then from the MOS version. IBOS must
\ be checked first: it makes OSBYTE &00 report 2, as on a B+.
.detect_machine
{
    JSR find_ibos
    BCC not_integra_b
    LDA #MACHINE_INTEGRA_B
    BNE done
.not_integra_b
    LDA #&00
    LDX #&01
    JSR OSBYTE
    CPX #OS_VERSION_2_00
    BEQ b_plus
    BCS master
    LDA #MACHINE_MODEL_B
    BEQ done
.b_plus
    LDA #MACHINE_B_PLUS
    BNE done
.master
    LDA #MACHINE_MASTER
.done
    STA zp_machine
    RTS
}

\ Return carry set if IBOS is present: it answers OSBYTE &49 with X=&FF by
\ returning X=&49. Its ROM title varies between versions, so is not used.
.find_ibos
{
    LDA #&49
    LDX #&FF
    LDY #&00
    JSR OSBYTE
    CPX #&49
    BEQ found
    CLC
    RTS
.found
    SEC
    RTS
}

\ Find writable sideways RAM in slots the MOS reports as empty, so that RAM
\ already holding a ROM image (such as a filing system) is left alone.
\ Lists them in ram_banks, highest first. Writing the slot number to ROMSEL
\ also clears the B+ ANDY and Integra-B PRVEN/MEMSEL bits, so &8000 is the
\ sideways bank itself.
.find_ram_banks
{
    LDA #0
    STA ram_bank_count
    LDX #15
.slot_loop
    LDA ROM_TYPE_TABLE,X
    BNE next_slot
    SEI
    STX ROMSEL
    LDA &8000
    EOR #&FF
    STA &8000
    CMP &8000
    PHP
    EOR #&FF
    STA &8000                   \ Restore the original byte
    LDA ROMSEL_COPY
    STA ROMSEL
    CLI
    PLP
    BNE next_slot
    TXA
    LDY ram_bank_count
    STA ram_banks,Y
    INC ram_bank_count
.next_slot
    DEX
    BPL slot_loop
    RTS
}

.ram_bank_count     SKIP 1
.ram_banks          SKIP 16
