\ Memory layout shared by every part of the game. See docs/architecture.md.

LOW_START    = &1900            \ Low RAM, always visible (OSHWM with DFS)
LOW_END      = &3000
USER_START   = &3000            \ User RAM: main game code and data
USER_END     = &8000
LOAD_BUFFER  = &3000            \ Where bank images are loaded before copying
SCREEN_START = &4000            \ 16K screen, shared addresses with user RAM
SCREEN_END   = &8000

RENDER_START = &8000            \ Render region: graphics...
RENDER_CODE  = &A008            \ ... and code, clear of &A000 (B+ PC rule)
RENDER_END   = &AFF8            \ ... and clear of &B000
RENDER_REGION_END = &B000
BANK_START   = &8000
BANK_END     = &C000

\ Screen geometry: 64 columns of 8-byte cells by 32 rows, of which
\ VIEW_ROWS are displayed (see build/generated/camera.asm)
ROW_BYTES        = 512
CELL_BYTES       = 8
TILE_BYTES       = 64
TILE_CACHE_SIZE  = 32           \ The tile cache is TILE_CACHE_SIZE square

\ CRTC
CRTC_ADDRESS = &FE00
CRTC_DATA    = &FE01
SYSTEM_VIA_B = &FE40            \ Addressable latch (hardware scroll wrap size)
SYSTEM_VIA_DDRA = &FE43         \ Port A's direction: the keyboard, the sound chip
SYSTEM_VIA_A_NO_HANDSHAKE = &FE4F
