## Changes

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

- Remove runtime dependency on `typing_extensions`.

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
