\ Acorn MOS entry points, vectors and hardware registers.

OSWRCH = &FFEE
OSASCI = &FFE3
OSNEWL = &FFE7
OSBYTE = &FFF4
OSWORD = &FFF1
OSFILE = &FFDD
OSCLI  = &FFF7

\ MOS workspace
ROMSEL_COPY = &F4               \ RAM copy of the paged ROM select register
ROM_TYPE_TABLE = &02A1          \ One byte per sideways slot; zero if empty
EVNTV = &0220                   \ The event vector
EVENT_VSYNC = 4

\ Hardware
ROMSEL = &FE30                  \ Paged ROM select (write only)
ACCCON_X = &04                  \ The Master's CPU sees the shadow at &3000-&7FFF
JIM_PAGE = &FCFF                \ JIM's page register: write only, a read loads it
JIM_COPY = &EE                  \ The OS's copy of it, written first
ACCCON = &FE34                  \ B+ ACCCON / Integra-B RAMSEL / Master ACCCON

\ OSBYTE &00 identifies the MOS version in X
OS_VERSION_1_20 = 1
OS_VERSION_2_00 = 2             \ BBC B+
