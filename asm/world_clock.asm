\ The world's day: a clock of HOURS hours, each HOUR_FRAMES game frames,
\ stopped while the pack is open (the game paused); and zp_world, sent to
\ the host in each packet (PACKET_WORLD) for the music's director: the
\ hour, with WORLD_UNDERGROUND if the player's feet are UNDERGROUND_DEPTH
\ or more tiles below its column's surface. The world's light doesn't
\ follow the clock yet.

\ The clock at the start of the game.
.world_clock_start
{
    LDA #0
    STA world_frames
    STA world_frames + 1
    LDA #START_HOUR
    STA world_hour
    STA zp_world
    RTS
}

\ A frame on, and zp_world.
.world_clock
{
    INC world_frames
    BNE counted
    INC world_frames + 1
.counted
    LDA world_frames
    CMP #LO(HOUR_FRAMES)
    BNE hour_kept
    LDA world_frames + 1
    CMP #HI(HOUR_FRAMES)
    BNE hour_kept
    LDA #0
    STA world_frames
    STA world_frames + 1
    LDX world_hour
    INX
    CPX #HOURS
    BNE hour_set
    LDX #0
.hour_set
    STX world_hour
.hour_kept
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
    ORA world_hour
    STA zp_world
    RTS
}
