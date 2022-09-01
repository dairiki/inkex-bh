# Inkscape Extensions for Barn Hunt

[![Tests](https://github.com/barnhunt/inkex-bh/actions/workflows/tests.yml/badge.svg)](https://github.com/barnhunt/inkex-bh/actions/workflows/tests.yml)
[![PyPI Version](https://img.shields.io/pypi/v/inkex-bh.svg)](https://pypi.org/project/inkex-bh/)
[![Python Versions](https://img.shields.io/pypi/pyversions/inkex-bh.svg)](https://pypi.org/project/inkex-bh/)
[![Inkscape Versions](https://img.shields.io/badge/Inkscape-1.0%E2%80%931.2-blue.svg?logo=inkscape)](https://inkscape.org/)
[![PyPI Status](https://img.shields.io/pypi/status/inkex-bh.svg)](https://pypi.org/project/inkex-bh/)

Here are some Inkscape extensions that are possibly useful when using
[Inkscape][] to draw [Barn Hunt][] maps.

These are a freshly updated and rewritten version of plugins that I
(and Sandra, my wife) have been using for several years to draw our
maps. The sample course map on the official [BHA Judging Assignment
Cheat Sheet][cheat] is one of mine. (The previous versions of the
plugins worked with Inkscape version 0.x.  The plugin API has changed
considerably since then, so a rewrite was necessary to get the plugins
to work with more modern versions of Inkscape.)

These extensions are, as yet, poorly documented, and likely not to
work without tweaks in all environments (I used Linux — these
extensions are totally untested on Windows), so I'm not sure that
they're generally useful, yet.

The goal is for these to work on all version of Inkscape with versions
of 1.0 or greater.  Currently, these have be cursorily tested under
Inkscape versions 1.1.2 and 1.2.1.

[Inkscape]: https://inkscape.org/ (The Inkscape home page)
[Barn Hunt]: https://www.barnhunt.com/ (Barn Hunt — a fabulous sport for dogs)
[cheat]: https://www.barnhunt.com/judge/resources.php?download=147 (The official BHA "Judging Assignment Cheat Sheet" which includes, as an example, one of my course maps, drawn using Inkscape.)


## What’s Here?

Currently there are four extensions.

### Count Symbols

We use Inkscape symbol libraries containing map elements like
individual bales, rat tube markers, etc to draw our maps.  This plugin
simply counts what symbols are visible, and reports a list of symbol
names along with how many times they are used in the drawing.  (By
default, only symbols on visible layers are counted.)

![Example output from the "Count Symbols" extension](https://github.com/barnhunt/inkex-bh/raw/master/count-symbols.png)

#### The bh:count-as symbol attribute

Symbols may be marked with a custom `bh:count-as` attribute, in order
to have them counted under some name other than their XML `id`.

I have a number of different symbols for bales: first level bales,
second level bales, bales on edge, leaners, etc.  I would like all
bales of a given size counted under the same name.  So, in my symbol
libraries, I set a `bh:count-as="bale-42x18x16"` on each of the
variants of 42”x18”x16” bales.

### Create Inset

This extension creates an embedded PNG image created by exporting a
portion of the drawing.  Such images are useful, for example, to include
a base-layer map (possibly at reduced scale) on the same page as the complete
course map.

To use, one should:

1. Hide/unhide layers as you wish, to make what you want visible in
   the exported image visible.

2. Select one object in the drawing. That object will define the
   rectangular bounding box of the exported image.  Then run the
   extension.

This will create an image. It will be created on top of all other
layers in the drawing. (You will probably want to move that image into
an appropriate layer.)

#### Regenerating the Insets

The layers that were visible when the image was generated, and the
object which defined the boundary of the image are recorded in custom
attributes on the `<svg:image>` element.  This makes it easy to
regenerate the image(s), should that become necessary (e.g. after
you've made changes to the drawing.)

Simply select just the generated images you'd like regenerated, and
fire off the extension.  It will adjust layer visibility to match what
it was when each image was first exported, and re-export it.


### Hide Rats

The third extension is used to randomize the position of rat tubes on rat maps.

Instructions pending... :-/

### Set Random Seed

This sets or updates a random number stored in a custom attribute out
the `<svg>` element of the drawing.  This number is used by the
[barnhunt][] program to seed the pseudo-random number generator used
when expanding text templates.  Setting it to a unique number ensure,
e.g., that the Master random rat numbers come out random, but still
reproducible.

When one copies an existing `.svg` file to use a template for a new
trial, one should run this plugin, with the _force-reseed_ checkbox
checked, to ensure that the copied file gets a new, unique random
seed.

----

## Installation

It's a little h<del>o</del><ins>ac</ins>key to use pip in this way,
but these extensions should be installable using pip.

```
pip install --target "$(inkscape --user-data-directory)/extensions" inkex_bh
```

Alternatively, it should work to simply symlink or copy the `inkex_bh`
directory from the source distribution (or git repository) to the user
`extensions` directory.

----


## What's Elsewhere?

There are two other bits I use when drawing maps.

Neither of these are published in a public place, yet.

And, of course, their use is not documented at all.

Kick me if you want to know more.


### Barn Hunt Symbol Libraries for Inkscape

I've constructed some symbol libraries for Inkscape containing things
like bales, boards, rat markers, fluff pile symbols, etc.

I've even got a semi-automatic scheme set up by which I can generate
symbol sets for arbitrary sized bales.


### The `barnhunt` command-line export utility

I draw all my maps for a given course (for a day or weekend) on
various nested layers in a single drawing.  By hiding and unhiding
various sets of layers all of my maps can be generated.

I have a python script named [`barnhunt`][barnhunt], whose primary job
is to automate that layer hiding/unhiding and PDF exporting process.
While exporting the map, it can also expand special template syntax in
text in the drawings.  This can be used to automate the printing of
course names and blind numbers on the exported map, and is also used
to generate the random Master rat numbers.

Sadly, at present there is zero documentation on how to use it.

Kick me if you want to know more.

[barnhunt]: https://github.com/barnhunt/barnhunt

## Author

Jeff Dairiki, BHAJ-221A
<dairiki@dairiki.org>

----
