# mypy: ignore-errors
import inkex

from inkex_bh.constants import NSMAP
from inkex_bh.debug import clear
from inkex_bh.debug import debugger
from inkex_bh.debug import draw_bbox


def test_draw_bbox(svg_maker):
    svg = svg_maker.svg
    with debugger(svg):
        draw_bbox(inkex.BoundingBox((0, 10), (20, 40)))
    rect = svg[-1]
    assert rect.tag == f"{{{NSMAP['svg']}}}rect"
    assert rect.left == 0
    assert rect.top == 20
    assert rect.width == 10
    assert rect.height == 20


def test_clear(svg_maker):
    rect = svg_maker.add_rectangle(width=10, height=10, parent=svg_maker.svg)
    svg = svg_maker.svg
    assert rect in svg
    with debugger(svg):
        clear()
    assert rect not in svg


def test_draw_bbox_debugger_inactive(svg_maker):
    svg = svg_maker.svg
    initial_length = len(svg)
    draw_bbox(inkex.BoundingBox((0, 10), (20, 40)))
    assert len(svg) == initial_length
