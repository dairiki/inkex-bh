# pylint: disable=redefined-outer-name
import inspect
import io
import os

import pytest
from lxml import etree

from inkex_bh.constants import BH_RANDOM_SEED
from inkex_bh.constants import NSMAP
from inkex_bh.random_seed import RandomSeed


TEST_SVG_TEMPL = inspect.cleandoc(
    """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <svg
       width="8.5in"
       height="11in"
       viewBox="0 0 816 1056"
       version="1.1"
       id="svg5"
       sodipodi:docname="test.svg"
       xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
       xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
       xmlns="http://www.w3.org/2000/svg"
       xmlns:svg="http://www.w3.org/2000/svg"
       {extra_root_attrs}>
      <sodipodi:namedview
         id="namedview7"
         a-bunch-of-stuff-elided="..."
         inkscape:current-layer="layer1" />
      <defs
         id="defs2" />
      <g
         inkscape:label="Layer 1"
         inkscape:groupmode="layer"
         id="layer1" />
    </svg>
    """
)


@pytest.fixture
def effect():
    return RandomSeed()


@pytest.fixture
def run_effect(effect):
    def run_effect(*cmd):
        # Dereference any Paths in the command sequence
        str_cmd = tuple(
            arg if isinstance(arg, (bytes, str)) else os.fspath(arg) for arg in cmd
        )
        outfp = io.BytesIO()

        effect.run(str_cmd, output=outfp)

        if outfp.tell() == 0:
            return None  # no output
        outfp.seek(0)
        return etree.parse(outfp).getroot()

    return run_effect


@pytest.fixture
def random_seed():
    return None


@pytest.fixture
def test_svg(tmp_path, random_seed):
    extra_root_attrs = ""
    if random_seed is not None:
        extra_root_attrs = f'bh:random-seed="{random_seed}" xmlns:bh="{NSMAP["bh"]}"'

    test_svg = tmp_path / "test.svg"
    test_svg.write_text(TEST_SVG_TEMPL.format(extra_root_attrs=extra_root_attrs))
    return test_svg


def test_adds_seed(test_svg, run_effect):
    out_svg = run_effect(test_svg)
    assert out_svg.get(BH_RANDOM_SEED).isdigit()


def test_adds_ns_decl(test_svg, run_effect):
    out_svg = run_effect(test_svg)
    assert out_svg.nsmap["bh"] == NSMAP["bh"]


@pytest.mark.parametrize("random_seed", [42])
def test_leaves_existing_seed(test_svg, run_effect):
    svg = run_effect(test_svg)
    assert svg is None
