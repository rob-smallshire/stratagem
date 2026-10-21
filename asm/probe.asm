\ PROBE: identify the machine and find usable sideways RAM banks.
\
\ Leaves its findings in zp_machine, ram_bank_count and ram_banks, prints a
\ summary, then sets zp_boot_status to BOOT_READY and idles.

INCLUDE "asm/os.asm"

ORG &70                         \ In the language's zero page
.zp_boot_status     SKIP 1      \ Zero while starting, BOOT_READY when ready
.zp_machine         SKIP 1      \ One of the MACHINE_* constants
.zp_ptr             SKIP 2

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

INCLUDE "asm/machine.asm"

.probe_end

SAVE "PROBE", probe_start, probe_end
