#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Export bbox of selection to PNG image

'''
import base64
from contextlib import contextmanager
import os
import subprocess
import struct
import tempfile

import inkex
import simpletransform

inkex.localize()
_ = _                           # noqa: F821

SVG_SVG = inkex.addNS('svg', 'svg')
SVG_IMAGE = inkex.addNS('image', 'svg')
XLINK_HREF = inkex.addNS('href', 'xlink')


fmt_f = "{:f}".format


@contextmanager
def temp_fn(*args, **kw):
    fd, fn = tempfile.mkstemp(*args, **kw)
    os.close(fd)
    try:
        yield fn
    finally:
        os.unlink(fn)


def png_dimensions(png_data):
    assert len(png_data) >= 24
    assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
    assert png_data[12:16] == b'IHDR'
    width, height = struct.unpack(">LL", png_data[16:24])
    return width, height


class CreateInset(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--tab")
        self.OptionParser.add_option("--scale", type="float",
                                     default=0.5)
        self.OptionParser.add_option("--dpi", type="float",
                                     default=144.0)
        self.OptionParser.add_option("--background", type="string",
                                     default="#ffffff")
        self.OptionParser.add_option("--background-opacity", type="float",
                                     default=1.0)
        self.OptionParser.add_option("--optipng-level", type="int",
                                     default=2)
        self.OptionParser.add_option("--verbose", type="inkbool",
                                     default=False)

    def run(self, cmd, fail_ok=False):
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            if ex.output:
                inkex.errormsg(ex.output)
            inkex.errormsg(ex)
            if not fail_ok:
                raise
        else:
            if self.options.verbose:
                inkex.errormsg(output)

    def export_png(self):
        document = self.document
        selected = self.selected
        opt = self.options

        inkscape_args = [
            '--export-background', opt.background,
            '--export-background-opacity', fmt_f(opt.background_opacity),
            '--export-dpi', fmt_f(opt.scale * opt.dpi),
            ]

        if len(selected) == 0:
            inkex.errormsg(_("You must select at least one object."))
            exit(1)
        elif len(selected) == 1:
            inkscape_args.extend([
                '--export-id', selected.keys()[0],
                ])
        else:
            xmin, xmax, ymin, ymax = simpletransform.computeBBox(
                selected.values())
            svg = document.getroot()
            height = self.unittouu(svg.get('height'))
            # Flip origins for UL to LL corner
            x0, y0 = xmin, height - ymax
            x1, y1 = xmax, height - ymin
            inkscape_args.extend([
                '--export-area', ":".join(map(fmt_f, (x0, y0, x1, y1))),
                ])

        with temp_fn(suffix=".svg", prefix="bh-") as infn:
            with open(infn, "w") as fp:
                document.write(fp)
            with temp_fn(suffix=".png", prefix="bh-") as outfn:
                self.run(['inkscape', '--file', infn, '--export-png', outfn]
                         + inkscape_args)
                if opt.optipng_level >= 0:
                    self.run(['optipng',
                              '-o', str(opt.optipng_level), outfn],
                             fail_ok=True)
                with open(outfn, 'rb') as fp:
                    return fp.read()

    def effect(self):
        dpi = self.options.dpi
        png_data = self.export_png()
        png_w, png_h = png_dimensions(png_data)
        width = png_w * 96.0 / dpi
        height = png_h * 96.0 / dpi

        image = inkex.etree.SubElement(
            self.document.getroot(),
            SVG_IMAGE,
            width=fmt_f(width),
            height=fmt_f(height),
            x=fmt_f(self.view_center[0] - width / 2),
            y=fmt_f(self.view_center[1] - height / 2),
            # XXX: Inkscape normally sets preserveAspectRatio=none
            # which allows the image to be scaled arbitrarily.
            # SVG default is preserveAspectRatio=xMidYMid, which
            # preserve the image aspect ratio on scaling and seems
            # to make more sense for us.
            #
            # preserveAspectRatio="none",
            style="image-rendering:optimizeQuality",
            )
        image.set(XLINK_HREF,
                  'data:image/png;base64,' + base64.b64encode(png_data))


if __name__ == '__main__':
    CreateInset().affect()
