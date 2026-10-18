\ PROBE: identify the machine and find usable sideways RAM banks.
\
\ Leaves its findings in zp_machine, ram_bank_count and ram_banks, prints a
\ summary, then sets zp_boot_status to BOOT_READY and idles.

INCLUDE "asm/os.asm"
INCLUDE "asm/zeropage.asm"

ORG &2000
GUARD &3000

.probe_start
{
    LDA #0
    STA zp_boot_status
    JSR detect_machine
    JSR find_ram_banks
    JSR print_report
    LDA #BOOT_READY
    STA zp_boot_status
.*idle
    JMP idle
}

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
.model_b
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
\ Writing the slot number to ROMSEL also clears the B+ ANDY and Integra-B
\ PRVEN/MEMSEL bits, so &8000 is the sideways bank itself.
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

.print_report
{
    LDA #LO(machine_heading)
    LDY #HI(machine_heading)
    JSR print_string
    LDX zp_machine
    LDA machine_names_low,X
    LDY machine_names_high,X
    JSR print_string
    JSR OSNEWL
    LDA #LO(ram_heading)
    LDY #HI(ram_heading)
    JSR print_string
    LDX #0
.bank_loop
    CPX ram_bank_count
    BEQ banks_done
    LDA #' '
    JSR OSWRCH
    LDA ram_banks,X
    JSR print_decimal
    INX
    BNE bank_loop
.banks_done
    JMP OSNEWL
}

\ Print the zero-terminated string at YA.
.print_string
{
    STA zp_ptr
    STY zp_ptr + 1
    LDY #0
.loop
    LDA (zp_ptr),Y
    BEQ done
    JSR OSASCI
    INY
    BNE loop
.done
    RTS
}

\ Print A (0-99) in decimal. Preserves X.
.print_decimal
{
    LDY #'0' - 1
    SEC
.tens_loop
    INY
    SBC #10
    BCS tens_loop
    ADC #10 + '0'
    PHA
    CPY #'0'
    BEQ units
    TYA
    JSR OSWRCH
.units
    PLA
    JMP OSWRCH
}

.machine_heading    EQUS "Machine:", 0
.ram_heading        EQUS "Sideways RAM:", 0
.name_model_b       EQUS " BBC Model B", 0
.name_integra_b     EQUS " BBC Model B with Integra-B", 0
.name_b_plus        EQUS " BBC B+", 0
.name_master        EQUS " BBC Master", 0
.machine_names_low
    EQUB LO(name_model_b), LO(name_integra_b), LO(name_b_plus), LO(name_master)
.machine_names_high
    EQUB HI(name_model_b), HI(name_integra_b), HI(name_b_plus), HI(name_master)

.ram_bank_count     SKIP 1
.ram_banks          SKIP 16

.probe_end

SAVE "PROBE", probe_start, probe_end
