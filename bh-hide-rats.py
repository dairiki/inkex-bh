#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Randomize the position of selected elements

'''
import collections
from functools import update_wrapper
from itertools import count
import random

import inkex
import simpletransform


inkex.localize()


NSMAP = inkex.NSS.copy()
NSMAP['bh'] = 'http://dairiki.org/barnhunt/inkscape-extensions'


def debug(message):
    inkex.errormsg(message)


_BBoxBase = collections.namedtuple('_bounds', ['xmin', 'xmax', 'ymin', 'ymax'])


class BBox(_BBoxBase):
    def __new__(typ, *args):
        if len(args) == 1:
            args = args[0]
        return _BBoxBase.__new__(typ, *args)

    @property
    def width(self):
        return self.xmax - self.xmin

    @property
    def height(self):
        return self.ymax - self.ymin

    def overlaps(self, other):
        return (self.xmin <= other.xmax
                and self.ymin <= other.ymax
                and other.xmin <= self.xmax
                and other.ymin <= self.ymax)

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


E = [[1, 0, 0], [0, 1, 0]]


class reify(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped
        update_wrapper(self, wrapped)

    def __get__(self, inst, objtype=None):
        if inst is None:
            return self
        val = self.wrapped(inst)
        setattr(inst, self.wrapped.__name__, val)
        return val


class Rat(object):
    """ Helper for element placement """
    def __init__(self, element):
        self.element = element

    @reify
    def parent_transform(self):
        parent = self.element.getparent()
        mat = E
        while parent is not None:
            trans = parent.get('transform')
            if trans:
                trans = simpletransform.parseTransform(trans)
                mat = simpletransform.composeTransform(trans, mat)
            parent = parent.getparent()
        return mat

    @reify
    def bbox(self):
        return BBox(simpletransform.computeBBox([self.element],
                                                self.parent_transform))

    def _clear_cache(self):
        del self.parent_transform
        del self.bbox

    @property
    def width(self):
        bbox = self.bbox
        return bbox.xmax - bbox.xmin

    @property
    def height(self):
        bbox = self.bbox
        return bbox.ymax - bbox.ymin

    @property
    def position(self):
        bbox = self.bbox
        return bbox.xmin, bbox.ymin

    @position.setter
    def position(self, (newx, newy)):
        x, y = self.position
        offset = [newx - x, newy - y]
        inv_trfm = simpletransform.invertTransform(self.parent_transform)
        simpletransform.applyTransformToPoint(inv_trfm, offset)
        local_trfm = [[1, 0, offset[0]],
                      [0, 1, offset[1]]]
        simpletransform.applyTransformToNode(local_trfm, self.element)
        self._clear_cache()


def random_position(bbox, bounds, exclusions=[], max_tries=32):
    """Find a random new position for element.

    The element has dimensions given by BBOX.  The new position will
    be contained within BOUNDS, if possible.  Reasonable efforts will
    be made to avoid placing the element such that it overlaps with
    any bboxes listed in EXCLUSIONS.

    """
    xmax = max(bounds.xmax - bbox.width, bounds.xmin)
    ymax = max(bounds.ymax - bbox.height, bounds.ymin)
    for n in count(1):
        # Compute random position offset
        x = random.uniform(bounds.xmin, xmax)
        y = random.uniform(bounds.ymin, ymax)
        new_bbox = BBox(x, x + bbox.width, y, y + bbox.height)
        if not any(new_bbox.overlaps(excl) for excl in exclusions):
            break
        elif n > max_tries:
            inkex.errormsg(
                "Can not find non-excluded location for rat after %d tries. "
                "Giving up." % n)
            break
    return x, y


def make_auto_exclusion(bbox):
    excl = inkex.etree.Element(
        inkex.addNS('rect', 'svg'),
        x="%f" % bbox.xmin,
        y="%f" % bbox.ymin,
        width="%f" % bbox.width,
        height="%f" % bbox.height,
        # style='display:none;fill:#9bff00;stroke:#ff0000ff;stroke-width:1px',
        style='fill:#9bff0035;fill-opacity:0.2;stroke:#ff0000;stroke-width:1px',
        )
    excl.set("{%s}rat-exclusion" % NSMAP['bh'], 'auto')
    # "lock" the exclusion
    excl.set("{%s}insensitive" % NSMAP['sodipodi'], 'true')
    return excl


class HideRats(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--tab")
        self.OptionParser.add_option("--restart", type="inkbool")
        self.OptionParser.add_option("--verbose", type="inkbool")

    def get_page_boundary(self):
        svg = self.document.getroot()
        xmax = self.unittouu(svg.attrib['width'])
        ymax = self.unittouu(svg.attrib['height'])
        return BBox(0, xmax, 0, ymax)

    def get_boundary(self):
        document = self.document
        bbox = None
        for el in document.xpath('//*[@bh:rat-boundary]', namespaces=NSMAP):
            trfm = context_transform(el)
            el_bbox = simpletransform.computeBBox([el], trfm)
            bbox = simpletransform.boxunion(bbox, el_bbox)

        if bbox is None:
            bbox = self.get_page_boundary()
        return BBox(bbox)

    def get_exclusions(self):
        document = self.document
        exclusions = []
        for el in document.xpath('//*[@bh:rat-exclusion]', namespaces=NSMAP):
            exclusions.append(Rat(el).bbox)
        return exclusions

    @reify
    def exclusion_layer(self):
        document = self.document
        r = document.xpath("//svg:g[@bh:rat-exclusion-layer]",
                           namespaces=NSMAP)
        if r:
            return r[0]
        g = inkex.etree.Element(
            inkex.addNS('g', 'svg'))
        g.set("{%s}rat-exclusion-layer" % NSMAP['bh'], 'true')
        g.set("{%s}groupmode" % NSMAP['inkscape'], 'layer')
        g.set("{%s}label" % NSMAP['inkscape'], '[h] ' + _('Rat auto-exclusions'))
        # "lock" layer
        g.set("{%s}insensitive" % NSMAP['sodipodi'], 'true')
        document.getroot().append(g)
        return g

    def cleanup_exclusions(self):
        document = self.document
        for el in document.xpath("//svg:g[@bh:rat-exclusion-layer]",
                                 namespaces=NSMAP):
            el.getparent().remove(el)

    def effect(self):
        if self.options.restart:
            self.cleanup_exclusions()

        bounds = self.get_boundary()
        exclusions = self.get_exclusions()

        rats = [Rat(el) for el in self.selected.values()]
        for rat in rats:
            # Add an exclusion rectangle for the current rat position
            if not any(rat.bbox.overlaps(excl) for excl in exclusions):
                self.exclusion_layer.append(make_auto_exclusion(rat.bbox))
            exclusions.append(rat.bbox)

        for rat in rats:
            newpos = random_position(rat.bbox, bounds, exclusions)
            rat.position = newpos
            self.exclusion_layer.append(make_auto_exclusion(rat.bbox))
            exclusions.append(rat.bbox)


if __name__ == '__main__':
    HideRats().affect()
