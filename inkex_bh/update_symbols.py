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
from __future__ import annotations

import json
import os
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Iterable
from typing import Mapping

import inkex
from inkex.command import inkscape
from inkex.elements import load_svg
from inkex.localization import inkex_gettext as _


def _get_data_path(user: bool = False) -> Path:
    """Get path to Inkscape's system (or user) data directory."""
    stdout = inkscape(
        None,
        system_data_directory=not user,
        user_data_directory=user,
    )
    if isinstance(stdout, bytes):  # inkex 1.0
        stdout = stdout.decode("utf-8", errors="replace")
    return Path(stdout.strip())


def _get_symbol_path(data_paths: Iterable[Path], name: str) -> Path | None:
    """Get path to directory containing named symbol set.

    Name is determined by examing ``METADATA.json`` files found
    under Inkscape's user symbol library directory.

    """
    for data_path in data_paths:
        for dirpath, dirnames, filenames in os.walk(data_path / "symbols"):
            path = Path(dirpath)
            if "METADATA.json" not in filenames:
                continue
            # do not recurse below dirs containing METADATA.json file
            dirnames[:] = []

            with open(path / "METADATA.json", "rb") as fp:
                meta = json.load(fp)
            if meta.get("name") == name:
                return path
    return None


def _symbol_scale(svg_path: Path) -> str:
    """Deduce symbol scale from filename."""
    m = re.search(r"-(\d+)to(\d+)\Z", svg_path.stem)
    if m is not None:
        return ":".join(m.groups())
    return "48:1"


def _has_unscoped_ids(symbol: inkex.Symbol) -> bool:
    """Check that symbol has no unnecessary id attributes set."""
    id_pfx = symbol.get("id") + ":"
    return not all(
        elem.get("id").startswith(id_pfx) for elem in symbol.iterfind(".//*[@id]")
    )


def _load_symbols_from_svg(svg_path: Path) -> dict[str, inkex.Symbol]:
    with svg_path.open("rb") as fp:
        svg = load_svg(fp)

    symbols: dict[str, inkex.Symbol] = {}
    for symbol in svg.getroot().findall("./svg:defs/svg:symbol[@id]"):
        id_ = symbol.get("id")
        if _has_unscoped_ids(symbol):
            inkex.errormsg(
                _("WARNINGS: skipping symbol #{} that contains unscoped id(s)").format(
                    id_
                )
            )
        elif id_ in symbols:
            inkex.errormsg(
                _("WARNING: skipping symbol #{} with duplicate id in {}").format(
                    id_, svg_path.name
                )
            )
        else:
            symbols[id_] = symbol
    return symbols


def load_symbols(
    data_paths: Iterable[Path] | None = None,
    name: str = "bh-symbols",
) -> Mapping[str, inkex.Symbol]:
    if data_paths is None:
        # system and user data paths
        data_paths = [_get_data_path(False), _get_data_path(True)]

    symbol_path = _get_symbol_path(data_paths, name)
    if symbol_path is None:
        raise RuntimeError(f"can not find symbol set with name {name!r}")

    svg_paths = (
        svg_path
        for svg_path in symbol_path.iterdir()
        if svg_path.suffix == ".svg" and svg_path.is_file()
    )

    def nonstandard_scales_last(svg_path: Path) -> tuple[int, str]:
        # sort 48:1 scale first, then by scale
        scale = _symbol_scale(svg_path)
        sort_first = scale == "48:1"
        return 0 if sort_first else 1, scale

    symbols_by_id: dict[str, inkex.Symbol] = {}
    for svg_path in sorted(svg_paths, key=nonstandard_scales_last):
        symbols = _load_symbols_from_svg(svg_path)
        if any(id_ in symbols_by_id for id_ in symbols):
            inkex.errormsg(
                _("WARNING: {} contains duplicate symbol ids, skipping").format(
                    svg_path.name
                )
            )
        else:
            symbols_by_id.update(symbols)
    return symbols_by_id


def update_symbols(
    svg: inkex.SvgDocumentElement, symbols: Mapping[str, inkex.Symbol]
) -> None:
    defs = svg.findone("svg:defs")
    for sym in defs.findall("./svg:symbol[@id]"):
        assert isinstance(sym, inkex.Symbol)
        try:
            replacement = symbols[sym.get("id")]
        except KeyError:
            continue
        inkex.errormsg(f"Updating #{sym.get('id')}")
        sym.replace_with(replacement)


class UpdateSymbols(inkex.EffectExtension):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")

    def effect(self) -> bool:
        try:
            symbols = load_symbols()
            update_symbols(self.svg, symbols)
        except Exception as exc:
            inkex.errormsg(exc)
            return False
        return True


if __name__ == "__main__":
    UpdateSymbols().run()
