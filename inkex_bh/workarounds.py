# Copyright (C) 2019–2022 Geoffrey T. Dairiki <dairiki@dairiki.org>
"""Some code for hacking around bugs in current and past version of inkex.

"""
from __future__ import annotations

import os
import shutil
import sys
from contextlib import contextmanager
from contextlib import ExitStack
from typing import Iterator
from typing import Sequence

import inkex

from . import typing as types
from ._compat import to_dimensionless


def inkex_tspan_bounding_box_is_buggy() -> bool:
    # As of Inkscape 1.2.1, inkex puts bbox.top at y and bbox.bottom
    # at y + font-size.  This is incorrect: tspan[@y] specifies the
    # position of the baseline, so bbox.top should be y - fontsize,
    # bbox.bottom should be y.
    tspan = inkex.Tspan.new(x="0", y="0", style="font-size: 1")
    bbox = tspan.bounding_box()
    return bbox.bottom > 0.5  # type: ignore[no-any-return]


@contextmanager
def negate_fontsizes(document: types.SvgElementTree) -> Iterator[None]:
    """Temporarily negate all text font-sizes.

    This is to work around a bug in inkex.Tspan.
    """
    mangled = []
    try:
        for elem in document.xpath("//svg:text | //svg:tspan"):
            elem.set("x-save-style", elem.get("style", None))
            fontsize = to_dimensionless(elem, elem.style.get("font-size"))
            elem.style["font-size"] = -fontsize
            mangled.append(elem)

        yield

    finally:
        for elem in mangled:
            elem.set("style", elem.attrib.pop("x-save-style", None))


@contextmanager
def text_bbox_hack(document: types.SvgElementTree) -> Iterator[None]:
    """Hack up document to work-around buggy text bbox computation in inkex."""
    with ExitStack() as stack:
        if inkex_tspan_bounding_box_is_buggy():
            stack.enter_context(negate_fontsizes(document))
        yield


def _is_subpath(path: str, parent: str) -> bool:
    """Determine whether path is a subpath of parent.

    Returns true iff path is a subpath of parent.

    """
    try:
        relpath = os.path.relpath(path, parent)
    except ValueError:
        return False  # different drive on windows
    return not any(
        relpath.startswith(f"{os.pardir}{sep}") for sep in (os.sep, os.altsep)
    )


def mangle_cmd_for_appimage(cmd: Sequence[str]) -> tuple[str, ...]:
    """Mangle the command argv when running a command from an AppImage.

    When running binaries from within an AppImage, we need to make sure
    that shared libraries are loaded from the AppImage.

    If the executable named by the first item in ``cmd`` appears to refer
    to a program from the currently active AppImage (if any), the command
    will be modified in a way to ensure that the command loads its shared
    libraries from the AppImage.

    If the named executable resolves to a binary outside of the currently
    active AppImage (or if there is no currently active AppImage) this
    returns ``cmd`` unmodified.

    Currently, this uses ld-linux to crowbar the library search path
    for the command.

    """
    # Without these machinations, inkscape seems to mostly run okay,
    # but, at least, when exporting PNGs produces:
    #
    # inkscape: symbol lookup error:
    #   /tmp/.mount_Inkscag6GeLM/usr/bin/../lib/x86_64-linux-gnu/inkscape/../libcairo.so.2:
    #   undefined symbol: pixman_image_set_dither
    #
    # See the /RunApp script in the Inkscape AppImage itself for an example
    # of how it runs inkscape.
    #
    if sys.platform != "linux":
        return tuple(cmd)  # AppImage is only supported on Linux
    executable = shutil.which(cmd[0])
    appdir = os.environ.get("APPDIR")
    if "APPIMAGE" not in os.environ or not appdir:
        return tuple(cmd)  # no active AppImage
    if executable is None or not _is_subpath(executable, appdir):
        return tuple(cmd)  # binary not in not in AppImage

    # XXX: is hard-coded good enough for these??
    platform = "x86_64-linux-gnu"
    ld_linux = os.path.join(appdir, "lib", platform, "ld-linux-x86-64.so.2")
    if not os.path.isfile(ld_linux):
        raise RuntimeError("Can not find ld-linux in AppImage")

    libpath = os.pathsep.join(
        [
            os.path.join(appdir, "lib", platform),
            os.path.join(appdir, "usr", "lib", platform),
            os.path.join(appdir, "usr", "lib"),
        ]
    )

    return (
        ld_linux,
        "--inhibit-cache",
        "--library-path",
        libpath,
        executable,
        *cmd[1:],
    )
