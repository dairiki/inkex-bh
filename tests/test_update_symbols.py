from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import inkex
import pytest

import inkex_bh.update_symbols
from inkex_bh.update_symbols import _find_symbol_distribution
from inkex_bh.update_symbols import _get_data_path
from inkex_bh.update_symbols import _has_unscoped_ids
from inkex_bh.update_symbols import _load_symbols_from_svg
from inkex_bh.update_symbols import _symbol_scale
from inkex_bh.update_symbols import _symbols_equal
from inkex_bh.update_symbols import load_symbols
from inkex_bh.update_symbols import update_symbols
from inkex_bh.update_symbols import UpdateStats
from inkex_bh.update_symbols import UpdateSymbols


@pytest.fixture
def effect() -> UpdateSymbols:
    return UpdateSymbols()


def svg_tmpl(defs: str = "", body: str = "") -> bytes:
    """Template for SVG source."""
    xml_src = f"""
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <svg xmlns="http://www.w3.org/2000/svg"
             xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
             xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
          <sodipodi:namedview id="cruft"/>
          <defs>{defs}</defs>
          <g inkscape:label="Layer 1" inkscape:groupmode="layer">{body}</g>
        </svg>
    """
    return xml_src.strip().encode("utf-8")


def load_symbol(symsrc: str) -> inkex.Symbol:
    """Parse symbol XML source to symbol element.

    The source is interpreted in the context of some useful XML
    namespace declarations (see ``svg_tmpl``).
    """
    tree = inkex.load_svg(svg_tmpl(defs=symsrc))
    symbol = tree.find("//{http://www.w3.org/2000/svg}symbol")
    assert isinstance(symbol, inkex.Symbol)
    return symbol


@dataclass
class WriteSvg:
    """Expand SVG template, write to file."""

    parent_path: Path
    default_filename: str = "drawing.svg"

    def __call__(
        self, defs: str = "", body: str = "", *, filename: str | None = None
    ) -> Path:
        if filename is None:
            filename = self.default_filename
        svg_path = self.parent_path / filename
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_bytes(svg_tmpl(defs, body))
        return svg_path


@pytest.fixture
def write_svg(tmp_path: Path) -> WriteSvg:
    """Expand SVG template, write to file."""
    return WriteSvg(parent_path=tmp_path)


@pytest.fixture
def symbol_metadata() -> dict[str, str]:
    return {
        "name": "bh-symbols",
        "version": "0.0.dev1",
    }


