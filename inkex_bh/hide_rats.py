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
""" Randomize the position of selected elements

"""
import random
import re
from argparse import ArgumentParser
from functools import reduce
from operator import add
from typing import Iterable
from typing import Iterator
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple

import inkex
from inkex.localization import inkex_gettext as _

from . import debug
from . import typing as types
from ._compat import compose_transforms
from ._compat import Literal
from ._compat import to_dimensionless
from .constants import BH_RAT_GUIDE_MODE
from .constants import BH_RAT_PLACEMENT
from .constants import NSMAP
from .workarounds import text_bbox_hack


SVG_USE = inkex.addNS("use", "svg")


def _xp_str(s: str) -> str:
    """Quote string for use in xpath expression."""
    for quote in '"', "'":
        if quote not in s:
            return f"{quote}{s}{quote}"
    strs = re.findall("[^\"]+|[^']+", s)
    assert "".join(strs) == s
    return f"concat({','.join(map(_xp_str, strs))})"


def containing_layer(elem: inkex.BaseElement) -> Optional[inkex.Layer]:
    """Return svg:g element for the layer containing elem or None if there
    is no such layer.

    """
    layers = elem.xpath(
        "./ancestor::svg:g[@inkscape:groupmode='layer'][position()=1]", namespaces=NSMAP
    )
    if layers:
        return layers[0]
    return None


def bounding_box(elem: inkex.BaseElement) -> inkex.BoundingBox:
    """Get bounding box in page coordinates (user units)"""
    return elem.bounding_box(elem.getparent().composed_transform())


class RatGuide:
    GuideMode = Literal["exclusion", "notation"]

    def __init__(self, exclusions: Sequence[inkex.BoundingBox], rat_layer: inkex.Layer):
        self.exclusions = list(exclusions)
        container = containing_layer(rat_layer)
        if container is None:
            container = rat_layer.root

        existing = container.xpath(
            ".//svg:g[@bh:rat-guide-mode='layer']", namespaces=NSMAP
        )
        if existing:
            self.guide_layer = existing[0]
            self._delete_rects("notation")
        else:
            layer = inkex.Layer.new(f"[h] {_('Rat Placement Guides')}")
            layer.set("sodipodi:insensitive", "true")  # lock layer
            layer.set(BH_RAT_GUIDE_MODE, "layer")
            container.append(layer)
            self.guide_layer = layer

        identity = inkex.Transform()
        assert self.guide_layer.composed_transform() == identity

        for excl in self.exclusions:
            self._add_rect(excl, "notation")

        for elem in self.guide_layer.xpath(
            ".//*[@bh:rat-guide-mode='exclusion']"
            # Treat top-level elements created in the guide layer by
            # the user as exclusions
            " | ./*[not(@bh:rat-guide-mode)]",
            namespaces=NSMAP,
        ):
            self.exclusions.append(bounding_box(elem))

    def reset(self) -> None:
        self._delete_rects("exclusion")

    def add_exclusion(self, bbox: inkex.BoundingBox) -> None:
        self._add_rect(bbox, "exclusion")
        self.exclusions.append(bbox)

    DEFAULT_STYLE = {
        "fill": "#c68c8c",
        "fill-opacity": "0.125",
        "stroke": "#ff0000",
        "stroke-width": "1",
        "stroke-opacity": "0.5",
        "stroke-dasharray": "2,6",
        "stroke-linecap": "round",
        "stroke-miterlimit": "4",
    }
    STYLES = {
        "notation": {
            **DEFAULT_STYLE,
            "fill": "#aaaaaa",
        }
    }

    def _add_rect(self, bbox: inkex.BoundingBox, mode: GuideMode) -> None:
        rect = inkex.Rectangle.new(bbox.left, bbox.top, bbox.width, bbox.height)
        rect.set(BH_RAT_GUIDE_MODE, mode)
        rect.style = self.STYLES.get(mode, self.DEFAULT_STYLE)
        self.guide_layer.append(rect)

    def _delete_rects(self, mode: GuideMode) -> None:
        for el in self.guide_layer.xpath(
            f".//*[@bh:rat-guide-mode={_xp_str(mode)}]", namespaces=NSMAP
        ):
            el.getparent().remove(el)


def _move_offset_to_transform(use: inkex.Use) -> None:
    """Move any offset in use[@x], use[@y] to the use[@transform]"""
    x = use.get("x", "0")
    y = use.get("y", "0")
    if x != "0" or y != "0":
        use.transform.add_translate(
            to_dimensionless(use, x),
            to_dimensionless(use, y),
        )
        use.set("x", "0")
        use.set("y", "0")


