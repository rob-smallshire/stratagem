\ The tile cache: keeping it holding the view's tiles, from the world, as the
\ camera moves. On the host-only game the world is in its bank (call_fill_cache
\ pages it in); on the parasite it is simply there.

\ Set view_left/right/top/bottom to the tiles the view at the camera
\ shows.
.view_tiles
{
    LDA zp_camera_x + 1         \ Left: camera_x >> 2
    STA zp_temp
    LDA zp_camera_x
    LSR zp_temp
    ROR A
    LSR zp_temp
    ROR A
    STA view_left
    CLC                         \ Right: (camera_x + VIEW_COLUMNS - 1) >> 2
    LDA zp_camera_x
    ADC #VIEW_COLUMNS - 1
    STA zp_temp
    LDA zp_camera_x + 1
    ADC #0
    LSR A
    ROR zp_temp
    LSR A
    ROR zp_temp
    LDA zp_temp
    STA view_right
    LDA zp_camera_y + 1         \ Top: camera_y >> 1
    LSR A
    LDA zp_camera_y
    ROR A
    STA view_top
    CLC                         \ Bottom: (camera_y + VIEW_ROWS - 1) >> 1
    LDA zp_camera_y
    ADC #VIEW_ROWS - 1
    STA zp_temp
    LDA zp_camera_y + 1
    ADC #0
    LSR A
    LDA zp_temp
    ROR A
    STA view_bottom
    RTS
}

\ Bring the tile cache up to date for the view at the camera, which has
\ moved by at most a tile each way: fill any new tile columns, then any new
\ tile rows (across the new columns too, so the corner is filled).
.update_tile_cache
{
    JSR view_tiles
    LDA view_bottom          \ Columns are filled over the view's rows
    SEC
    SBC view_top
    STA zp_temp + 1
    INC zp_temp + 1             \ Tiles in a column
.right_loop
    LDA cached_right
    CMP view_right
    BCS right_done              \ Only ever expand: cached_right >= view_right
    INC cached_right
    LDA cached_right
    JSR fill_tile_column
    JMP right_loop
.right_done
.left_loop
    LDA view_left
    CMP cached_left
    BCS left_done               \ view_left >= cached_left
    DEC cached_left
    LDA cached_left
    JSR fill_tile_column
    JMP left_loop
.left_done
    LDA view_right           \ Rows are filled over the view's columns
    SEC
    SBC view_left
    STA zp_temp + 1
    INC zp_temp + 1             \ Tiles in a row
.down_loop
    LDA cached_bottom
    CMP view_bottom
    BCS down_done               \ cached_bottom >= view_bottom
    INC cached_bottom
    LDA cached_bottom
    JSR fill_tile_row
    JMP down_loop
.down_done
.up_loop
    LDA view_top
    CMP cached_top
    BCS up_done                 \ view_top >= cached_top
    DEC cached_top
    LDA cached_top
    JSR fill_tile_row
    JMP up_loop
.up_done
    \ The cache now holds exactly the view's tiles.
    LDA view_left
    STA cached_left
    LDA view_right
    STA cached_right
    LDA view_top
    STA cached_top
    LDA view_bottom
    STA cached_bottom
    RTS
}

\ Fill the cache for tile column A, zp_temp + 1 tiles from the view's top.
.fill_tile_column
{
    STA zp_fill_x
    LDA view_top
    STA zp_fill_y
    LDA #&FF
    BNE fill                    \ Always branches
}

\ Fill the cache for tile row A, zp_temp + 1 tiles from the view's left.
.fill_tile_row
{
    STA zp_fill_y
    LDA view_left
    STA zp_fill_x
    LDA #0
}

.fill
{
    STA zp_fill_down
    LDA zp_temp + 1
    STA zp_fill_count
    LDA #&FF                    \ New tiles: the light needs working out
    STA light_dirty
    JMP call_fill_cache
}

\ Fill the tile cache for the view at the camera, all of it.
.fill_view
{
    JSR view_tiles
    LDA view_right
    SEC
    SBC view_left
    STA zp_temp + 1
    INC zp_temp + 1             \ Tiles in a row
    LDA view_left               \ Cached so far: the rows filled
    STA cached_left
    LDA view_right
    STA cached_right
    LDA view_top
    STA cached_top
    STA cached_bottom
.fill_loop
    LDA cached_bottom
    JSR fill_tile_row
    LDA cached_bottom
    CMP view_bottom
    BEQ done
    INC cached_bottom
    BNE fill_loop               \ Always branches
.done
    RTS
}
