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
import struct
import subprocess
import sys
from argparse import ArgumentParser
from contextlib import contextmanager
from functools import reduce
from operator import or_
from tempfile import TemporaryDirectory
from typing import Callable
from typing import Iterable
from typing import Iterator
from typing import Sequence

import inkex
from inkex.command import INKSCAPE_EXECUTABLE_NAME
from inkex.localization import inkex_gettext as _
from lxml import etree

from ._compat import TypedDict
from .constants import BH_INSET_EXPORT_ID
from .constants import BH_INSET_VISIBLE_LAYERS
from .workarounds import mangle_cmd_for_appimage


DEFAULT_BACKGROUND = inkex.Color("white")


class Logger:
    def __init__(self) -> None:
        self.verbose = False

    def set_verbosity(self, verbose: bool) -> bool:
        prev = self.verbose
        self.verbose = verbose
        return prev

    def __call__(self, message: str) -> None:
        if self.verbose:
            inkex.errormsg(message)


log = Logger()


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


def run_command(cmd: Sequence[str], missing_ok: bool = False) -> None:
    """Run an external command.

    This goes to some lengths to be able to successfully run an
    executable (e.g. inkscape) which is provided by a currently active
    AppImage.

    verbose — Write command output to stderr, even when command
    completes successfully.  Normally output is squelched unless the
    command exits with a non-zero status.

    missing_ok — If executable can not be found, write a warning
    message, a return without raising an exception.

    """
    if missing_ok and not shutil.which(cmd[0]):
        inkex.errormsg(_("WARNING: Can not find executable for {}").format(cmd[0]))
        return

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
    if proc.stdout:
        log(proc.stdout)


class PngOptions(TypedDict, total=False):
    dpi: float
    scale: float
    background: str
    background_opacity: float
    optipng_level: int | None


def export_png(
    svg: inkex.SvgDocumentElement,
    export_id: str,
    *,
    dpi: float = 96,
    scale: float = 0.5,
    background: str = "#ffffff",
    background_opacity: float = 1.0,
    optipng_level: int | None = None,
) -> tuple[bytes, float, float]:
    """Create a PNG image from SVG drawing.

    Parameters:

    svg — The SVG element to convert to PNG

    export_id — The XML id of an element in svg. The bounding box of
      this element specifies the PNG boundaries.

    Returns:

    A triple (png_data, width, height) where png_data is the PNG image
    data, and width and height give the dimensions of the resulting
    image in Inkscape user units.
    """
    with TemporaryDirectory(prefix="bh-") as tmpdir:
        input_svg = os.path.join(tmpdir, "input.svg")
        output_png = os.path.join(tmpdir, "output.png")

        with open(input_svg, "wb") as fp:
            etree.ElementTree(svg).write(fp)
        args = [
            f"--export-filename={output_png}",
            "--export-type=png",
            f"--export-id={export_id}",
            f"--export-dpi={scale * dpi:f}",
            f"--export-background={background}",
            f"--export-background-opacity={background_opacity:f}",
        ]
        run_command([INKSCAPE_EXECUTABLE_NAME, *args, input_svg])

        if optipng_level is not None and optipng_level >= 0:
            run_command(
                ["optipng", "-o", f"{optipng_level:d}", output_png],
                missing_ok=True,
            )

        with open(output_png, "rb") as fp:
            png_data = fp.read()

    png_w, png_h = png_dimensions(png_data)
    image_scale = 96.0 / dpi
    return png_data, png_w * image_scale, png_h * image_scale


def export_image(
    svg: inkex.SvgDocumentElement,
    export_id: str,
    target: inkex.Image,
    png_options: PngOptions,
) -> None:
    """Export PNG image.

    Exports a PNG image.  The resulting image data is embedded in the
    svg:image element specified by target.
    """
    png_data, width, height = export_png(svg, export_id, **png_options)
    target.set("xlink:href", data_url(png_data, "image/png"))
    target.set("width", fmt_f(width))
    target.set("height", fmt_f(height))


