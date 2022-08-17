from contextlib import contextmanager
from contextlib import ExitStack
from typing import Iterator

import inkex

import bh_typing as types


def inkex_tspan_bounding_box_is_buggy() -> bool:
    # As of Inkscape 1.2.1, inkex puts bbox.top at y and bbox.bottom
    # at y + font-size.  This is incorrect: tspan[@y] specifies the
    # position of the baseline, so bbox.top should be y - fontsize,
    # bbox.bottom should be y.
    tspan = inkex.Tspan.new(x="0", y="0", style="font-size: 1")
    bbox = tspan.bounding_box()
    return bbox.bottom > 0.5    # type: ignore


@contextmanager
def negate_fontsizes(document: types.SvgElementTree) -> Iterator[None]:
    """ Temporarily negate all text font-sizes.

    This is to work around a bug in inkex.Tspan.
    """
    mangled = []
    try:
        for elem in document.xpath("//svg:text | //svg:tspan"):
            elem.set("x-save-style", elem.get("style", None))
            # XXX: should use elem.to_dimensionless?
            fontsize = elem.uutounit(elem.style.get('font-size'))
            # fontsize = elem.to_dimensionless(elem.style.get('font-size'))
            elem.style["font-size"] = -fontsize
            mangled.append(elem)

        yield

    finally:
        for elem in mangled:
            elem.set("style", elem.attrib.pop("x-save-style", None))


@contextmanager
def text_bbox_hack(document: types.SvgElementTree) -> Iterator[None]:
    """ Hack up document to work-around buggy text bbox computation in inkex.
    """
    with ExitStack() as stack:
        if inkex_tspan_bounding_box_is_buggy():
            stack.enter_context(negate_fontsizes(document))
        yield
