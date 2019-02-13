#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Randomize the position of selected elements

'''
# standard library
import collections
import random
# local library
import inkex
import simpletransform


inkex.localize()


NSMAP = inkex.NSS.copy()
NSMAP['bh'] = 'http://dairiki.org/barnhunt/inkscape-extensions'


def debug(message):
    inkex.errormsg(message)


_bounds = collections.namedtuple('_bounds', ['xmin', 'xmax', 'ymin', 'ymax'])


class bounds(_bounds):
    def __new__(typ, *args):
        if len(args) == 1:
            args = args[0]
        return _bounds.__new__(typ, *args)

    @property
    def width(self):
        return self.xmax - self.xmin

    @property
    def height(self):
        return self.ymax - self.ymin

    def __repr__(self):
        return tuple.__repr__(self)


def context_transform(el, map=[[1, 0, 0], [0, 1, 0]]):
    """ Get the outer transform in effect for element.

    This includes the transforms of all parent elements, but not the transform
    of the element itself.

    """
    parent = el.getparent()
    if parent is not None:
        map = simpletransform.composeParents(parent, map)
    return map


def randomize_position(el, bbox):
    """ Randomize the position of element within bounding box.
    """
    bbox = bounds(bbox)

    # Work in page coordinates
    local_trfm = context_transform(el)
    el_bbox = bounds(simpletransform.computeBBox([el], local_trfm))

    # Compute random position offset
    x = random.uniform(bbox.xmin, max(bbox.xmax - el_bbox.width, bbox.xmin))
    y = random.uniform(bbox.ymin, max(bbox.ymax - el_bbox.height, bbox.ymin))
    offset = [x - el_bbox.xmin, y - el_bbox.ymin]

    # Transform back to element coordinates
    local_trfm_inv = simpletransform.invertTransform(local_trfm)
    simpletransform.applyTransformToPoint(local_trfm_inv, offset)
    trfm = [[1, 0, offset[0]],
            [0, 1, offset[1]]]
    simpletransform.applyTransformToNode(trfm, el)


class HideRats(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--tab")
        self.OptionParser.add_option("--verbose", type="inkbool")

    def get_page_boundary(self):
        svg = self.document.getroot()
        xmax = self.unittouu(svg.attrib['width'])
        ymax = self.unittouu(svg.attrib['height'])
        return bounds(0, xmax, 0, ymax)

    def get_boundary(self):
        document = self.document
        bbox = None
        for el in document.xpath('//*[@bh:rat-boundary]', namespaces=NSMAP):
            trfm = context_transform(el)
            el_bbox = simpletransform.computeBBox([el], trfm)
            bbox = simpletransform.boxunion(bbox, el_bbox)

        if bbox is None:
            bbox = self.get_page_boundary()
        return bounds(bbox)

    def effect(self):
        bbox = self.get_boundary()
        for el in self.selected.values():
            randomize_position(el, bbox)


if __name__ == '__main__':
    HideRats().affect()
