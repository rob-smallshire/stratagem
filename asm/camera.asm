\ Camera: modelled exactly by tools/stratagem/camera.py. Pure, using only
\ zero page, so it can be tested in py65.

\ Ease the lead towards the focus's direction of travel, zp_direction, then
\ decide where the camera goes next: set zp_camera_x/y, and either
\ zp_plan_dx/dy, the movement to apply at the next flip, or zp_redraw.
.plan_camera
{
    LDA #0
    LDX zp_direction
    BEQ target_set
    LDA #LEAD_MAX
    CPX #1
    BEQ target_set
    LDA #&100 - LEAD_MAX
.target_set
    STA zp_temp
    LDA zp_lead
    SEC
    SBC zp_temp                 \ lead - target, small enough not to overflow
    BEQ lead_done
    BMI increase_lead
    DEC zp_lead
    JMP lead_done
.increase_lead
    INC zp_lead
.lead_done
    LDA #0
    STA zp_redraw
    STA zp_plan_dx
    STA zp_plan_dy
    \ The focus column and row, and where they are in the view.
    LDA zp_focus_x + 1
    LSR A
    STA zp_column + 1
    LDA zp_focus_x
    ROR A
    STA zp_column
    LDA zp_focus_y + 1
    STA zp_row + 1
    LDA zp_focus_y
    LSR zp_row + 1
    ROR A
    LSR zp_row + 1
    ROR A
    LSR zp_row + 1
    ROR A
    STA zp_row
    SEC
    LDA zp_column
    SBC zp_camera_x
    STA zp_relative_x
    LDA zp_column + 1
    SBC zp_camera_x + 1
    BNE jump_to_redraw          \ Left of the view, or far right of it
    LDA zp_relative_x
    CMP #VIEW_COLUMNS
    BCS jump_to_redraw
    SEC
    LDA zp_row
    SBC zp_camera_y
    STA zp_relative_y
    LDA zp_row + 1
    SBC zp_camera_y + 1
    BNE jump_to_redraw
    LDA zp_relative_y
    CMP #VIEW_ROWS
    BCC in_view
.jump_to_redraw
    JMP redraw
.in_view
    \ Horizontally: keep the focus in the window, shifted by the lead.
    LDA #WINDOW_LEFT
    SEC
    SBC zp_lead
    STA zp_temp                 \ Left edge of the window
    LDA zp_relative_x
    CMP zp_temp
    BCS not_left
    LDA zp_temp                 \ Step left by min(MAX_STEP_X, (left - x + 3) >> 2)
    SEC
    SBC zp_relative_x
    CLC
    ADC #3
    LSR A
    LSR A
    CMP #MAX_STEP_X
    BCC left_step
    LDA #MAX_STEP_X
.left_step
    EOR #&FF                    \ Negate
    CLC
    ADC #1
    STA zp_plan_dx
    JMP vertical
.not_left
    LDA #WINDOW_RIGHT
    SEC
    SBC zp_lead
    STA zp_temp                 \ Right edge of the window
    LDA zp_relative_x
    CMP zp_temp
    BCC vertical
    SEC                         \ Step right by min(MAX_STEP_X, (x - right + 4) >> 2)
    SBC zp_temp
    CLC
    ADC #4
    LSR A
    LSR A
    CMP #MAX_STEP_X
    BCC right_step
    LDA #MAX_STEP_X
.right_step
    STA zp_plan_dx
.vertical
    LDA zp_relative_y
    CMP #WINDOW_TOP
    BCS not_up
    LDA #&FF
    STA zp_plan_dy
    BNE apply
.not_up
    CMP #WINDOW_BOTTOM
    BCC apply
    LDA #1
    STA zp_plan_dy
.apply
    \ Move the camera, clamped to the world, and record how far it moved.
    LDA zp_camera_x
    STA zp_temp
    LDA zp_plan_dx
    BEQ x_done
    BMI x_left
    CLC
    ADC zp_camera_x
    STA zp_camera_x
    BCC x_added
    INC zp_camera_x + 1
.x_added
    LDA #LO(CAMERA_X_MAX)
    CMP zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    SBC zp_camera_x + 1
    BCS x_moved
    LDA #LO(CAMERA_X_MAX)
    STA zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    STA zp_camera_x + 1
    JMP x_moved
.x_left
    CLC
    ADC zp_camera_x
    STA zp_camera_x
    LDA zp_camera_x + 1
    ADC #&FF
    STA zp_camera_x + 1
    BCS x_moved                 \ No borrow, so not below 0
    LDA #0
    STA zp_camera_x
    STA zp_camera_x + 1
.x_moved
    LDA zp_camera_x
    SEC
    SBC zp_temp
    STA zp_plan_dx
.x_done
    LDA zp_camera_y
    STA zp_temp
    LDA zp_plan_dy
    BEQ y_done
    BMI y_up
    CLC
    ADC zp_camera_y
    STA zp_camera_y
    BCC y_added
    INC zp_camera_y + 1
.y_added
    LDA #LO(CAMERA_Y_MAX)
    CMP zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    SBC zp_camera_y + 1
    BCS y_moved
    LDA #LO(CAMERA_Y_MAX)
    STA zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    STA zp_camera_y + 1
    JMP y_moved
.y_up
    CLC
    ADC zp_camera_y
    STA zp_camera_y
    LDA zp_camera_y + 1
    ADC #&FF
    STA zp_camera_y + 1
    BCS y_moved
    LDA #0
    STA zp_camera_y
    STA zp_camera_y + 1
.y_moved
    LDA zp_camera_y
    SEC
    SBC zp_temp
    STA zp_plan_dy
.y_done
    RTS

    \ The focus is outside the view: centre the view on it.
.redraw
    LDA #&FF
    STA zp_redraw
    SEC                         \ camera_x = clamp(column - CENTRE_X, 0, CAMERA_X_MAX)
    LDA zp_column
    SBC #CENTRE_X
    STA zp_camera_x
    LDA zp_column + 1
    SBC #0
    STA zp_camera_x + 1
    BCS redraw_x_not_negative
    LDA #0
    STA zp_camera_x
    STA zp_camera_x + 1
.redraw_x_not_negative
    LDA #LO(CAMERA_X_MAX)
    CMP zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    SBC zp_camera_x + 1
    BCS redraw_x_done
    LDA #LO(CAMERA_X_MAX)
    STA zp_camera_x
    LDA #HI(CAMERA_X_MAX)
    STA zp_camera_x + 1
.redraw_x_done
    SEC                         \ camera_y = clamp(row - CENTRE_Y, 0, CAMERA_Y_MAX)
    LDA zp_row
    SBC #CENTRE_Y
    STA zp_camera_y
    LDA zp_row + 1
    SBC #0
    STA zp_camera_y + 1
    BCS redraw_y_not_negative
    LDA #0
    STA zp_camera_y
    STA zp_camera_y + 1
.redraw_y_not_negative
    LDA #LO(CAMERA_Y_MAX)
    CMP zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    SBC zp_camera_y + 1
    BCS redraw_y_done
    LDA #LO(CAMERA_Y_MAX)
    STA zp_camera_y
    LDA #HI(CAMERA_Y_MAX)
    STA zp_camera_y + 1
.redraw_y_done
    RTS
}

