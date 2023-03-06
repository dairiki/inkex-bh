from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import inkex
import pytest
from conftest import SvgMaker
from lxml import etree

import inkex_bh.update_symbols
from inkex_bh.update_symbols import _get_data_path
from inkex_bh.update_symbols import _get_symbol_path
from inkex_bh.update_symbols import _has_unscoped_ids
from inkex_bh.update_symbols import _iter_symbol_files
from inkex_bh.update_symbols import _iter_symbols
from inkex_bh.update_symbols import _symbol_scale
from inkex_bh.update_symbols import load_symbols
from inkex_bh.update_symbols import update_symbols
from inkex_bh.update_symbols import UpdateSymbols


@pytest.fixture
def effect() -> UpdateSymbols:
    return UpdateSymbols()


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


def svg_tmpl(defs: str = "", body: str = "") -> str:

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <svg xmlns="http://www.w3.org/2000/svg"
            xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
            xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
          <sodipodi:namedview id="cruft"/>
          <defs>{defs}</defs>
          <g inkscape:label="Layer 1" inkscape:groupmode="layer">{body}</g>
        </svg>
        """


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


def test_iter_symbol_files(tmp_path: Path) -> None:
    for fn in ["symbols.svg", "ignored-scale-60to1.svg", "junk.txt"]:
        Path(tmp_path, fn).touch()
    assert set(_iter_symbol_files(tmp_path)) == {tmp_path / "symbols.svg"}


def test_iter_symbol_files_ignores_nonstandard_scales(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for fn in ["symbols.svg", "ignored-scale-60to1.svg", "junk.txt"]:
        Path(tmp_path, fn).touch()
    assert set(_iter_symbol_files(tmp_path)) == {tmp_path / "symbols.svg"}
    output = capsys.readouterr()
    assert re.search(r"non-standard scale\b.*\b60:1\b", output.err)


def test_iter_symbols(tmp_path: Path) -> None:
    svg_path = tmp_path / "symbol.svg"
    svg_path.write_text(
        svg_tmpl(
            '<symbol id="sym1"></symbol>'
            '<g id="not-a-sym"></g>'
            '<symbol id="sym2"></symbol>'
        )
    )
    assert {sym.get("id") for sym in _iter_symbols(svg_path)} == {"sym1", "sym2"}


def test_iter_symbols_ignore_nested_defs(tmp_path: Path) -> None:
    svg_path = tmp_path / "symbol.svg"
    svg_path.write_text(
        svg_tmpl('<symbol id="sym1"><defs><symbol id="sym2"></symbol></defs></symbol>')
    )
    assert {sym.get("id") for sym in _iter_symbols(svg_path)} == {"sym1"}


def test_iter_symbols_ignores_symbols_outside_defs(tmp_path: Path) -> None:
    svg_path = tmp_path / "symbol.svg"
    svg_path.write_text(
        svg_tmpl(
            defs='<g><defs><symbol id="sym2"></symbol></defs></g>',
            body='<symbol id="sym1"></symbol>',
        )
    )
    assert {sym.get("id") for sym in _iter_symbols(svg_path)} == set()


@pytest.mark.parametrize(
    "svg",
    [
        '<symbol id="foo"><g id="other:subid"></g></symbol>',
    ],
)
def test_has_unscoped_ids_is_true(svg: str) -> None:
    sym = inkex.load_svg(svg).getroot()
    assert _has_unscoped_ids(sym)


@pytest.mark.parametrize(
    "svg",
    [
        '<symbol id="foo"><g></g></symbol>',
        '<symbol id="foo"><g id="foo:subid"></g></symbol>',
    ],
)
def test_has_unscoped_ids_is_false(svg: str) -> None:
    sym = inkex.load_svg(svg).getroot()
    assert not _has_unscoped_ids(sym)


def test_load_symbols(dummy_symbol_path: Path) -> None:
    svg_path = dummy_symbol_path / "symbols.svg"
    svg_path.write_text(svg_tmpl('<symbol id="sym1"></symbol>'))
    symbols = load_symbols()
    assert set(symbols.keys()) == {"sym1"}


def test_load_symbols_ignores_duplicate_id(
    dummy_symbol_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for svg_file in ("symbols.svg", "dup.svg"):
        Path(dummy_symbol_path, svg_file).write_text(
            svg_tmpl('<symbol id="sym1"></symbol>')
        )
    symbols = load_symbols()
    assert set(symbols.keys()) == {"sym1"}
    output = capsys.readouterr()
    assert "duplicate id" in output.err


def test_load_symbols_ignores_syms_w_unscoped_ids(
    dummy_symbol_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    svg_path = dummy_symbol_path / "symbols.svg"
    svg_path.write_text(svg_tmpl('<symbol id="sym1"><g id="unscoped"></g></symbol>'))
    symbols = load_symbols()
    assert set(symbols.keys()) == set()
    output = capsys.readouterr()
    assert "unscoped id" in output.err


def test_load_symbols_raises_runtime_error(dummy_symbol_path: Path) -> None:
    with pytest.raises(RuntimeError) as exc_info:
        load_symbols(name="unknown-symbol-set-ag8dkf")
    assert "can not find" in str(exc_info.value)


@pytest.fixture
def drawing_with_sym1(svg_maker: SvgMaker) -> SvgMaker:
    sym1 = svg_maker.add_symbol(id="sym1")
    g = svg_maker.add_group(parent=sym1)
    g.set("id", "sym1:old")
    return svg_maker


@pytest.fixture
def new_sym1() -> inkex.Symbol:
    return inkex.load_svg('<symbol id="sym1"><g id="sym1:new"></g></symbol>').getroot()


def test_update_symbols(drawing_with_sym1: SvgMaker, new_sym1: inkex.Symbol) -> None:
    svg = drawing_with_sym1.svg
    update_symbols(svg, {"sym1": new_sym1})
    assert svg.find(".//*[@id='sym1:new']") is not None
    assert svg.find(".//*[@id='sym1:old']") is None


def test_update_symbols_ignores_unknown(drawing_with_sym1: SvgMaker) -> None:
    svg = drawing_with_sym1.svg
    symbols: dict[str, inkex.Symbol] = {}
    update_symbols(svg, symbols)
    assert svg.find(".//*[@id='sym1:old']") is not None


@pytest.fixture
def dummy_symbols(
    dummy_symbol_path: Path,
    new_sym1: inkex.Symbol,
) -> None:
    symbols_svg = dummy_symbol_path / "symbols.svg"
    symbols_svg.write_text(svg_tmpl(etree.tostring(new_sym1, encoding="unicode")))


@pytest.mark.usefixtures("dummy_symbols")
def test_effect(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    drawing_with_sym1: SvgMaker,
) -> None:
    out = run_effect(drawing_with_sym1.as_file())
    assert out is not None
    assert out.find(".//*[@id='sym1']") is not None


def test_effect_error(
    run_effect: Callable[..., inkex.SvgDocumentElement | None],
    drawing_with_sym1: SvgMaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        # no symbols here
        inkex_bh.update_symbols,
        "_get_data_path",
        lambda user: tmp_path,
    )

    out = run_effect(drawing_with_sym1.as_file())
    assert out is None
    output = capsys.readouterr()
    assert "can not find symbol set" in output.err