def create_inset(
    svg: inkex.SvgDocumentElement,
    export_id: str,
    png_options: PngOptions,
) -> None:
    """Create a new inset."""
    image = inkex.Image()
    visible_layer_ids = {layer.get_id() for layer in get_visible_layers(svg)}
    image.set(BH_INSET_EXPORT_ID, export_id)
    image.set(BH_INSET_VISIBLE_LAYERS, " ".join(visible_layer_ids))

    export_image(svg, export_id, image, png_options)

    # center image on screen
    view_center = svg.namedview.center
    image.set("x", fmt_f(view_center.x - image.width / 2))
    image.set("y", fmt_f(view_center.y - image.height / 2))

    image.style["image-rendering"] = "optimizeQuality"
    # Inkscape normally sets preserveAspectRatio=none
    # which allows the image to be scaled arbitrarily.
    # SVG default is preserveAspectRatio=xMidYMid, which
    # preserves the image aspect ratio on scaling and seems
    # to make more sense for us.
    image.set("preserveAspectRatio", "xMidYMid")
    svg.append(image)


def recreate_inset(
    svg: inkex.SvgDocumentElement,
    image: inkex.Image,
    png_options: PngOptions,
) -> bool:
    """Re-export an existing inset."""
    export_id = image.get(BH_INSET_EXPORT_ID)
    visible_layer_ids = set(image.get(BH_INSET_VISIBLE_LAYERS, "").split())

    export_node = svg.getElementById(export_id)
    if export_node is None:
        inkex.errormsg(_("Can not find export node #{}").format(export_id))
        return False

    with temporary_visibility() as set_visibility:
        set_visibility(image, False)  # hide inset image
        for layer in get_layers(svg):
            set_visibility(layer, layer.get_id() in visible_layer_ids)
        export_image(svg, export_id, image, png_options)

    return True


def is_inset(elem: inkex.BaseElement) -> bool:
    """Determine whether element looks like an inset image we created."""
    return (
        isinstance(elem, inkex.Image)
        and elem.get(BH_INSET_EXPORT_ID)
        and elem.get(BH_INSET_VISIBLE_LAYERS)
    )


class CreateInset(inkex.Effect):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")
        pars.add_argument("--scale", type=float, default=0.5)
        pars.add_argument("--dpi", type=float, default=144.0)
        pars.add_argument("--background", type=inkex.Color, default=DEFAULT_BACKGROUND)
        pars.add_argument("--optipng-level", type=int, default=2)
        pars.add_argument("--verbose", type=inkex.Boolean, default=False)

    def effect(self) -> bool:
        svg = self.svg
        opt = self.options

        log.set_verbosity(opt.verbose)

        png_options: PngOptions = {
            "dpi": opt.dpi,
            "scale": opt.scale,
            "background": str(opt.background.to_rgb()),
            "background_opacity": opt.background.alpha,
            "optipng_level": opt.optipng_level if opt.optipng_level >= 0 else None,
        }

        insets = [elem for elem in svg.selection if is_inset(elem)]
        if insets:
            if len(svg.selection) != len(insets):
                inkex.errormsg(
                    _("Recreating selected insets. Ignoring non-insets in selection.")
                )
            # FIXME: parallel?
            return reduce(
                or_, (recreate_inset(svg, image, png_options) for image in insets)
            )

        if len(svg.selection) == 0:
            inkex.errormsg(_("No objects selected."))
            return False
        if len(svg.selection) > 1:
            inkex.errormsg(
                _(
                    "Select exactly one object to define the "
                    "bounding box of a new inset."
                )
            )
            return False

        # Selected element was not an inset image.
        # Create PNG from selected element
        export_id = svg.selection[0].get_id()
        create_inset(svg, export_id, png_options)
        return True


if __name__ == "__main__":
    CreateInset().run()
