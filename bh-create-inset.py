#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Export bbox of selection to PNG image

'''
import base64
from contextlib import contextmanager
import os
from subprocess import check_call
import sys
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

    def export_png(self, bbox,
                   dpi=144,
                   background='#ffffff',
                   background_opacity=1.0,
                   verbose=False):
        stdout = sys.stderr if verbose else open(os.devnull, 'wb')
        document = self.document
        xmin, xmax, ymin, ymax = bbox
        svg = document.getroot()
        height = self.unittouu(svg.get('height'))
        # Flip origins for UL to LL corner
        x0, y0 = xmin, height - ymax
        x1, y1 = xmax, height - ymin

        with temp_fn(suffix=".svg", prefix="bh-") as infn:
            with open(infn, "w") as fp:
                document.write(fp)
            with temp_fn(suffix=".png", prefix="bh-") as outfn:
                cmd = [
                    'inkscape',
                    '--export-png', outfn,
                    '--export-area', ":".join(map(fmt_f, (x0, y0, x1, y1))),
                    '--export-background', str(background),
                    '--export-background-opacity', fmt_f(background_opacity),
                    '--export-dpi', fmt_f(dpi),
                    infn,
                    ]
                check_call(cmd, stdout=stdout)
                with open(outfn, 'rb') as fp:
                    return fp.read()

    def effect(self):
        if len(self.selected) == 0:
            inkex.errormsg(_("You must select at least one object."))
            exit(1)
        bbox = simpletransform.computeBBox(self.selected.values())

        scale = self.options.scale
        png_data = self.export_png(
            bbox,
            dpi=scale * self.options.dpi,
            background=self.options.background,
            background_opacity=self.options.background_opacity)

        xmin, xmax, ymin, ymax = bbox
        width = scale * (xmax - xmin)
        height = scale * (ymax - ymin)
        image = inkex.etree.SubElement(
            self.document.getroot(),
            SVG_IMAGE,
            width=fmt_f(width),
            height=fmt_f(height),
            x=fmt_f(self.view_center[0] - width / 2),
            y=fmt_f(self.view_center[1] - height / 2),
            preserveAspectRatio="none",  # FIXME: is this what is wanted?
            style="image-rendering:optimizeQuality"
            )
        image.set(XLINK_HREF,
                  'data:image/png;base64,' + base64.encodestring(
                      png_data).rstrip())


if __name__ == '__main__':
    CreateInset().affect()
