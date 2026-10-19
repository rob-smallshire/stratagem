\ The player's box in pixels and lines, from its position in sixteenths:
\ wanted by movement, digging and light, and by the sprite's drawing.

\ Set zp_box_x/y to the player's position in pixels and lines.
.player_pixels
{
    LDA zp_player_x + 1
    STA zp_box_x + 1
    LDA zp_player_x
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    LSR zp_box_x + 1
    ROR A
    STA zp_box_x
    LDA zp_player_y + 1
    STA zp_box_y + 1
    LDA zp_player_y
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    LSR zp_box_y + 1
    ROR A
    STA zp_box_y
    RTS
}
