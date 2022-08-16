#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Randomize the position of selected elements

'''
from collections import namedtuple
from functools import reduce, update_wrapper
from itertools import count
from operator import add
import random
import re

from lxml import etree

import inkex
from inkex.localization import inkex_gettext as _
#import simpletransform

SVG_SVG = inkex.addNS('svg', 'svg')
SVG_G = inkex.addNS('g', 'svg')
SVG_USE = inkex.addNS('use', 'svg')
SVG_RECT = inkex.addNS('rect', 'svg')
INKSCAPE_GROUPMODE = inkex.addNS('groupmode', 'inkscape')
INKSCAPE_LABEL = inkex.addNS('label', 'inkscape')
SODIPODI_INSENSTIVE = inkex.addNS('insensitive', 'sodipodi')
XLINK_HREF = inkex.addNS('href', 'xlink')

NSMAP = {
    **inkex.NSS,
    "bh": "http://dairiki.org/barnhunt/inkscape-extensions",
}
BH_RAT_PLACEMENT = f"{{{NSMAP['bh']}}}rat-placement"
BH_RAT_GUIDE_MODE = f"{{{NSMAP['bh']}}}rat-guide-mode"


def _xp_str(s):
    for quote in '"', "'":
        if quote not in s:
            return f"{quote}{s}{quote}"
    strs = re.findall('[^"]+|[^\']+', s)
    assert ''.join(strs) == s
    return f"concat({','.join(map(_xp_str, strs))})"


def containing_layer(elem):
    """Return svg:g element for the layer containing elem or None if there is no such layer.
    """
    layers = elem.xpath(
        "./ancestor::svg:g[@inkscape:groupmode='layer'][position()=1]",
        namespaces=NSMAP)
    if layers:
        return layers[0]
    return None


class RatGuide(object):
    BOUNDARY_STYLE = (
        'fill:none;'
        'stroke:#00ff00;stroke-width:2;stroke-dasharray:4,8;'
        'stroke-linecap:round;stroke-miterlimit:4')
    EXCLUSION_STYLE = (
        'fill:#c68c8c;fill-opacity:0.125;'
        'stroke:#ff0000;stroke-width:1;stroke-opacity:0.5;'
        'stroke-dasharray:2,6;'
        'stroke-linecap:round;stroke-miterlimit:4')

    def __init__(self, document, page_bbox, parent_layer=None):
        self.document = document
        self.page_bbox = page_bbox

        if parent_layer is not None:
            parent = parent_layer
        else:
            parent = document.getroot()
        existing = parent.xpath(".//svg:g[@bh:rat-guide-mode='layer']",
                                namespaces=NSMAP)
        if existing:
            self.guide_layer = existing[0]
        else:
            self.guide_layer = self._create_guide_layer()
            parent.append(self.guide_layer)
            self._populate_guide_layer()

    def _create_guide_layer(self):
        layer = etree.Element(SVG_G)
        layer.attrib.update({
            INKSCAPE_LABEL: '[h] %s' % _('Rat Placement Guides'),
            INKSCAPE_GROUPMODE: 'layer',
            BH_RAT_GUIDE_MODE: 'layer',
            SODIPODI_INSENSTIVE: 'true',
            })
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
            self.document.xpath("//*[@bh:rat-placement='boundary']",
                                namespaces=NSMAP))

    def _compute_boundary(self, elems):
        # FIXME: transform
        bboxes =[el.bounding_box(transform=None) for el in elems]
        if bboxes:
            return reduce(add, bboxes)
        else:
            return self.page_bbox

    def reset(self):
        guide_layer = self.guide_layer
        # delete all auto-created elements
        for el in guide_layer.xpath(".//*[@bh:rat-guide-mode]",
                                    namespaces=NSMAP):
            el.getparent().remove(el)
        self._populate_guide_layer()

    def add_exclusion(self, bbox):
        rect = make_rect(bbox)
        rect.attrib.update({
            BH_RAT_GUIDE_MODE: 'exclusion',
            'style': self.EXCLUSION_STYLE,
            })
        self.guide_layer.append(rect)

    def get_boundary(self):
        return self._compute_boundary(
            self.guide_layer.xpath(".//*[@bh:rat-guide-mode='boundary']",
                                   namespaces=NSMAP))

    def get_exclusions(self):
        elems = self.guide_layer.xpath(
            ".//*[@bh:rat-guide-mode='exclusion']"
            # Treat top-level elements created in the guide layer by
            # the user as exclusions
            " | ./*[not(@bh:rat-guide-mode)]",
            namespaces=NSMAP
        )
        # FIXME: transform
        return [el.bounding_box(transform=None) for el in elems]


# FIXME: move this
def make_rect(bbox):
    return inkex.Rectangle.new(bbox.left, bbox.top, bbox.width, bbox.height)


# FIXME: move this
def find_exclusions(elem, transform=None):
    if elem.getparent() is None:
        base = "/svg:svg/*[not(self::svg:defs)]/descendant-or-self::"
        is_hidden = ("ancestor::svg:g[@inkscape:groupmode='layer']"
                     "[contains(@style,'display:none')]")
        cond = f"[not({is_hidden})]"
    else:
        base = "./descendant-or-self::"
        cond = ""

    path = '|'.join(base + s + cond for s in [
        "*[@bh:rat-placement='exclude']",
        "svg:use[starts-with(@xlink:href,'#')]",
        ])

    for el in elem.xpath(path, namespaces=NSMAP):
        if el.get(BH_RAT_PLACEMENT) == 'exclude':
            yield el.bounding_box(transform=transform)
        else:
            assert el.tag == SVG_USE
            href = el.get(XLINK_HREF)
            assert href.startswith('#') and len(href) > 1

            local_tfm = el.transform @ inkex.Transform(transform)
            raise RuntimeError(f"elem = {elem!r}")
            for node in elem.xpath(f'//*[@id={_xp_str(href[1:])}]'):
                yield from find_exclusions(node)



class RatPlacer(object):
    def __init__(self, boundary, exclusions=None):
        if exclusions is None:
            exclusions = []
        self.boundary = boundary
        self.exclusions = exclusions

    def add_exclusion(self, bbox):
        self.exclusions.append(bbox)

    def place_rat(self, rat):
        # FIXME: check for symbol?
        #if not isinstance(rat, Element):
        #    raise TypeError("rat must be an Element")

        # FIXME: transform
        rat_bbox = rat.bounding_box(transform=None)
        top, left = self.random_position(rat_bbox)
        itrans = rat.getparent().composed_transform().__neg__()
        local_offset = itrans.add_translate(
            left - rat_bbox.left, top - rat_bbox.top
        )
        rat.transform @= local_offset

    def intersects_excluded(self, bbox):
        return any((bbox & excl) for excl in self.exclusions)

    def random_position(self, rat_bbox, max_tries=128):
        """Find a random new position for element.

        The element has dimensions given by DIMENSION.  The new position will
        be contained within BOUNDARY, if possible.  Reasonable efforts will
        be made to avoid placing the element such that it overlaps with
        any bboxes listed in EXCLUSIONS.

        """
        # FIXME: this needs cleanup
        boundary = inkex.BoundingBox.new_xywh(
            self.boundary.left,
            self.boundary.top,
            self.boundary.width - rat_bbox.width,
            self.boundary.height - rat_bbox.height
            )
        boundary &= self.boundary
        inkex.errormsg(
            f"boundary: {self.boundary!r} - {rat_bbox!r} = {boundary!r}"
        )
        inkex.errormsg(
            f"exclusions: {len(self.exclusions)}"
        )
        for ex in self.exclusions:
            inkex.errormsg(f"ex: {ex!r}")
                

        for n in count(1):
            # Compute random position offset
            x = random.uniform(boundary.left, boundary.right)
            y = random.uniform(boundary.top, boundary.bottom)
            new_bbox = inkex.BoundingBox.new_xywh(
                x, y, rat_bbox.width, rat_bbox.height
            )
            if not self.intersects_excluded(new_bbox):
                break
            elif n >= max_tries:
                inkex.errormsg(
                    "Can not find non-excluded location for rat after %d "
                    "tries. Giving up." % n)
                break
        return x, y


class HideRats(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--restart", type=inkex.Boolean)
        pars.add_argument("--newblind", type=inkex.Boolean)

    def get_page_boundary(self):
        svg = self.document.getroot()
        inkex.errormsg(f"page_boundary: {svg.get_page_bbox()!r}")
        return svg.get_page_bbox()

    def get_rat_layer(self, rats):
        rat_layers = set(map(containing_layer, rats))
        if len(rat_layers) == 0:
            raise RuntimeError("No rats selected")
        if len(rat_layers) != 1:
            raise RuntimeError("Rats are not all on the same layer")
        layer = rat_layers.pop()
        if layer is None:
            raise RuntimeError("Rats are not on a layer")
        return layer

    def clone_blind(self, rat_layer, rats):
        new_rats = set()

        def _clone(elem):
            attrib = dict(elem.attrib)
            attrib.pop('id', None)
            copy = etree.Element(elem.tag, attrib)
            copy.text = elem.text
            copy.tail = elem.tail
            copy[:] = map(_clone, elem)
            if elem in rats:
                new_rats.add(copy)
            return copy
            
        new_layer = _clone(rat_layer)

        # compute name for new layer
        names = set()
        max_idx = 0
        for label in rat_layer.xpath(
                "../svg:g[@inkscape:groupmode='layer']/@inkscape:label",
                namespaces=NSMAP
        ):
            m = re.match(r'^(\[o.*?\].*?)\s+(\d+)\s*$', label)
            if m:
                name, idx = m.groups()
                names.add(name)
                max_idx = max(max_idx, int(idx))
        if len(names) == 1:
            name = names.pop()
        else:
            name = 'Blind'
        new_layer.attrib[INKSCAPE_LABEL] = "%s %d" % (name, max_idx + 1)

        rat_layer.getparent().insert(0, new_layer)
        rat_layer.attrib['style'] = 'display:none'
        return new_rats
        
    def effect(self):
        rats = self.svg.selection
        rat_layer = self.get_rat_layer(rats)
        assert rat_layer.tag == SVG_G

        guide_layer = RatGuide(self.document,
                               self.get_page_boundary(),
                               parent_layer=containing_layer(rat_layer))
        if self.options.restart or self.options.newblind:
            # FIXME:
            guide_layer.reset()

        if self.options.newblind:
            rats = self.clone_blind(rat_layer, rats)

        bounds = guide_layer.get_boundary()
        exclusions = guide_layer.get_exclusions()
        rat_placer = RatPlacer(bounds, exclusions)

        for rat in rats:
            #rat = Element(el)
            rat_placer.place_rat(rat)
            # FIXME: transform
            bbox = rat.bounding_box(transform=None)
            guide_layer.add_exclusion(bbox)
            rat_placer.add_exclusion(bbox)


if __name__ == '__main__':
    HideRats().run()
