#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Randomize the position of selected elements

'''
from collections import namedtuple
from functools import update_wrapper
from itertools import count
import random

from lxml import etree

import inkex
import simpletransform


inkex.localize()

BH_NS = 'http://dairiki.org/barnhunt/inkscape-extensions'
BH_RAT_EXCLUSION = etree.QName(BH_NS, 'rat-exclusion')

NSMAP = inkex.NSS.copy()
NSMAP['bh'] = BH_NS


class Point(namedtuple('Point', ['x', 'y'])):
    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            args = args[0]
        return super(Point, cls).__new__(cls, *args, **kwargs)

    def __sub__(self, other):
        if not isinstance(other, Point):
            raise TypeError()
        return Offset(dx=self.x - other.x, dy=self.y - other.y)


class Offset(namedtuple('Offset', ['dx', 'dy'])):
    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            args = args[0]
        return super(Offset, cls).__new__(cls, *args, **kwargs)


class Dimension(namedtuple('Point', ['width', 'height'])):
    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            args = args[0]
        return super(Dimension, cls).__new__(cls, *args, **kwargs)


class BoundingBox(namedtuple('BoundingBox', ['xmin', 'xmax', 'ymin', 'ymax'])):
    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            args = args[0]
        return super(BoundingBox, cls).__new__(cls, *args, **kwargs)

    @property
    def width(self):
        return self.xmax - self.xmin

    @property
    def height(self):
        return self.ymax - self.ymin

    @property
    def dimension(self):
        return Dimension(width=self.xmax - self.xmin,
                         height=self.ymax - self.ymin)

    @property
    def ul(self):
        return Point(x=self.xmin, y=self.ymin)

    @property
    def lr(self):
        return Point(x=self.xmax, y=self.ymax)

    def __sum__(self, other):
        if not isinstance(other, BoundingBox):
            raise TypeError()
        return BoundingBox(simpletransform.boxunion(self, other))

    def overlaps(self, other):
        return (self.xmin <= other.xmax
                and self.ymin <= other.ymax
                and other.xmin <= self.xmax
                and other.ymin <= self.ymax)


class Transform(tuple):
    def __new__(cls, transform=None):
        if transform is None:
            transform = ((1, 0, 0), (0, 1, 0))
        elif isinstance(transform, basestring):
            transform = simpletransform.parseTransform(transform)
        elif isinstance(transform, Transform):
            # FIXME: better type checking
            pass
        return tuple.__new__(cls, transform)

    @classmethod
    def offset(cls, offset):
        offset = Offset(offset)
        return cls(((1, 0, offset.dx),
                    (0, 1, offset.dy)))

    def inverse(self):
        return Transform(simpletransform.invertTransform(self))

    def __mul__(self, other):
        if isinstance(other, Transform):
            return Transform(
                simpletransform.composeTransform(self, other))
        elif isinstance(other, Point):
            (a11, a12, a13), (a21, a22, a23) = self
            return Point(x=a11 * other.x + a12 * other.y + a13,
                         y=a21 * other.x + a22 * other.y + a23)
        elif isinstance(other, Offset):
            (a11, a12, _), (a21, a22, _) = self
            return Offset(dx=a11 * other.dx + a12 * other.dy,
                          dy=a21 * other.dx + a22 * other.dy)
        else:
            raise TypeError()

    def __str__(self):
        (a11, a12, a13), (a21, a22, a23) = self
        if (a11, a12, a21, a22) == (1, 0, 0, 1):
            return "translate(%f,%f)" % (a13, a23)
        else:
            return simpletransform.formatTransform(self)

    def __repr__(self):
        return "%s%r" % (self.__class__.__name__, tuple(self))


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


def lineage(elem):
    while elem:
        yield elem
        elem = elem.parent


def composed_transform(elem, transform=None):
    return reduce(lambda transform, el: el.transform * transform,
                  lineage(elem),
                  Transform(transform))


class Element(object):
    """ Helper for element placement """
    def __init__(self, element):
        self.element = element

    @property
    def transform(self):
        return Transform(self.element.get('transform'))

    @transform.setter
    def transform(self, newval):
        if not isinstance(newval, basestring):
            newval = str(Transform(newval))
        return self.element.set('transform', newval)

    @property
    def parent(self):
        parent = self.element.getparent()
        if parent is not None:
            return Element(parent)

    def compute_bbox(self, transform=None):
        t = composed_transform(self.parent, transform)
        return BoundingBox(simpletransform.computeBBox([self.element], t))

    @reify
    def bbox(self):
        return self.compute_bbox()

    @property
    def position(self):
        return self.bbox.ul

    @position.setter
    def position(self, newpos):
        offset = Point(newpos) - self.position
        local_offset = composed_transform(self.parent).inverse() * offset
        self.transform = Transform.offset(local_offset) * self.transform
        self._clear_cache()

    def _clear_cache(self):
        """Delete cached values."""
        # Reset all reified values
        cls = self.__class__
        for name in dir(cls):
            if isinstance(getattr(cls, name), reify):
                delattr(self, name)


def random_position(dim, bounds, exclusions=[], max_tries=128):
    """Find a random new position for element.

    The element has dimensions given by DIM.  The new position will
    be contained within BOUNDS, if possible.  Reasonable efforts will
    be made to avoid placing the element such that it overlaps with
    any bboxes listed in EXCLUSIONS.

    """
    xmax = max(bounds.xmax - dim.width, bounds.xmin)
    ymax = max(bounds.ymax - dim.height, bounds.ymin)
    for n in count(1):
        # Compute random position offset
        x = random.uniform(bounds.xmin, xmax)
        y = random.uniform(bounds.ymin, ymax)
        new_bbox = BoundingBox(x, x + dim.width, y, y + dim.height)
        if not any(new_bbox.overlaps(excl) for excl in exclusions):
            break
        elif n > max_tries:
            inkex.errormsg(
                "Can not find non-excluded location for rat after %d tries. "
                "Giving up." % n)
            break
    return x, y


def find_exclusions(elem, transform=None):
    exclusions = []

    if elem.getparent() is None:
        base = "/svg:svg/*[not(self::svg:defs)]/descendant-or-self::"
        is_hidden = ("ancestor::svg:g[@inkscape:groupmode='layer']"
                     "[contains(@style,'display:none')]")
        cond = "[not({is_hidden})]".format(is_hidden=is_hidden)
    else:
        base = "./descendant-or-self::"
        cond = ""

    path = '|'.join(base + s + cond for s in [
        "*[@bh:rat-exclusion]",
        "svg:use[starts-with(@xlink:href,'#')]",
        ])

    for el in elem.xpath(path, namespaces=NSMAP):
        if el.get(BH_RAT_EXCLUSION) is not None:
            exclusions.append(Element(el).compute_bbox(transform))
        else:
            assert el.tag == inkex.addNS('use', 'svg')
            href = el.get(inkex.addNS('href', 'xlink'))
            assert href.startswith('#') and len(href) > 1

            local_tfm = composed_transform(Element(el), transform)
            for node in elem.xpath('//*[@id=$ref_id]', ref_id=href[1:]):
                exclusions.extend(find_exclusions(node, local_tfm))
    return exclusions


def make_auto_exclusion(bbox):
    excl = inkex.etree.Element(
        inkex.addNS('rect', 'svg'),
        x="%f" % bbox.xmin,
        y="%f" % bbox.ymin,
        width="%f" % bbox.width,
        height="%f" % bbox.height,
        # style='display:none;fill:#9bff00;stroke:#ff0000ff;stroke-width:1px',
        style='fill:#b3c895;fill-opacity:0.25;stroke:#ff0000;stroke-width:1px',
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
        return BoundingBox(0, xmax, 0, ymax)

    def get_boundary(self):
        document = self.document
        bbox = None
        for el in document.xpath('//*[@bh:rat-boundary]', namespaces=NSMAP):
            boundary = Element(el)
            if bbox is None:
                bbox = boundary.bbox
            else:
                bbox += boundary.bbox
        if bbox is None:
            bbox = self.get_page_boundary()
        return bbox

    def get_exclusions(self):
        return find_exclusions(self.document.getroot())

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

        # FIXME: only do this for exclusions which are not visible?
        # for excl in exclusions:
        #     self.exclusion_layer.append(make_auto_exclusion(excl))

        rats = [Element(el) for el in self.selected.values()]
        for rat in rats:
            # Add an exclusion rectangle for the current rat position
            if not any(rat.bbox.overlaps(excl) for excl in exclusions):
                self.exclusion_layer.append(make_auto_exclusion(rat.bbox))
            exclusions.append(rat.bbox)

        for rat in rats:
            newpos = random_position(rat.bbox.dimension, bounds, exclusions)
            rat.position = newpos
            self.exclusion_layer.append(make_auto_exclusion(rat.bbox))
            exclusions.append(rat.bbox)


if __name__ == '__main__':
    HideRats().affect()
