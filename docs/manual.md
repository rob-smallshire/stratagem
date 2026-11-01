# Stratagem: the miner's manual

*Kept in step with the recipes in `tools/stratagem/crafting.py`. Written to
be printed, as the manuals of the games it follows were.*

## The miner

You are a miner, set down on a hillside with a few torches and nothing
else. Below you the ground goes down a long way. What you dig, you keep;
what you keep, you can build with, or make into something better.

## Keys

In the world:

| Key | |
|---|---|
| Z, X | left, right |
| K | jump |
| L | dig ahead; with K or M, above or below you; with Z or X as well, a sloping tunnel |
| SPACE | place what's in your hand ahead (a block, or a torch); with K or M, above or below you. A torch with nowhere else to go goes where you stand |
| TAB | the next thing in your hand |
| 1 to 9 | take a tool from your belt into your tool hand; an empty slot is your bare hands |
| 0 | show the tool in your hand, and its number on your belt |
| P | open your pack |

In the pack, the world waits:

| Key | |
|---|---|
| Z X K M | choose what's in your hand |
| TAB | the next thing in your pack, round again |
| R T / F G | the cells of the grid: put what's in your hand there, or take it back |
| DELETE | empty the grid |
| L | make what the grid shows; hold it to make more |
| COPY | lay out again something you've made before |
| 1 to 9 | take that slot of your belt into your tool hand: an empty slot first takes a tool of the kind in your hand from your pack; a full one puts its tool back in your pack, in your hand |
| P | close your pack |

## Your pack

Your pack holds everything you carry: up to 99 of each kind. Dig past 99
and the rest is left behind, so keep an eye on your counts.

The arrowheads mark what's in your hand. SPACE puts it down; when it runs
out, your hand moves to the next thing you can place, shown above you:
press SPACE again to place that.

## Making things

Below your pack is a grid, two cells by two, one for each of the keys
R T / F G, as they lie on the keyboard:

```
   R  T
    F  G
```

Choose something with Z X K M, then press a cell's key to lay it
there. Press the key again to take it back. Lay things out in the right
shape and what they make shows beside the grid: press L to make it.
The grid fills again from your pack, ready to make another.

A shape can sit anywhere in the grid, but it can't be turned round.

Near a workbench, the grid is three cells by three, the keys
R T Y / F G H / V B N:

```
   R  T  Y
    F  G  H
     V  B  N
```

A workbench is placed like a block, with SPACE. Dig it and it comes back to
you.

What you've made once, your pack remembers. COPY lays out each of those
shapes in turn, from what you carry; a cell left empty shows what you're
short of.

## First shapes

Wood comes from trees. Dig a tree's root, and down it comes.

**Planks** (four), from a piece of wood:

```
  [wood]
```

**Torches** (two), ore over wood:

```
  [ore ]
  [wood]
```

**A workbench**, from four planks:

```
  [plnk][plnk]
  [plnk][plnk]
```

At a workbench:

**A wooden pickaxe**, a T of planks:

```
  [plnk][plnk][plnk]
  [    ][plnk][    ]
  [    ][plnk][    ]
```

**A stone pickaxe**, the same with a head of stone.

## Your tool belt

You have two hands. One holds what SPACE places; the other holds a tool,
which L digs with. Your tools hang on a belt of nine slots, one for each
of the number keys 1 to 9. In your pack, choose a tool, then press a number
to take one out of your pack and hang it there; press the number again to
put it back. Out in the world, press that number to take it in hand. The
tool shows above you for a moment, with its number beside it, whenever you
press its number; 0 shows the tool you're holding. The belt is shown along
the bottom of your pack, its arrowheads cyan; your hand's arrowheads turn
cyan too when they're at a tool, something that can hang on the belt, and
so does the one pointing at what the grid makes, when it makes a tool.

Bare hands dig soil slowly and can't dig stone at all; a pickaxe can. A
tree, though, comes down to bare hands: start there.

Dug, soil is gone: there's nothing in it to carry. Stone you carry can be
put down again, but only as soil, and only on something solid: nothing
you put down hangs in the air, but a torch, which can go on a wall.

Tools wear out. When one breaks it's gone from your belt, and a blue
outline, your bare hands, shows above you: hang another there from your
pack. A tool put back in your pack doesn't mend; the worn ones come out
first.

There is more to make than this. The old miners are said to have made
much better tools than these, and left word of them in the deep places.
