#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Export bbox of selection to PNG image

'''
import base64
from contextlib import contextmanager
import copy
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


def get_visible_layer_ids(tree):
    def is_visible(layer):
        style = Style(layer.get('style'))
        return style.get('display') != 'none'

    ids = set()
    for layer in tree.xpath("//svg:g[@id][@inkscape:groupmode='layer']",
                            namespaces=NSMAP):
        lineage = layer.xpath(
            "ancestor-or-self::svg:g[@inkscape:groupmode='layer']",
            namespaces=NSMAP)
        if all(is_visible(lyr) for lyr in lineage):
            ids.add(layer.get('id'))
    return ids


def remove_element_by_id(tree, elem_id):
    for elem in tree.xpath('//*[@id=$elem_id]', elem_id=elem_id):
        elem.getparent().remove(elem)


def adjust_layer_visibility(tree, visible_layer_ids):
    for layer in tree.xpath("//svg:g[@id][@inkscape:groupmode='layer']",
                            namespaces=NSMAP):
        style = Style(layer.get('style'))
        is_visible = layer.get('id') in visible_layer_ids
        style['display'] = 'inline' if is_visible else 'none'
        layer.set('style', str(style))


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

    def export_png(self, tree, export_id):
        opt = self.options

        with temp_fn(suffix=".svg", prefix="bh-") as infn:
            with open(infn, "w") as fp:
                tree.write(fp)
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

        id_, elem = next(iter(self.selected.items()))
        if elem.tag == SVG_IMAGE and elem.get(BH_INSET_EXPORT_ID):
            # Previously created inset image was selected.
            # Attempt to re-create/update the image.
            image_elem = elem
            export_id = elem.get(BH_INSET_EXPORT_ID)
            visible_layer_ids = set(
                elem.get(BH_INSET_VISIBLE_LAYERS, '').split())
            tree = copy.deepcopy(self.document)
            remove_element_by_id(tree, id_)  # remove image
            adjust_layer_visibility(tree, visible_layer_ids)
        else:
            # Selected element was not an inset image.
            # Create PNG from selected element
            image_elem = None
            export_id = id_
            tree = self.document
            visible_layer_ids = get_visible_layer_ids(tree)

        png_data = self.export_png(tree, export_id)
        png_w, png_h = png_dimensions(png_data)
        image_scale = 96.0 / self.options.dpi
        width = png_w * image_scale
        height = png_h * image_scale

        if image_elem is None:
            image_attr = {
                'x': fmt_f(self.view_center[0] - width / 2),
                'y': fmt_f(self.view_center[1] - height / 2),
                # XXX: Inkscape normally sets preserveAspectRatio=none
                # which allows the image to be scaled arbitrarily.
                # SVG default is preserveAspectRatio=xMidYMid, which
                # preserve the image aspect ratio on scaling and seems
                # to make more sense for us.
                #
                # 'preserveAspectRatio': "none",
                'style': "image-rendering:optimizeQuality",
                BH_INSET_EXPORT_ID: export_id,
                BH_INSET_VISIBLE_LAYERS: ' '.join(visible_layer_ids),
                }
            image_elem = inkex.etree.SubElement(
                self.document.getroot(), SVG_IMAGE, image_attr)

        image_elem.attrib.update({
            'width': fmt_f(width),
            'height': fmt_f(height),
            XLINK_HREF: 'data:image/png;base64,' + base64.b64encode(png_data),
            })


if __name__ == '__main__':
    CreateInset().affect()