class RatPlacer:
    def __init__(
        self, boundary: inkex.BoundingBox, exclusions: Sequence[inkex.BoundingBox]
    ):
        self.boundary = boundary
        self.exclusions = exclusions

    def place_rat(self, rat: inkex.Use) -> None:
        _move_offset_to_transform(rat)
        parent_transform = rat.getparent().composed_transform()
        rat_bbox = rat.bounding_box(parent_transform)
        if rat_bbox is None:
            rat_bbox = inkex.BoundingBox((0, 0), (0, 0))
        debug.draw_bbox(rat_bbox, "red")

        newpos = self.random_position(rat_bbox)

        # Map positions from document to element
        # pylint: disable=unnecessary-dunder-call
        inverse_parent_transform = parent_transform.__neg__()
        p2 = inverse_parent_transform.apply_to_point(newpos)
        p1 = inverse_parent_transform.apply_to_point(rat_bbox.minimum)
        rat.transform.add_translate(p2 - p1)
        debug.draw_bbox(rat.bounding_box(parent_transform), "blue")

    def intersects_excluded(self, bbox: inkex.BoundingBox) -> bool:
        return any((bbox & excl) for excl in self.exclusions)

    def random_position(
        self, rat_bbox: inkex.BoundingBox, max_tries: int = 128
    ) -> inkex.ImmutableVector2d:
        """Find a random new position for element.

        The element has dimensions given by DIMENSION.  The new position will
        be contained within BOUNDARY, if possible.  Reasonable efforts will
        be made to avoid placing the element such that it overlaps with
        any bboxes listed in EXCLUSIONS.

        """
        x0 = self.boundary.left
        x1 = max(self.boundary.right - rat_bbox.width, x0)
        y0 = self.boundary.top
        y1 = max(self.boundary.bottom - rat_bbox.height, y0)

        def random_pos() -> inkex.ImmutableVector2d:
            return inkex.ImmutableVector2d(
                random.uniform(x0, x1), random.uniform(y0, y1)
            )

        for _n in range(max_tries):  # pylint: disable=unused-variable
            pos = random_pos()
            new_bbox = inkex.BoundingBox(
                (pos.x, pos.x + rat_bbox.width), (pos.y, pos.y + rat_bbox.height)
            )
            if not self.intersects_excluded(new_bbox):
                break
        else:
            inkex.errormsg(
                _(
                    "Can not find non-excluded location for rat after {} tries. "
                    "Giving up."
                ).format(max_tries)
            )
        return pos


class BadRats(ValueError):
    pass


def _clone_layer(
    layer: inkex.Layer, selected: Sequence[inkex.BaseElement]
) -> Tuple[inkex.Layer, Set[inkex.BaseElement]]:
    cloned_selected = set()

    def clone(elem: inkex.BaseElement) -> inkex.BaseElement:
        attrib = dict(elem.attrib)
        attrib.pop("id", None)
        copy = elem.__class__()
        copy.update(**attrib)
        copy.text = elem.text
        copy.tail = elem.tail
        copy.extend(map(clone, elem))

        if elem in selected:
            cloned_selected.add(copy)
        return copy

    return clone(layer), cloned_selected


def _dwim_rat_layer_name(layer_labels: Iterable[str]) -> str:
    pat = re.compile(r"^ (\[o.*?\].*?) \s+ (\d+) \s*$", re.X)
    matches = list(filter(None, map(pat.match, layer_labels)))
    names = {m.group(1) for m in matches}
    max_index = max((int(m.group(2)) for m in matches), default=0)
    name = names.pop() if len(names) == 1 else "Blind"
    return f"{name} {max_index + 1}"


def clone_rat_layer(
    rat_layer: inkex.Layer, rats: Sequence[inkex.Use]
) -> Tuple[inkex.Layer, Set[inkex.BaseElement]]:
    new_layer, new_rats = _clone_layer(rat_layer, rats)
    layer_labels = rat_layer.xpath(
        "../svg:g[@inkscape:groupmode='layer']/@inkscape:label", namespaces=NSMAP
    )
    new_layer.set("inkscape:label", _dwim_rat_layer_name(layer_labels))
    rat_layer.getparent().insert(0, new_layer)

    # lock and hide cloned layer
    rat_layer.style["display"] = "none"
    rat_layer.set("sodipodi:insensitive", "true")
    return new_layer, new_rats


