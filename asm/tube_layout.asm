\ The Tube game (docs/tube-game.md): what the host and the parasite share.
\
\ Each frame the parasite writes a packet into one of two buffers and tells
\ the host which (OSWRCH COMMAND_FRAME, then the buffer's number). The host
\ reads the packet's first part (the camera, the player, new tiles) a byte at
\ a time over the Tube, writes the input it reads into the parasite's
\ mailbox, draws, and at the flip reads the second part, the light's draw
\ list, drawing each cell as it reads it. Meanwhile the parasite works out
\ the next frame, from that input, into the other buffer.

\ The parasite's buffers
PACKET_BUFFER_0 = &0800         \ The first part, frame 0, 2, 4...
LIST_BUFFER_0 = &0D00           \ The second part
PACKET_BUFFER_1 = &1200         \ Frames 1, 3, 5...
LIST_BUFFER_1 = &1700
PACKET_BYTES = &500
LIST_BYTES = &500

\ The parasite's mailbox, written by the host: the input, then a count of
\ frames read (so the parasite knows the input has come)
MAILBOX_INPUT = &8E
MAILBOX_FRAME = &8F
MAILBOX_BYTES = 2
MAILBOX_FETCHED = &8D           \ Set by the host when it has copied a chunk
                                \ asked for at once (COMMAND_FETCH)

\ Commands, by OSWRCH from the parasite to the host
COMMAND_FRAME = 128             \ Then the buffer: 0 or 1
COMMAND_FETCH = 129             \ Then a slot of the host's store, and the
                                \ parasite address to copy its chunk to

\ The packet's first part
PACKET_FLAGS = 0                \ PACKET_REDRAW if the view must be redrawn
PACKET_PLAN_DX = 1
PACKET_PLAN_DY = 2
PACKET_CAMERA_X = 3             \ 2 bytes
PACKET_CAMERA_Y = 5             \ 2 bytes
PACKET_PLAYER_X = 7             \ 2 bytes, sixteenths of a pixel
PACKET_PLAYER_Y = 9             \ 2 bytes
PACKET_PLAYER_FRAME = 11
PACKET_STRIPS = 12              \ Then that many strips of new tiles: down
                                \ (non-zero: a column), x, y, count, then
                                \ count tiles of material, shape and light;
                                \ then a count of changed tiles (up to
                                \ CHANGES_PER_FRAME), and each: x, y,
                                \ material, shape, light
PACKET_REDRAW = &80
TILE_BYTES_SENT = 3              \ (A piece's tile may follow PIECE_COMPOSE,
PIECE_COMPOSE = &FF             \ its slot, piece and backdrop: pieces.asm)
CHANGES_PER_FRAME = 3           \ Changed tiles in a packet, at most

\ The draw list: a count, then per cell its masks' low byte, its graphics'
\ address and its screen address, then an entry's worth of padding (the
\ host reads an entry ahead)
LIST_ENTRY_BYTES = 5
LIST_MAX = 255

\ The store of changed chunks: the parasite's, and the host's copy in its
\ sideways RAM, slot n (from 1) at &8000 + ((n - 1) MOD 128) * 128 of the
\ store's bank (n - 1) DIV 128. A packet's changes to it follow its changed
\ tiles: a count, then each change's slot and offset, then a tile's
\ material and shape, or (offset STORE_CHUNK) the whole chunk.
\ The store has 255 slots: the directory holds a slot in a byte.
CHUNK_SIZE = 8
CHUNK_TILES = CHUNK_SIZE * CHUNK_SIZE
SLOT_BYTES = 2 * CHUNK_TILES    \ The materials, then the shapes
STORE_BANKS = 2
STORE_CHUNK = &FF
STORE_TILE_BYTES = 4
STORE_CHUNK_BYTES = 2 + SLOT_BYTES
FETCH_BYTES = 3                 \ Then a chunk to fetch: its slot, and the
                                \ parasite address to copy it to; or a 0;
                                \ then the items to draw (items.asm)

\ Host addresses the parasite puts into draw lists (asserted in render.asm)
HOST_MATERIAL_PAGES = &8100
HOST_LIGHT_MASKS = &9500

\ The Tube itself
TUBE_ENTRY = &0406              \ Host: claim, release, or start a transfer
TUBE_CLAIM = &C0 + &0E          \ Our claim ID: &0E
TUBE_RELEASE = &80 + &0E
TUBE_BYTES_TO_HOST = 0          \ Transfer types
TUBE_BYTES_TO_PARASITE = 1
TUBE_EXECUTE = 4
TUBE_R3_STATUS = &FEE4          \ Host: bit 7 a byte to read, bit 6 room to write
TUBE_R3 = &FEE5
