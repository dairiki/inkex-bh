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

from lxml import etree

import inkex

inkex.localize()
_ = _                           # noqa: F821

SVG_SVG = inkex.addNS('svg', 'svg')
SVG_IMAGE = inkex.addNS('image', 'svg')
XLINK_HREF = inkex.addNS('href', 'xlink')

BH_NS = 'http://dairiki.org/barnhunt/inkscape-extensions'
BH_INSET_EXPORT_ID = etree.QName(BH_NS, 'inset--export-id')
BH_INSET_VISIBLE_LAYERS = etree.QName(BH_NS, 'inset--visible-layers')

NSMAP = inkex.NSS.copy()
NSMAP['bh'] = BH_NS


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


class Style(dict):
    def __init__(self, style=None):
        if style is not None:
            for piece in style.split(';'):
                prop, sep, value = piece.partition(':')
                if sep:
                    self[prop.strip()] = value.strip()

    def __str__(self):
        return ';'.join(map("{0[0]}:{0[1]}".format, self.items()))


class TemporaryVisibility(object):
    def __init__(self):
        self.saved = []

    def __call__(self, elem, visibility):
        elem_style = elem.get('style')
        if elem_style or not visibility:
            self.saved.append((elem, elem_style))
            style = Style(elem_style)
            style['display'] = 'inline' if visibility else 'none'
            elem.set('style', str(style))

    def restore(self):
        for elem, style in reversed(self.saved):
            if style is None:
                elem.attrib.pop('style', None)
            else:
                elem.set('style', style)
        self.saved = []

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        self.restore()


def iter_layers(tree):
    return tree.xpath("//svg:g[@inkscape:groupmode='layer']",
                      namespaces=NSMAP)


def is_visible(elem):
    while elem is not None:
        style = Style(elem.get('style'))
        if style.get('display') == 'none':
            return False
        elem = elem.getparent()
    return True


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
            inkex.errormsg(str(ex))
            if not fail_ok:
                exit(1)
        else:
            if self.options.verbose:
                inkex.errormsg(output)

    def export_png(self, export_id, document=None):
        opt = self.options
        if document is None:
            document = self.document

        with temp_fn(suffix=".svg", prefix="bh-") as infn:
            with open(infn, "w") as fp:
                document.write(fp)
            with temp_fn(suffix=".png", prefix="bh-") as outfn:
                self.run([
                    'inkscape',
                    '--file', infn,
                    '--export-png', outfn,
                    '--export-id', export_id,
                    '--export-background', opt.background,
                    '--export-background-opacity', fmt_f(
                        opt.background_opacity),
                    '--export-dpi', fmt_f(opt.scale * opt.dpi),
                    ])
                if opt.optipng_level >= 0:
                    self.run(['optipng',
                              '-o', str(opt.optipng_level), outfn],
                             fail_ok=True)
                with open(outfn, 'rb') as fp:
                    return fp.read()

    def effect(self):
        if len(self.selected) != 1:
            inkex.errormsg(_("You must select exactly one object."))
            exit(1)
        selected_id, selected_elem = next(iter(self.selected.items()))

        inset_selected = (selected_elem.tag == SVG_IMAGE
                          and selected_elem.get(BH_INSET_EXPORT_ID))
        if not inset_selected:
            # Selected element was not an inset image.
            # Create PNG from selected element
            image = None
            export_id = selected_id
            visible_layer_ids = set(
                layer.get('id')
                for layer in iter_layers(self.document)
                if is_visible(layer) and layer.get('id') is not None)
            png_data = self.export_png(export_id)
        else:
            # Previously created inset image was selected.
            # Attempt to re-create/update the image.
            image = selected_elem
            export_id = image.get(BH_INSET_EXPORT_ID)
            visible_layer_ids = set(
                image.get(BH_INSET_VISIBLE_LAYERS, '').split())
            with TemporaryVisibility() as set_visibility:
                set_visibility(image, False)  # hide inset image
                for layer in iter_layers(self.document):
                    visibility = layer.get('id') in visible_layer_ids
                    set_visibility(layer, visibility)
                png_data = self.export_png(export_id)

        png_w, png_h = png_dimensions(png_data)
        image_scale = 96.0 / self.options.dpi
        width = png_w * image_scale
        height = png_h * image_scale

        if image is None:
            # Create new image element, centered on view
            image = inkex.etree.SubElement(
                self.document.getroot(), SVG_IMAGE,
                x=fmt_f(self.view_center[0] - width / 2),
                y=fmt_f(self.view_center[1] - height / 2))

        image.attrib.update({
            'width': fmt_f(width),
            'height': fmt_f(height),
            XLINK_HREF: 'data:image/png;base64,' + base64.b64encode(png_data),
            BH_INSET_EXPORT_ID: export_id,
            BH_INSET_VISIBLE_LAYERS: ' '.join(visible_layer_ids),
            'style': "image-rendering:optimizeQuality",
            # Inkscape normally sets preserveAspectRatio=none
            # which allows the image to be scaled arbitrarily.
            # SVG default is preserveAspectRatio=xMidYMid, which
            # preserve the image aspect ratio on scaling and seems
            # to make more sense for us.
            'preserveAspectRatio': "xMidYMid",
            })


if __name__ == '__main__':
    CreateInset().affect()
