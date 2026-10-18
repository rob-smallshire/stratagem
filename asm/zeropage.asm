\ Zero page allocation.
\
\ The OS stays resident, so we use only &00-&8F. Variables are declared
\ with ORG/SKIP rather than as constants so that beebasm exports them as
\ labels, which the tests look up by name.

BOOT_READY = &FF                \ zp_boot_status once initialisation is done

ORG &70
.zp_boot_status     SKIP 1      \ Zero while starting, BOOT_READY when ready
.zp_machine         SKIP 1      \ One of the MACHINE_* constants
.zp_ptr             SKIP 2      \ General purpose pointer

\ Values of zp_machine
MACHINE_MODEL_B   = 0
MACHINE_INTEGRA_B = 1
MACHINE_B_PLUS    = 2
MACHINE_MASTER    = 3
