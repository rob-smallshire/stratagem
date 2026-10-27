\ MUSIC: the title's music on the Music 5000, the Stratagem Overture
\ (asm/music5000.asm, tools/stratagem/overture.py). STRAT loads it into user
\ RAM once the title's picture is on the (shadow) screen, plays it while
\ the title shows, and silences the board before it loads the game, whose
\ MAIN then overwrites it. On a machine without the board its writes go
\ nowhere.

CLEAR USER_START, USER_END
ORG USER_START
GUARD USER_END
.music_start
INCLUDE "asm/music5000.asm"
INCLUDE "build/generated/m5_overture.asm"
.music_end
SAVE "MUSIC", music_start, music_end