def _iter_exclusions(
    elem: inkex.BaseElement, transform: types.TransformLike = None
) -> Iterator[inkex.BoundingBox]:
    if elem.getparent() is None:
        base = "/svg:svg/*[not(self::svg:defs)]/descendant-or-self::"
        is_hidden = (
            "ancestor::svg:g[@inkscape:groupmode='layer']"
            "[contains(@style,'display:none')]"
        )
        cond = f"[not({is_hidden})]"
    else:
        base = "./descendant-or-self::"
        cond = ""

    path = "|".join(
        base + s + cond
        for s in [
            "*[@bh:rat-placement='exclude']",
            "svg:use[starts-with(@xlink:href,'#')]",
        ]
    )

    for el in elem.xpath(path, namespaces=NSMAP):
        if el.get(BH_RAT_PLACEMENT) == "exclude":
            yield el.bounding_box(
                compose_transforms(transform, el.getparent().composed_transform())
            )
        else:
            assert el.tag == SVG_USE
            local_tfm = compose_transforms(transform, el.composed_transform())
            local_tfm.add_translate(
                to_dimensionless(el, el.get("x", "0")),
                to_dimensionless(el, el.get("y", "0")),
            )
            href = el.href
            if href is None:
                inkex.errormsg(f"Invalid href={el.get('xlink:href')!r} in use")
            else:
                yield from _iter_exclusions(href, local_tfm)


def find_exclusions(svg: inkex.SvgDocumentElement) -> Sequence[inkex.BoundingBox]:
    """Get the permanent rat exclusion bboxes for the course.

    These are defined by visible elements with a bh:rat-placement="exclude"
    attribute.

    Svg:use references are resolved when looking for exclusions.
    """
    return list(_iter_exclusions(svg))


def get_rat_boundary(svg: inkex.SvgDocumentElement) -> inkex.BoundingBox:
    boundaries = svg.xpath(
        "/svg:svg/*[not(self::svg:defs)]/descendant-or-self::"
        "*[@bh:rat-placement='boundary']",
        namespaces=NSMAP,
    )
    if len(boundaries) == 0:
        return svg.get_page_bbox()
    bboxes = (el.bounding_box(el.getparent().composed_transform()) for el in boundaries)
    return reduce(add, bboxes)


def find_rat_layer(rats: Sequence[inkex.BaseElement]) -> inkex.Layer:
    def looks_like_rat(elem: inkex.BaseElement) -> bool:
        return (
            elem.tag == SVG_USE
            and re.match(r"#(rat|.*tube)", elem.get("xlink:href", "")) is not None
        )

    if not all(map(looks_like_rat, rats)):
        raise BadRats(_("Fishy looking rats"))

    rat_layers = set(map(containing_layer, rats))
    if len(rat_layers) == 0:
        raise BadRats(_("No rats selected"))
    if len(rat_layers) != 1:
        raise BadRats(_("Rats are not all on the same layer"))
    layer = rat_layers.pop()
    if layer is None:
        raise BadRats(_("Rats are not on a layer"))
    assert isinstance(layer, inkex.Layer)
    return layer


def hide_rat(
    rat: inkex.Use,
    boundary: inkex.BoundingBox,
    exclusions: Sequence[inkex.BoundingBox],
) -> None:
    rat_placer = RatPlacer(boundary, exclusions)
    rat_placer.place_rat(rat)


class HideRats(inkex.EffectExtension):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")
        pars.add_argument("--restart", type=inkex.Boolean)
        pars.add_argument("--newblind", type=inkex.Boolean)

    def effect(self) -> None:
        # with debug.debugger(self.svg):
        #     debug.clear()
        try:
            self._effect()
        except BadRats as exc:
            inkex.errormsg(exc)

    def _effect(self) -> None:
        rats = self.svg.selection
        rat_layer = find_rat_layer(rats)

        with text_bbox_hack(self.svg):
            guide_layer = RatGuide(find_exclusions(self.svg), rat_layer)
        if self.options.restart or self.options.newblind:
            guide_layer.reset()
        if self.options.newblind:
            rat_layer, rats = clone_rat_layer(rat_layer, rats)

        boundary = get_rat_boundary(self.svg)
        with text_bbox_hack(self.svg):
            for rat in rats:
                hide_rat(rat, boundary, guide_layer.exclusions)
                guide_layer.add_exclusion(bounding_box(rat))


if __name__ == "__main__":
    HideRats().run()
