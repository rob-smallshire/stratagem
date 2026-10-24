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
| SPACE | place what's in your hand ahead; with K or M, above or below you |
| T | drop a torch |
| TAB | the next thing in your hand |
| P | open your pack |

In the pack, the world waits:

| Key | |
|---|---|
| the cursor keys | choose what's in your hand |
| T Y / G H | the cells of the grid: put what's in your hand there, or take it back |
| DELETE | empty the grid |
| RETURN | make what the grid shows; hold it to make more |
| COPY | lay out again something you've made before |
| P | close your pack |

## Your pack

Your pack holds everything you carry: up to 99 of each kind. Dig past 99
and the rest is left behind, so keep an eye on your counts.

The arrowheads mark what's in your hand. SPACE puts it down; when it runs
out, your hand moves to the next thing you can place.

## Making things

Below your pack is a grid, two cells by two, one for each of the keys
T Y / G H, as they lie on the keyboard:

```
   T  Y
    G  H
```

Choose something with the cursor keys, then press a cell's key to lay it
there. Press the key again to take it back. Lay things out in the right
shape and what they make shows beside the grid: press RETURN to make it.
The grid fills again from your pack, ready to make another.

A shape can sit anywhere in the grid, but it can't be turned round.

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

There is more to make than this. The old miners are said to have made
much better tools than these, and left word of them in the deep places.
