# To-Dos and Ideas

## Count Symbols extension

- [ ] Remove all parameters from .inx file so that dialog is not
      necessary.  (If the _include hidden_ option is really necessary,
      make that a whole separate command in it's own .inx file.)

## Create-Inset extension

- [ ] Add a way to rebuild all insets in file.

- [ ] Rebuild multiple insets in parallel, in multiple inkscape subprocesses.

## Resurrect the Update-Symbols extension

This would be good to have, as I think it would obviate the need for
the `[h] Internal Bits` layer in the maps.  Right now that is
necessary to hold references to fill patterns used by some of the
symbols.  The _update-symbols_ plugin should be able to insert the
needed fill patterns into the current document.

Since I am not a master of XSLT, it may be worth re-writing this in
python from it's current XSLT form.

If left as an XSLT transform, I think Inkscape can run it natively
without the need for `bh-update-symbols.sh` which runs `xsltproc`
externally.  (Look at the [aisvg.inx][] extension for hints.)

[aisvg.inx]: https://gitlab.com/inkscape/extensions/-/blob/master/aisvg.inx
