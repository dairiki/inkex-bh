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
from inkex_bh.update_symbols import _get_data_path
from inkex_bh.update_symbols import _get_symbol_path
from inkex_bh.update_symbols import _has_unscoped_ids
from inkex_bh.update_symbols import _load_symbols_from_svg
from inkex_bh.update_symbols import _symbol_scale
from inkex_bh.update_symbols import load_symbols
from inkex_bh.update_symbols import update_symbols
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
def dummy_symbol_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a dummy symbol-set directory.

    _get_data_path will be monkeypatched so that, by default, the code
    in update_symbols will find this symbol set.
    """
    monkeypatch.setattr(
        inkex_bh.update_symbols, "_get_data_path", lambda user: tmp_path
    )

    metadata_json = tmp_path / "symbols/some-lib/METADATA.json"
    metadata_json.parent.mkdir(parents=True, exist_ok=True)
    metadata_json.write_text(json.dumps({"name": "bh-symbols"}))
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


def test_get_symbol_path(tmp_path: Path) -> None:
    metadata = tmp_path / "symbols/subdir/METADATA.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({"name": "test-name"}))
    assert _get_symbol_path([tmp_path], "test-name") == metadata.parent


def test_get_symbol_path_only_checks_symbols(tmp_path: Path) -> None:
    metadata = tmp_path / "not-symbols/subdir/METADATA.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({"name": "test-name"}))
    assert _get_symbol_path([tmp_path], "test-name") is None


def test_get_symbol_path_skips_missing_paths(tmp_path: Path) -> None:
    metadata = tmp_path / "symbols/subdir/METADATA.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({"name": "test-name"}))
    missing = tmp_path / "missing"
    assert _get_symbol_path([missing, tmp_path], "test-name") == metadata.parent


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
    for filename in ("symbols.svg", "dup.svg"):
        write_symbol_svg('<symbol id="sym1"></symbol>', filename=filename)
    symbols = load_symbols()
    assert set(symbols.keys()) == {"sym1"}
    captured = capsys.readouterr()
    assert "dup.svg contains duplicate" in captured.err


def test_load_symbols_ignores_syms_w_unscoped_ids(
    write_symbol_svg: WriteSvg, capsys: pytest.CaptureFixture[str]
) -> None:
    write_symbol_svg('<symbol id="sym1"><g id="unscoped"></g></symbol>')
    symbols = load_symbols()
    assert set(symbols.keys()) == set()
    captured = capsys.readouterr()
    assert "unscoped id" in captured.err


@pytest.mark.usefixtures("dummy_symbol_path")
def test_load_symbols_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        load_symbols(name="unknown-symbol-set-ag8dkf")
    assert "can not find" in str(exc_info.value)


def test_update_symbols(capsys: pytest.CaptureFixture[str]) -> None:
    svg = inkex.load_svg(
        svg_tmpl('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    ).getroot()
    symbols = {"sym1": load_symbol('<symbol id="sym1"><g id="sym1:new"></g></symbol>')}
    update_symbols(svg, symbols)
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
    update_symbols(svg, symbols)
    assert svg.find(".//*[@id='sym1:old']") is not None


def test_effect(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    write_svg: WriteSvg,
    write_symbol_svg: WriteSvg,
) -> None:
    drawing_svg = write_svg('<symbol id="sym1"><g id="sym1:old"></g></symbol>')
    write_symbol_svg('<symbol id="sym1"><g id="sym1:new"></g></symbol>')
    out = run_effect(os.fspath(drawing_svg))
    assert out is not None
    assert out.find(".//*[@id='sym1:new']") is not None


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
