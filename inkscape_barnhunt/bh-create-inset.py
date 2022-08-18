#!/usr/bin/env python
# Copyright (C) 2019–2022 Geoffrey T. Dairiki <dairiki@dairiki.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Export bbox of selection to PNG image

"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import struct
import sys
from argparse import ArgumentParser
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Callable
from typing import Iterable
from typing import Iterator
from typing import Sequence

import inkex
from inkex.command import INKSCAPE_EXECUTABLE_NAME
from inkex.localization import inkex_gettext as _

from inkex_bh.constants import BH_INSET_EXPORT_ID
from inkex_bh.constants import BH_INSET_VISIBLE_LAYERS


def data_url(data: bytes, content_type: str = "application/binary") -> str:
    encoded = base64.b64encode(data).decode("ascii", errors="strict")
    return f"data:{content_type};base64,{encoded}"


def png_dimensions(png_data: bytes) -> tuple[int, int]:
    assert len(png_data) >= 24
    assert png_data[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_data[12:16] == b"IHDR"
    width, height = struct.unpack(">LL", png_data[16:24])
    return width, height


def fmt_f(value: float) -> str:
    """Format value as float."""
    return f"{value:f}"


def get_layers(svg: inkex.SvgDocumentElement) -> Iterable[inkex.Layer]:
    """Get all layers in SVG."""
    layers: Sequence[inkex.Layer] = svg.xpath("//svg:g[@inkscape:groupmode='layer']")
    return layers


def is_visible(elem: inkex.BaseElement) -> bool:
    while elem is not None:
        if elem.style.get("display") == "none":
            return False
        elem = elem.getparent()
    return True


def get_visible_layers(svg: inkex.SvgDocumentElement) -> Iterator[inkex.Layer]:
    for layer in get_layers(svg):
        if is_visible(layer):
            yield layer


SetVisibilityFunction = Callable[[inkex.BaseElement, bool], None]


@contextmanager
def temporary_visibility() -> Iterator[SetVisibilityFunction]:
    """Temporarily adjust SVG element/layer visiblity.

    This context manager provices a function which can be used to set
    the visibility of SVG elements.

    Any visibility changes so made are undone when the context is exited.

    """
    saved = []

    def set_visibility(elem: inkex.BaseElement, visibility: bool) -> None:
        saved.append((elem, elem.get("style")))
        elem.style["display"] = "inline" if visibility else "none"

    try:
        yield set_visibility

    finally:
        for elem, style in reversed(saved):
            elem.set("style", style)


def is_appimage_executable(prog: str) -> bool:
    """Determine whether program belongs to the active AppImage

    Returns true iff ``prog`` resolves to a executable contained with
    the currently active AppImage.  (If there is no active AppImage
    returns false.)
    """
    executable = shutil.which(prog)
    if executable is None:
        return False

    appdir = os.environ.get("APPDIR", "")
    if appdir and "APPIMAGE" in os.environ:
        try:
            relpath = os.path.relpath(executable, appdir)
        except ValueError:
            return False  # different drive on windows
    return not any(
        relpath.startswith(f"{os.pardir}{sep}") for sep in (os.sep, os.altsep)
    )


def mangle_cmd_for_appimage(cmd: Sequence[str]) -> tuple[str, ...]:
    """Mangle the LD_LIBRARY_PATH when running a command from an AppImage.

    When running inkscape (or python?) from an Inkscape AppImage we need to
    tell ld-linux to used shared libraries from the AppImage.  This mangles
    the ``cmd`` sequence in order to do that.

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

    appdir = os.environ["APPDIR"]
    executable = shutil.which(cmd[0])
    assert executable is not None

    # XXX: is hard-coded good enough for these??
    platform = "x86_64-linux-gnu"
    ld_linux = os.path.join(appdir, "lib", platform, "ld-linux-x86-64.so.2")
    if not os.path.isfile(ld_linux):
        raise RuntimeError("Can not find ld-linux in AppImage")

    libpath = [
        os.path.join(appdir, "lib", platform),
        os.path.join(appdir, "usr/lib", platform),
        os.path.join(appdir, "usr/lib"),
    ]

    return (
        ld_linux,
        "--inhibit-cache",
        "--library-path",
        ":".join(libpath),
        executable,
        *cmd[1:],
    )


def run(cmd: Sequence[str], verbose: bool = False, missing_ok: bool = False) -> None:
    if missing_ok and not shutil.which(cmd[0]):
        inkex.errormsg(_("WARNING: Can not find executable for {}").format(cmd[0]))
        return

    if is_appimage_executable(cmd[0]):
        cmd = mangle_cmd_for_appimage(cmd)

    try:
        proc = subprocess.run(
            cmd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as ex:
        if ex.stdout:
            inkex.errormsg(ex.stdout)
        inkex.errormsg(str(ex))
        sys.exit(1)
    if verbose and proc.stdout:
        inkex.errormsg(proc.stdout)


class CreateInset(inkex.Effect):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")
        pars.add_argument("--scale", type=float, default=0.5)
        pars.add_argument("--dpi", type=float, default=144.0)
        pars.add_argument("--background", type=inkex.Color, default="#ffffff")
        pars.add_argument("--optipng-level", type=int, default=2)
        pars.add_argument("--verbose", type=inkex.Boolean, default=False)

    def export_png(self, export_id: str, target: inkex.Image) -> None:
        opt = self.options

        with TemporaryDirectory(prefix="bh-") as tmpdir:
            input_svg = os.path.join(tmpdir, "input.svg")
            output_png = os.path.join(tmpdir, "output.png")

            with open(input_svg, "wb") as fp:
                self.document.write(fp)

            run(
                [
                    INKSCAPE_EXECUTABLE_NAME,
                    f"--export-filename={output_png}",
                    "--export-type=png",
                    f"--export-id={export_id}",
                    f"--export-background={opt.background.to_rgb()}",
                    f"--export-background-opacity={opt.background.alpha:f}",
                    f"--export-dpi={opt.scale * opt.dpi:f}",
                    input_svg,
                ],
                verbose=opt.verbose,
            )

            if opt.optipng_level >= 0:
                run(
                    ["optipng", "-o", f"{opt.optipng_level}", output_png],
                    missing_ok=True,
                    verbose=opt.verbose,
                )

            with open(output_png, "rb") as fp:
                png_data = fp.read()

        png_w, png_h = png_dimensions(png_data)
        image_scale = 96.0 / self.options.dpi
        target.set("xlink:href", data_url(png_data, "image/png"))
        target.set("width", fmt_f(png_w * image_scale))
        target.set("height", fmt_f(png_h * image_scale))

    def _recreate_inset(self, image: inkex.Image) -> None:
        export_id = image.get(BH_INSET_EXPORT_ID)
        visible_layer_ids = set(image.get(BH_INSET_VISIBLE_LAYERS, "").split())

        export_node = self.svg.getElementById(export_id)
        if export_node is None:
            inkex.errormsg(_("Can not find export node #{}").format(export_id))
            sys.exit(1)

        with temporary_visibility() as set_visibility:
            set_visibility(image, False)  # hide inset image
            for layer in get_layers(self.svg):
                set_visibility(layer, layer.eid in visible_layer_ids)
            self.export_png(export_id, image)

    def _create_inset(self, export_id: str) -> None:
        image = inkex.Image()
        self.export_png(export_id, image)

        visible_layer_ids = {layer.eid for layer in get_visible_layers(self.svg)}
        image.set(BH_INSET_EXPORT_ID, export_id)
        image.set(BH_INSET_VISIBLE_LAYERS, " ".join(visible_layer_ids))

        # center image on screen
        view_center = self.svg.namedview.center
        image.set("x", fmt_f(view_center.x - image.width / 2))
        image.set("y", fmt_f(view_center.y - image.height / 2))

        image.style["image-rendering"] = "optimizeQuality"
        # Inkscape normally sets preserveAspectRatio=none
        # which allows the image to be scaled arbitrarily.
        # SVG default is preserveAspectRatio=xMidYMid, which
        # preserves the image aspect ratio on scaling and seems
        # to make more sense for us.
        image.set("preserveAspectRatio", "xMidYMid")
        self.svg.append(image)

    def effect(self) -> None:
        # FIXME: add a way to rebuild all insets in the file
        if len(self.svg.selection) != 1:
            inkex.errormsg(_("You must select exactly one object."))
            sys.exit(1)
        selected_elem = self.svg.selection[0]

        if isinstance(selected_elem, inkex.Image) and selected_elem.get(
            BH_INSET_EXPORT_ID
        ):
            # Previously created inset image was selected.
            # Attempt to re-create/update the image.
            self._recreate_inset(image=selected_elem)
        else:
            # Selected element was not an inset image.
            # Create PNG from selected element
            self._create_inset(export_id=selected_elem.eid)


if __name__ == "__main__":
    CreateInset().run()
