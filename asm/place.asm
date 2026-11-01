\ Placing, on the parasite (tools/stratagem/actions.py's act, with
\ actions.asm): in PLIGHT, as PGAME has no room.

\ Place the kind in hand in the empty tile aimed at, if any: clear of the
\ player, unless it can be walked through. If none of that kind is left,
\ the hand moves to the first kind held that places something, and nothing
\ is placed until SPACE is pressed again (zp_place_wait); if there is none,
\ or the hand places nothing, nothing is placed. Anything but a torch
\ goes only on a floor: the tile beneath it solid (not passable), so
\ nothing is put down in mid-air. A torch is added to the torches
\ (torches.asm), unless there are TORCH_MAX already; with no empty tile to
\ aim at, it goes in the miner's own tile, if that is empty.
.place
{
    LDA zp_place_wait
    BNE none
    LDX hand
    LDA kind_places,X
    BMI none
    LDA inventory,X
    BNE in_hand
    LDX #0
.find
    LDA kind_places,X
    BMI next
    LDA inventory,X
    BNE found
.next
    INX
    CPX #KIND_COUNT
    BNE find
.none
    RTS
.found
    STX hand                    \ Shown, not placed, until SPACE again
    LDA #&FF
    STA zp_place_wait
    RTS
.in_hand
    JSR torch_room              \ A torch, if there is room for another
    BCS done
    LDX hand                    \ Aim for an empty tile: clear of the
    LDY kind_places,X           \ player (bit 6), unless passable
    LDA #&FF
    LDX material_passable,Y
    BEQ solid
    LDA #&80
.solid
    STA want
    JSR aim
    BCC aimed
    JSR torch_own_tile          \ None: a torch goes in the miner's own
    BCS done                    \ tile, if that is empty
    BCC floored
.aimed
    LDX hand
    LDA kind_places,X
    CMP #TILE_TORCH
    BEQ floored
    INC target_y                \ Anything else on a floor
    JSR target_tile
    DEC target_y
    TAX
    LDA material_passable,X
    BNE done
.floored
    JSR target_background
    STA zp_world_new_shape      \ SHAPE_FULL with the background
    LDX hand
    LDA kind_places,X
    CMP #TILE_TORCH
    BEQ torch
    JSR change_target
    BCS done
.placed
    LDX hand
    DEC inventory,X
    LDA #PLACE_FRAMES
    STA cooldown
    LDA #ACTION_PLACE
    STA action
.done
    RTS
.torch
    JSR torch_place
    BCC placed
    RTS
}
