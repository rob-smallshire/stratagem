\ The world's day: a 16-bit clock of game frames, zp_time, midnight at 0
\ and noon at &8000, wrapping at midnight; stopped while the pack is open
\ (the game paused). Its high byte, the time in 256ths of a day, is sent
\ to the host in each packet (PACKET_TIME), and zp_world (PACKET_WORLD):
\ WORLD_UNDERGROUND if the player's feet are UNDERGROUND_DEPTH or more
\ tiles below its column's surface. Both are for the music's director; the
\ world's light doesn't follow the clock yet.

\ The clock at the start of the game.
.world_clock_start
{
    LDA #LO(START_TIME)
    STA zp_time
    LDA #HI(START_TIME)
    STA zp_time + 1
    LDA #0
    STA zp_world
    RTS
}

\ A frame on, and zp_world.
.world_clock
{
    INC zp_time
    BNE counted
    INC zp_time + 1
.counted
    CLC                         \ The player's middle column (as middle_column,
    LDA zp_box_x                \ keeping target_x)
    ADC #PLAYER_WIDTH / 2
    STA zp_temp
    LDA zp_box_x + 1
    ADC #0
    JSR column_of
    TAX
    JSR feet_row
    SEC
    SBC surface_heights,X       \ Rows below the surface
    BCC above
    CMP #UNDERGROUND_DEPTH
    BCC above
    LDA #WORLD_UNDERGROUND
    BNE world                   \ (always)
.above
    LDA #0
.world
    STA zp_world
    RTS
}
