# pylint: disable=redefined-outer-name
# mypy: ignore-errors
from __future__ import annotations

import inkex
import pytest

from inkex_bh.constants import BH_RANDOM_SEED
from inkex_bh.constants import NSMAP
from inkex_bh.random_seed import RandomSeed


@pytest.fixture
def effect() -> inkex.InkscapeExtension:
    return RandomSeed()


pytestmark = pytest.mark.usefixtures("assert_quiet")


def test_adds_seed(svg_maker, run_effect):
    out_svg = run_effect(svg_maker.as_file())
    assert out_svg.get(BH_RANDOM_SEED).isdigit()


def test_adds_ns_decl(svg_maker, run_effect):
    out_svg = run_effect(svg_maker.as_file())
    assert out_svg.nsmap["bh"] == NSMAP["bh"]


def test_leaves_existing_seed(svg_maker, run_effect, capsys):
    svg_maker.svg.set(BH_RANDOM_SEED, "42")
    svg = run_effect(svg_maker.as_file())
    assert svg is None
    output = capsys.readouterr()
    assert output.out == ""
    assert "Random seed is already set" in output.err