@pytest.fixture
def dummy_symbol_path(
    symbol_metadata: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Create a dummy symbol-set directory.

    _get_data_path will be monkeypatched so that, by default, the code
    in update_symbols will find this symbol set.
    """
    monkeypatch.setattr(
        inkex_bh.update_symbols, "_get_data_path", lambda user: tmp_path
    )

    metadata_json = tmp_path / "symbols/some-lib/METADATA.json"
    metadata_json.parent.mkdir(parents=True, exist_ok=True)
    metadata_json.write_text(json.dumps(symbol_metadata))
    return metadata_json.parent


@pytest.fixture
def write_symbol_svg(dummy_symbol_path: Path) -> WriteSvg:
    """Expand SVG template, write to file in symbol path."""
    return WriteSvg(parent_path=dummy_symbol_path, default_filename="symbols.svg")


try:
    inkex.command.inkscape(None, version=True)
    have_inkscape = True
except inkex.command.CommandNotFound:
    have_inkscape = False


@pytest.mark.parametrize("for_user", [False, True])
@pytest.mark.skipif(not have_inkscape, reason="inkscape not installed")
def test_get_data_path(for_user: bool) -> None:
    data_path = _get_data_path(for_user)
    assert data_path.is_dir()


def test_find_symbol_distribution(tmp_path: Path) -> None:
    metadata = tmp_path / "symbols/subdir/METADATA.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({"name": "test-name"}))
    dist = _find_symbol_distribution([tmp_path], "test-name")
    assert dist.path == metadata.parent


def test_find_symbol_distribution_only_checks_symbols(tmp_path: Path) -> None:
    metadata = tmp_path / "not-symbols/subdir/METADATA.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({"name": "test-name"}))
    with pytest.raises(LookupError):
        _find_symbol_distribution([tmp_path], "test-name")


def test_find_symbol_distribution_skips_missing_paths(tmp_path: Path) -> None:
    metadata = tmp_path / "symbols/subdir/METADATA.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({"name": "test-name"}))
    missing = tmp_path / "missing"
    dist = _find_symbol_distribution([missing, tmp_path], "test-name")
    assert dist.path == metadata.parent


@pytest.mark.parametrize(
    "filename, scale",
    [
        ("symbols-12x13x14.svg", "48:1"),
        ("symbols-12x13x14-14to3.svg", "14:3"),
    ],
)
def test_get_symbol_scale(filename: str, scale: str) -> None:
    symbol_path = Path("/some/where", filename)
    assert _symbol_scale(symbol_path) == scale


def test_load_symbols_from_svg(write_svg: WriteSvg) -> None:
    svg_path = write_svg(
        '<symbol id="sym1"></symbol>'
        '<g id="not-a-sym"></g>'
        '<symbol id="sym2"></symbol>'
    )
    assert set(_load_symbols_from_svg(svg_path)) == {"sym1", "sym2"}


def test_load_symbols_from_svg_ignores_nested_defs(write_svg: WriteSvg) -> None:
    svg_path = write_svg(
        '<symbol id="sym1">' '<defs><symbol id="sym1:sym2"></symbol></defs>' "</symbol>"
    )
    assert set(_load_symbols_from_svg(svg_path)) == {"sym1"}


def test_load_symbols_from_svg_ignores_symbols_outside_defs(
    write_svg: WriteSvg,
) -> None:
    svg_path = write_svg(
        defs='<g><defs><symbol id="sym2"></symbol></defs></g>',
        body='<symbol id="sym1"></symbol>',
    )
    assert len(_load_symbols_from_svg(svg_path)) == 0


def test_load_symbols_from_svg_skips_unscoped_ids(
    write_svg: WriteSvg, capsys: pytest.CaptureFixture[str]
) -> None:
    svg_path = write_svg('<symbol id="sym1"><g id="foo"></g></symbol>')
    assert len(_load_symbols_from_svg(svg_path)) == 0
    captured = capsys.readouterr()
    assert "unscoped id" in captured.err


def test_load_symbols_from_svg_skips_duplicate_ids(
    write_svg: WriteSvg, capsys: pytest.CaptureFixture[str]
) -> None:
    svg_path = write_svg('<symbol id="sym1"></symbol>' '<symbol id="sym1"></symbol>')
    assert set(_load_symbols_from_svg(svg_path)) == {"sym1"}
    captured = capsys.readouterr()
    assert "duplicate id" in captured.err


@pytest.mark.parametrize(
    "svg",
    [
        '<symbol id="foo"><g id="bar"></g></symbol>',
        '<symbol id="foo"><g id="other:subid"></g></symbol>',
    ],
)
def test_has_unscoped_ids_is_true(svg: str) -> None:
    sym = load_symbol(svg)
    assert _has_unscoped_ids(sym)


@pytest.mark.parametrize(
    "svg",
    [
        '<symbol id="foo"><g></g></symbol>',
        '<symbol id="foo"><g id="foo:subid"></g></symbol>',
    ],
)
def test_has_unscoped_ids_is_false(svg: str) -> None:
    sym = load_symbol(svg)
    assert not _has_unscoped_ids(sym)


def test_load_symbols(write_symbol_svg: WriteSvg) -> None:
    write_symbol_svg('<symbol id="sym1"></symbol>')
    symbols = load_symbols()
    assert set(symbols.keys()) == {"sym1"}


def test_load_symbols_ignores_duplicate_id(
    write_symbol_svg: WriteSvg, capsys: pytest.CaptureFixture[str]
) -> None:
    for filename in ("symbols.svg", "symbols-60to1.svg"):
        write_symbol_svg('<symbol id="sym1"></symbol>', filename=filename)
    symbols = load_symbols()
    assert set(symbols.keys()) == {"sym1"}
    captured = capsys.readouterr()
    assert "symbols-60to1.svg contains duplicate" in captured.err


def test_load_symbols_ignores_syms_w_unscoped_ids(
    write_symbol_svg: WriteSvg, capsys: pytest.CaptureFixture[str]
) -> None:
    write_symbol_svg('<symbol id="sym1"><g id="unscoped"></g></symbol>')
    symbols = load_symbols()
    assert set(symbols.keys()) == set()
    captured = capsys.readouterr()
    assert "unscoped id" in captured.err


def test_load_symbols_reports_symbol_version(
    symbol_metadata: dict[str, str],
    write_symbol_svg: WriteSvg,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_symbol_svg('<symbol id="sym1"></symbol>')
    load_symbols()
    captured = capsys.readouterr()
    version_str = f"{symbol_metadata['name']}=={symbol_metadata['version']}"
    assert re.search(rf"(?mi)^updating .* {re.escape(version_str)}", captured.err)


@pytest.mark.usefixtures("dummy_symbol_path")
def test_load_symbols_missing_symbols() -> None:
    with pytest.raises(Exception) as exc_info:
        load_symbols(name="unknown-symbol-set-ag8dkf")
    assert "can not find" in str(exc_info.value)


def _symx(body: str) -> str:
    return f'<symbol id="x">{body}</symbol>'


@pytest.mark.parametrize(
    "sym1, sym2",
    [
        ('<symbol id="sym1"/>', '<symbol id="sym1"/>'),
        (_symx("<g/>"), _symx("<g/>")),
        (_symx('<g id="g1"/>'), _symx("<g/>")),
        (_symx('<g id="g1"/>'), _symx('<g id="g2"/>')),
        (_symx('<g id="x:g"/>'), _symx('<g id="x:g"/>')),
        (
            _symx('<a xmlns="http://example.org/"/>'),
            _symx('<a xmlns="http://example.org/"/>'),
        ),
        (_symx("text<g/>tail"), _symx(" text <g/> tail ")),
        (_symx("<t>text</t>"), _symx("<t>text</t>")),
    ],
)
def test_symbols_equal(sym1: str, sym2: str) -> None:
    svg1 = load_symbol(sym1)
    svg2 = load_symbol(sym2)
    assert _symbols_equal(svg1, svg2) is True
    assert _symbols_equal(svg2, svg1) is True


@pytest.mark.parametrize(
    "sym1, sym2",
    [
        ('<symbol id="sym1"/>', '<symbol id="sym2"/>'),
        (_symx('<g id="x:g1"/>'), _symx('<g id="x:g2"/>')),
        (_symx("<g/>"), _symx("<path/>")),
        (_symx("<g/>"), _symx("")),
        (
            _symx('<a xmlns="http://example.org/"/>'),
            _symx('<a xmlns="http://example.net/"/>'),
        ),
        (_symx("text<g/>tail"), _symx("<g/>tail")),
        (_symx("text<g/>tail"), _symx("text<g/>")),
        (_symx("<t>text</t>"), _symx("<t> text</t>")),
        (_symx("<t>text</t>"), _symx("<t>text </t>")),
        (_symx("<t>text</t>"), _symx("<t/>")),
    ],
)
def test_symbols_equal_false(sym1: str, sym2: str) -> None:
    svg1 = load_symbol(sym1)
    svg2 = load_symbol(sym2)
    assert _symbols_equal(svg1, svg2) is False
    assert _symbols_equal(svg2, svg1) is False


def test_update_symbols(capsys: pytest.CaptureFixture[str]) -> None:
    svg = inkex.load_svg(
        svg_tmpl('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    ).getroot()
    symbols = {"sym1": load_symbol('<symbol id="sym1"><g id="sym1:new"></g></symbol>')}
    stats = update_symbols(svg, symbols)
    assert stats == UpdateStats(total=1, known=1, updated=1)
    assert svg.find(".//*[@id='sym1:new']") is not None
    assert svg.find(".//*[@id='sym1:old']") is None
    captured = capsys.readouterr()
    assert re.search(r"(?i)\bupdat(ing|ed)\b", captured.err)
    assert re.search(r"\bsym1\b", captured.err)


def test_update_symbols_ignores_unknown() -> None:
    svg = inkex.load_svg(
        svg_tmpl('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    ).getroot()
    symbols: dict[str, inkex.Symbol] = {}
    stats = update_symbols(svg, symbols)
    assert stats == UpdateStats(total=1)
    assert svg.find(".//*[@id='sym1:old']") is not None


def test_update_symbols_skips_uptodate_symbols() -> None:
    svg = inkex.load_svg(
        svg_tmpl('<symbol id="sym1"><g id="cruft"/></symbol>')
    ).getroot()
    symbols = {"sym1": load_symbol('<symbol id="sym1"><g/></symbol>')}
    stats = update_symbols(svg, symbols)
    assert stats == UpdateStats(total=1, known=1)
    assert svg.find(".//*[@id='cruft']") is not None


def test_update_symbols_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    svg = inkex.load_svg(
        svg_tmpl('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    ).getroot()
    symbols = {"sym1": load_symbol('<symbol id="sym1"><g id="sym1:new"></g></symbol>')}
    stats = update_symbols(svg, symbols, dry_run=True)
    assert stats == UpdateStats(total=1, known=1, updated=1)
    assert svg.find(".//*[@id='sym1:old']") is not None
    assert svg.find(".//*[@id='sym1:new']") is None
    captured = capsys.readouterr()
    assert re.search(r"(?i)\bupdat(ing|ed)\b", captured.err)
    assert re.search(r"\bsym1\b", captured.err)


def test_effect(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    write_svg: WriteSvg,
    write_symbol_svg: WriteSvg,
    capsys: pytest.CaptureFixture[str],
) -> None:
    drawing_svg = write_svg('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    write_symbol_svg('<symbol id="sym1"><g id="sym1:new"></g></symbol>')
    out = run_effect(os.fspath(drawing_svg))
    assert out is not None
    assert out.find(".//*[@id='sym1:new']") is not None
    captured = capsys.readouterr()
    assert re.search("(?m)^UPDATED.* 1 of 1 ", captured.err)


def test_effect_uptodate(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    write_svg: WriteSvg,
    write_symbol_svg: WriteSvg,
) -> None:
    drawing_svg = write_svg('<symbol id="sym1"><g id="cruft"/></symbol>')
    write_symbol_svg('<symbol id="sym1"><g/></symbol>')
    out = run_effect(os.fspath(drawing_svg))
    assert out is None


def test_effect_dry_run(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    write_svg: WriteSvg,
    write_symbol_svg: WriteSvg,
    capsys: pytest.CaptureFixture[str],
) -> None:
    drawing_svg = write_svg('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    write_symbol_svg('<symbol id="sym1"><g id="sym1:new"></g></symbol>')
    out = run_effect(os.fspath(drawing_svg), "--dry-run=true")
    assert out is None
    captured = capsys.readouterr()
    assert re.search("(?m)^DRY-RUN.* 1 of 1 ", captured.err)


def test_effect_error(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    write_svg: WriteSvg,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        # no symbols here
        inkex_bh.update_symbols,
        "_get_data_path",
        lambda user: tmp_path,
    )
    drawing_svg = write_svg('<symbol id="sym1"><g id="sym1:old"></g></symbol>')

    out = run_effect(os.fspath(drawing_svg))
    assert out is None
    captured = capsys.readouterr()
    assert "can not find symbol set" in captured.err
