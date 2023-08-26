## Changes

### 1.0.0 (2023-08-26)

#### create-inset

- Fix to work when there are visible clones of layers with hidden parents. ([#2])

[#2]: https://github.com/barnhunt/inkex-bh/issues/2

### 1.0.0rc7 (2023-03-08)

#### update-symbols

- Only skip symbol sets if they contain a symbol id that conflicts
  with an already scanned symbol set.  Standard-scale (48:1) symbols
  sets are loaded first, so this results in skipping non-standard
  symbol sets, but *only* if they contain conflicting symbol ids.
  Previously, we just ignored all non-standard symbol sets.

  (Until recently, bale sets for non-standard scales (e.g. 60:1) used
  the same symbol ids as the standard scale (48:1) sets. As of
  `bh-symbols==1.0.0rc5`, all symbols now have globally unique ids.)

- Do not update unchanged symbols.

- Add `dry-run` option to report which symbols would be updated.

- Report the currently installed version of [bh-symbols].

### 1.0.0rc6 (2023-03-06)

- Added new *update-symbols* extension to update the symbol definitions
  in a drawing to those in the installed version of the [bh-symbols] symbol
  library.

  **NOTE** The *update symbols* operation, if it goes badly, has the
  capability to significantly mangle the drawing.  Make sure you have
  a back-up copy of the drawing before running the extension.

[bh-symbols]: https://github.com/barnhunt/bh-symbols

### 1.0.0rc5 (2023-02-17)

#### Refactor

- Use helpers provided by `inkex.command` (rather than calling
  `subprocess.run` directly) to run Inkscape (and optipng) from the
  *create-inset* extension.

#### Testing

- Add integration test for the *create-inset* extension. This checks
  that the extension can be invoked from Inkscape's batch mode.

- Omit use of virtual environment in `test_run_module_in_installed_extensions`.

### 1.0.0rc4 (2023-02-14)

#### Bugs

- Fix the _create inset_ extensions when running from the AppImage-packaged version
  of Inkscape 1.2.2.

### 1.0.0rc3 (2022-10-12)

#### Bugs

- Fix the _create inset_ and _hide rats_ extensions so that they might
  actually run under Inkscape 1.0.x.

#### Packaging

- We now build and publish — as GitHub Release artifacts — zip
  archives of the extension that suitable for unzipping in a user's
  Inkscape extensions directory.

- Use [hatch] for packaging.

#### Testing

- Install `inkex` from custom-built wheels in the python registry at
  https://gitlab.com/dairiki/inkex/.  The versions of `inkex` on PyPI
  are stale, and also don't match the `inkex` included in any
  particular version of Inkscape.

- We now test (I think) under truly the whole matrix of supported
  python × Inkscape/inkex versions.


[hatch]: https://github.com/pypa/hatch

### 1.0.0rc2 (2022-09-25)

#### Bugs Fixed

##### Hide Rats

- When _Clone rat layer_ selected, cloning of text was screwed up.

### 1.0.0rc1 (2022-08-31)

This is a fairly complete rewrite and repackaging of a set of Barn
Hunt extensions I used with Inkscape 0.9x.  (As of Inkscape 1.0, the
extension API changed significantly, so this required a significant
rework.)
