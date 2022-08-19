# mypy: ignore-errors
import re
from collections import Counter

import inkex
import pytest
from lxml import etree

from inkex_bh.count_symbols import count_symbols
from inkex_bh.count_symbols import CountSymbols

pytestmark = pytest.mark.usefixtures("assert_no_stdout")


@pytest.fixture
def effect():
    return CountSymbols()


@pytest.fixture
def svg():
    tree = inkex.load_svg(
        """
    <svg
       viewBox="0 0 816 1056"
       id="svg5"
       sodipodi:docname="test1.svg"
       xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
       xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
       xmlns:xlink="http://www.w3.org/1999/xlink"
       xmlns="http://www.w3.org/2000/svg"
       xmlns:svg="http://www.w3.org/2000/svg">
      <sodipodi:namedview
         id="namedview7"
         a-bunch-of-stuff-elided="..."
         inkscape:current-layer="layer1" />
      <defs
         id="defs2">
        <svg:symbol id="sym1" />
        <svg:symbol id="sym2" />
      </defs>
      <g
         inkscape:label="Layer 1"
         inkscape:groupmode="layer"
         id="layer1" />
    </svg>
    """
    )
    return tree.getroot()


def test_count_symbols(svg):
    sym1, sym2 = svg.xpath("//svg:symbol")[:2]
    layer = svg.findone("./svg:g[@inkscape:groupmode='layer']")
    layer.append(inkex.Use.new(sym1.eid, 1, 1))
    layer.append(inkex.Use.new(sym2.eid, 2, 2))
    layer.append(inkex.Use.new(sym2.eid, 3, 3))

    assert count_symbols(svg.xpath("//svg:use")) == Counter(
        {
            f"#{sym1.eid}": 1,
            f"#{sym2.eid}": 2,
        }
    )


def test_count_symbols_in_groups(svg):
    sym = svg.findone("//svg:symbol")

    layer = svg.findone("./svg:g[@inkscape:groupmode='layer']")
    group1 = inkex.Group.new(
        "test", inkex.Use.new(sym.eid, 0, 0), inkex.Use.new(sym.eid, 1, 1)
    )
    layer.append(group1)  # 2 sym
    group2 = inkex.Group.new(
        "test", inkex.Use.new(group1.eid, 0, 0), inkex.Use.new(sym.eid, 1, 1)
    )
    layer.append(group2)  # 2 + 1 = 3 syms

    # group1 is visible with two syms
    layer.append(inkex.Use.new(group1.eid, 10, 10))  # 2 syms
    layer.append(inkex.Use.new(group2.eid, 20, 20))  # 3 syms
    layer.append(inkex.Use.new(sym.eid, 30, 30))  # 1 syms

    counts = count_symbols(svg.xpath("//svg:use"))
    assert counts == Counter({f"#{sym.eid}": 11})


def test_count_symbols_warn_on_missing_href(svg, capsys):
    layer = svg.findone("./svg:g[@inkscape:groupmode='layer']")
    layer.append(inkex.Use.new("missing-ref", 10, 10))

    counts = count_symbols(svg.xpath("//svg:use"))
    assert counts == Counter()
    print("foo")
    output = capsys.readouterr()
    assert re.search(r"WARNING\b.*\bno element for href\b", output.err)


def test_effect(svg, run_effect, tmp_path, capsys):
    sym1, sym2 = svg.xpath("//svg:symbol")[:2]
    layer = svg.findone("./svg:g[@inkscape:groupmode='layer']")
    layer.append(inkex.Use.new(sym1.eid, 10, 10))

    hidden = inkex.Layer.new("hidden layer")
    hidden.style["display"] = "none"
    hidden.append(inkex.Use.new(sym2.eid, 20, 20))
    svg.append(hidden)

    infile = tmp_path / "in.svg"
    infile.write_bytes(etree.tostring(svg))

    assert run_effect(infile) is None  # no output
    output = capsys.readouterr().err
    matches = {
        m.group("symbol"): int(m.group("count"))
        for m in re.finditer(
            r"(?mx)^ \s* (?P<count>\d+): \s+ (?P<symbol>\S+) $", output
        )
    }
    assert matches == {f"#{sym1.eid}": 1}
