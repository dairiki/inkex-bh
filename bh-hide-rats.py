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
_ = _                           # noqa: F821

SVG_SVG = inkex.addNS('svg', 'svg')
SVG_G = inkex.addNS('g', 'svg')
SVG_USE = inkex.addNS('use', 'svg')
SVG_RECT = inkex.addNS('rect', 'svg')
INKSCAPE_GROUPMODE = inkex.addNS('groupmode', 'inkscape')
INKSCAPE_LABEL = inkex.addNS('label', 'inkscape')
SODIPODI_INSENSTIVE = inkex.addNS('insensitive', 'sodipodi')
XLINK_HREF = inkex.addNS('href', 'xlink')

BH_NS = 'http://dairiki.org/barnhunt/inkscape-extensions'
BH_RAT_EXCLUSION = etree.QName(BH_NS, 'rat-exclusion')
BH_RAT_GUIDE_MODE = etree.QName(BH_NS, 'rat-guide-mode')

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
    def xml_id(self):
        return self.element.get('id')

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


class RatGuide(object):
    BOUNDARY_STYLE = (
        'fill:#00ff00;fill-opacity:0.02;'
        'stroke:#00ab00:stroke-width:2.5;'
        'stroke-linecap:round;stroke-miterlimit:4')
    EXCLUSION_STYLE = (
        'fill:#c68c8c;fill-opacity:0.25;'
        'stroke:#ff0000:stroke-width:1;'
        'stroke-linecap:round;stroke-miterlimit:4')

    def __init__(self, document, page_bbox):
        self.document = document
        self.page_bbox = page_bbox

        existing = document.xpath("//svg:g[@bh:rat-guide-mode='layer']",
                                  namespaces=NSMAP)
        if existing:
            self.guide_layer = existing[0]
        else:
            self.guide_layer = self._create_guide_layer()
            self._populate_guide_layer()

    def _create_guide_layer(self):
        layer = inkex.etree.Element(SVG_G)
        layer.attrib.update({
            INKSCAPE_LABEL: '[h] %s' % _('Rat Placement Guides'),
            INKSCAPE_GROUPMODE: 'layer',
            BH_RAT_GUIDE_MODE: 'layer',
            SODIPODI_INSENSTIVE: 'true',
            })
        self.document.getroot().append(layer)
        return layer

    def _populate_guide_layer(self):
        # Draw bounding box on guide layer
        bounds = make_rect(self._get_boundary())
        bounds.attrib.update({
            BH_RAT_GUIDE_MODE: 'boundary',
            'style': self.BOUNDARY_STYLE,
            })
        self.guide_layer.insert(0, bounds)

        # Find visible exclusion elements and draw their bounding boxes
        for bbox in find_exclusions(self.document.getroot()):
            # FIXME: add link to original exclusion element?
            self.add_exclusion(bbox)

    def _get_boundary(self):
        return self._compute_boundary(
            self.document.xpath('//*[@bh:rat-boundary]', namespaces=NSMAP))

    def _compute_boundary(self, elems):
        bbox = None
        for el in elems:
            boundary = Element(el)
            if bbox is None:
                bbox = boundary.bbox
            else:
                bbox += boundary.bbox
        if bbox is None:
            bbox = self.page_bbox
        return bbox

    def reset(self):
        guide_layer = self.guide_layer
        # delete all auto-created elements
        for el in guide_layer.xpath(".//*[@bh:rat-guide-mode]",
                                    namespaces=NSMAP):
            el.getparent().remove(el)
        self._populate_guide_layer()

    def add_exclusion(self, bbox, src_id=None):
        rect = make_rect(bbox)
        rect.attrib.update({
            BH_RAT_GUIDE_MODE: 'exclusion',
            'style': self.EXCLUSION_STYLE,
            })
        if src_id is not None:
            href = '#%s' % src_id
            for el in self.guide_layer.xpath(".//*[@xlink:href=$href]",
                                             href=href,
                                             namespaces=NSMAP):
                del el.attrib[XLINK_HREF]
            rect.set(XLINK_HREF, href)
        self.guide_layer.append(rect)

    def exclusion_for_src(self, src_id):
        if src_id is None:
            return None
        href = '#%s' % src_id
        for el in self.guide_layer.xpath(".//*[@xlink:href=$href]",
                                         href=href,
                                         namespaces=NSMAP):
            return Element(el).bbox

    def get_boundary(self):
        return self._compute_boundary(
            self.guide_layer.xpath(".//*[@bh:rat-guide-mode='boundary']",
                                   namespaces=NSMAP))

    def get_exclusions(self):
        res = self.guide_layer.xpath(
            ".//*[@bh:rat-guide-mode='exclusion']"
            # Treat top-level elements created in the guide layer by the user
            # as exclusions
            " | ./*[not(@bh:rat-guide-mode)]",
            namespaces=NSMAP)
        return [Element(excl).bbox for excl in res]


