\ MAIN: the game, in user RAM. For now: the player walks (Z, X) and jumps
\ (K) about the world, digs (L) and places blocks (SPACE), aiming down (M)
\ or up (K) or ahead, and the camera follows, scrolling smoothly.
\
\ Each frame, just after vertical sync, the screen is flipped: the CRTC is
\ given the new start address, and any newly exposed columns are drawn,
\ top-down, ahead of the beam. A newly exposed row is always the hidden
\ 32nd row, so it is drawn before the flip, while it cannot be seen. The rest
\ of the frame moves the player and plans the next flip.

CLEAR USER_START, USER_END
ORG USER_START
GUARD USER_END

\ Negative INKEY numbers, as OSBYTE &81 takes them in X
INKEY_Z = &100 - 98
INKEY_X = &100 - 67
INKEY_K = &100 - 71
INKEY_M = &100 - 102
INKEY_L = &100 - 87
INKEY_SPACE = &100 - 99

.main_start
{
    LDX #&FF                    \ Reset the stack: the loader is finished
    TXS
    LDA #0
    STA zp_frame
    STA zp_input
    STA zp_lead
    STA zp_camera_x
    STA zp_camera_x + 1
    STA zp_camera_y
    STA zp_camera_y + 1
    STA zp_columns_width
    STA zp_sprite_drawn
    STA zp_direction
    STA zp_player_vx
    STA zp_player_vy
    STA zp_player_on_ground
    STA inventory
    STA cooldown
    STA zp_player_jump_held
    STA zp_player_air_jumps
    STA redraw_tile
    STA light_valid
    STA light_queue_count
    LDA #STARTING_ABILITIES
    STA zp_abilities
    LDA #1
    STA zp_player_facing
    LDA #LO(PLAYER_START_X)
    STA zp_player_x
    LDA #HI(PLAYER_START_X)
    STA zp_player_x + 1
    LDA #LO(PLAYER_START_Y)
    STA zp_player_y
    LDA #HI(PLAYER_START_Y)
    STA zp_player_y + 1
    JSR player_focus_and_frame
    LDA #LO(SCREEN_START)
    STA zp_screen_start
    LDA #HI(SCREEN_START)
    STA zp_screen_start + 1
    JSR call_world_reset
    JSR setup_screen
    JSR call_render_clear
    JSR plan_camera             \ The focus is outside the view, so redraw
    JSR apply_plan
    JSR set_crtc_start
    JSR draw_sprite
    LDA #BOOT_READY
    STA zp_boot_status
    \ Fall through into the main loop
}

.main_loop
    INC zp_frame
    LDA #19                     \ Wait for vertical sync
    JSR OSBYTE
    \ After vertical sync, staying ahead of the beam: the new start address;
    \ the new columns' rows above the sprite, which the beam reaches first;
    \ the sprite (well inside the view, so clear of the new columns), which
    \ the beam reaches next; then the rest of the new columns.
    JSR set_crtc_start
    JSR sprite_split_row
    LDA #0
    LDX zp_split_row
    JSR draw_column_rows
    JSR restore_sprite
    JSR redraw_queued_tile
    JSR redraw_light_queue
    JSR draw_sprite
    LDA #VIEW_ROWS
    SEC
    SBC zp_split_row
    TAX
    LDA zp_split_row
    JSR draw_column_rows
    LDA #0
    STA zp_columns_width
.frame_shown                    \ The screen now shows the camera's view
    JSR read_input
    JSR update_player
    JSR player_action
    JSR plan_camera
    JSR apply_plan
    JMP main_loop

\ ---------------------------------------------------------------------------
\ Input

.read_input
{
    LDA #0
    STA zp_input
    LDX #INKEY_Z
    LDA #INPUT_LEFT
    JSR read_key
    LDX #INKEY_X
    LDA #INPUT_RIGHT
    JSR read_key
    LDX #INKEY_K
    LDA #INPUT_UP
    JSR read_key
    LDX #INKEY_M
    LDA #INPUT_DOWN
    JSR read_key
    LDX #INKEY_L
    LDA #INPUT_ACTION
    JSR read_key
    LDX #INKEY_SPACE
    LDA #INPUT_PLACE
    \ Fall through
}

\ If the key with negative INKEY number X is pressed, set bits A in zp_input.
.read_key
{
    PHA
    LDA #&81
    LDY #&FF
    JSR OSBYTE
    PLA
    CPX #&FF
    BNE done
    ORA zp_input
    STA zp_input
.done
    RTS
}

\ ---------------------------------------------------------------------------
\ Applying the plan

\ Redraw the whole view, or move the screen start by the planned movement,
\ bring the tile cache up to date, draw the new row (if any) into the
\ hidden row, and plan the new columns (if any) to be drawn at the flip.
.apply_plan
{
    LDA zp_redraw
    BEQ move
    JMP redraw_view
.move
    JSR move_screen_start
    JSR update_tile_cache
    JSR update_light            \ Before drawing the new row
    LDA zp_plan_dy
    BEQ no_row
    JSR draw_new_row
.no_row
    LDA zp_plan_dx
    BEQ no_columns
    JMP plan_new_columns
.no_columns
    RTS
}

\ Fill the tile cache for the view at the camera, light it, and draw it.
.redraw_view
{
    JSR fill_view
    JSR update_light
    JSR draw_view
    LDA #0                      \ Every tile is drawn with its light
    STA light_queue_count
    RTS
}

\ ---------------------------------------------------------------------------
\ Data

INCLUDE "asm/pixels.asm"
INCLUDE "asm/scroll.asm"
INCLUDE "asm/camera.asm"
INCLUDE "asm/cache.asm"
INCLUDE "asm/view.asm"
INCLUDE "asm/player.asm"
INCLUDE "asm/actions.asm"
INCLUDE "asm/lighting.asm"

.main_end

SAVE "MAIN", main_start, main_end
