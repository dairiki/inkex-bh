# mypy: ignore-errors
import re
from collections import Counter

import pytest

from inkex_bh.count_symbols import count_symbols
from inkex_bh.count_symbols import CountSymbols


@pytest.fixture
def effect():
    return CountSymbols()


pytestmark = pytest.mark.usefixtures("assert_quiet")


def test_count_symbols(svg_maker):
    sym1 = svg_maker.add_symbol()
    sym2 = svg_maker.add_symbol()
    svg_maker.add_use(sym1)
    svg_maker.add_use(sym2, x=2)
    svg_maker.add_use(sym2, x=3)

    svg = svg_maker.svg
    assert count_symbols(svg.xpath("//svg:use")) == Counter(
        {
            f"#{sym1.get('id')}": 1,
            f"#{sym2.get('id')}": 2,
        }
    )


def test_count_symbols_in_groups(svg_maker):
    sym = svg_maker.add_symbol()

    # two symbols in a group
    group1 = svg_maker.add_group()
    svg_maker.add_use(sym, x=1, parent=group1)
    svg_maker.add_use(sym, x=2, parent=group1)

    # another group, with one symbol directly and two more indirectly
    group2 = svg_maker.add_group()
    svg_maker.add_use(sym, x=3, parent=group2)
    svg_maker.add_use(group1, x=4, parent=group2)

    svg_maker.add_use(group1, y=1)  # 2 more indirect syms
    svg_maker.add_use(group2, y=2)  # 3 more indirect syms
    svg_maker.add_use(sym, y=3)  # 1 direct sym

    svg = svg_maker.svg
    assert count_symbols(svg.xpath("//svg:use")) == Counter({f"#{sym.get('id')}": 11})


def test_count_symbols_warn_on_missing_href(svg_maker, capsys):
    svg_maker._add("svg:use")
    svg = svg_maker.svg
    counts = count_symbols(svg.xpath("//svg:use"))
    assert counts == Counter()
    output = capsys.readouterr()
    assert re.search(r"WARNING\b.*\bno element for href\b", output.err)
    assert output.out == ""


def test_effect(svg_maker, run_effect, tmp_path, capsys):
    sym1 = svg_maker.add_symbol()
    svg_maker.add_use(sym1)

    sym2 = svg_maker.add_symbol()
    hidden = svg_maker.add_layer("Hidden", visible=False)
    svg_maker.add_use(sym2, parent=hidden)

    assert run_effect(svg_maker.as_file()) is None  # no output
    output = capsys.readouterr()
    assert output.out == ""
    matches = {
        m.group("symbol"): int(m.group("count"))
        for m in re.finditer(
            r"(?mx)^ \s* (?P<count>\d+): \s+ (?P<symbol>\S+) $", output.err
        )
    }
    assert matches == {f"#{sym1.get('id')}": 1}