# FIXME: move this
def make_rect(bbox):
    return inkex.etree.Element(SVG_RECT,
                               x="%f" % bbox.xmin,
                               y="%f" % bbox.ymin,
                               width="%f" % bbox.width,
                               height="%f" % bbox.height)


# FIXME: move this
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
            assert el.tag == SVG_USE
            href = el.get(XLINK_HREF)
            assert href.startswith('#') and len(href) > 1

            local_tfm = composed_transform(Element(el), transform)
            for node in elem.xpath('//*[@id=$ref_id]', ref_id=href[1:]):
                exclusions.extend(find_exclusions(node, local_tfm))
    return exclusions


class RatPlacer(object):
    def __init__(self, boundary, exclusions=None):
        if exclusions is None:
            exclusions = []
        self.boundary = boundary
        self.exclusions = exclusions

    def add_exclusion(self, bbox):
        self.exclusions.append(bbox)

    def place_rat(self, rat):
        if not isinstance(rat, Element):
            raise TypeError("rat must be an Element")

        newpos = self.random_position(rat.bbox.dimension)
        rat.position = newpos

    def intersects_excluded(self, bbox):
        return any(bbox.overlaps(excl) for excl in self.exclusions)

    def random_position(self, rat_bbox, max_tries=128):
        """Find a random new position for element.

        The element has dimensions given by DIMENSION.  The new position will
        be contained within BOUNDARY, if possible.  Reasonable efforts will
        be made to avoid placing the element such that it overlaps with
        any bboxes listed in EXCLUSIONS.

        """
        xmin, xmax, ymin, ymax = self.boundary
        xmax = max(xmax - rat_bbox.width, xmin)
        ymax = max(ymax - rat_bbox.height, ymin)

        for n in count(1):
            # Compute random position offset
            x = random.uniform(xmin, xmax)
            y = random.uniform(ymin, ymax)
            new_bbox = BoundingBox(x, x + rat_bbox.width,
                                   y, y + rat_bbox.height)
            if not self.intersects_excluded(new_bbox):
                break
            elif n >= max_tries:
                inkex.errormsg(
                    "Can not find non-excluded location for rat after %d "
                    "tries. Giving up." % n)
                break
        return x, y


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

    def effect(self):
        guide_layer = RatGuide(self.document, self.get_page_boundary())
        if self.options.restart:
            # FIXME:
            guide_layer.reset()

        rats = [Element(el) for el in self.selected.values()]

        bounds = guide_layer.get_boundary()
        exclusions = guide_layer.get_exclusions()
        rat_placer = RatPlacer(bounds, exclusions)

        for rat in rats:
            # Add an exclusion rectangle for the current rat position
            prev_exclusion = guide_layer.exclusion_for_src(rat.xml_id)
            if not prev_exclusion or not prev_exclusion.overlaps(rat.bbox):
                guide_layer.add_exclusion(rat.bbox)
                rat_placer.add_exclusion(rat.bbox)

        for rat in rats:
            rat_placer.place_rat(rat)
            guide_layer.add_exclusion(rat.bbox, rat.xml_id)
            rat_placer.add_exclusion(rat.bbox)


if __name__ == '__main__':
    HideRats().affect()
