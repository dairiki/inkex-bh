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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from typing import Mapping
from typing import NamedTuple

import inkex
from inkex.command import inkscape
from inkex.elements import load_svg
from inkex.localization import inkex_gettext as _

from ._compat import ensure_str


def _get_data_path(user: bool = False) -> Path:
    """Get path to Inkscape's system (or user) data directory."""
    which = "user" if user else "system"
    stdout = ensure_str(inkscape(f"--{which}-data-directory"))
    return Path(stdout.strip())


class _SymbolDistribution(NamedTuple):
    path: Path
    metadata: dict[str, str | list[str]]

    @property
    def version(self) -> str | None:
        version = self.metadata.get("version")
        if version is not None:
            assert isinstance(version, str)
        return version

    @property
    def svg_paths(self) -> tuple[Path, ...]:
        return tuple(
            svg_path
            for svg_path in self.path.iterdir()
            if svg_path.suffix == ".svg" and svg_path.is_file()
        )


def _find_symbol_distribution(
    data_paths: Iterable[Path], name: str
) -> _SymbolDistribution:
    """Find named symbol distribution.

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
                metadata = json.load(fp)
            if metadata.get("name") == name:
                return _SymbolDistribution(path, metadata)
    raise LookupError(f"can not find symbol set with name {name!r}")


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

    symbol_distribution = _find_symbol_distribution(data_paths, name)
    inkex.errormsg(
        _("Updating symbols from {}=={}").format(name, symbol_distribution.version)
    )

    def nonstandard_scales_last(svg_path: Path) -> tuple[int, str]:
        # sort 48:1 scale first, then by scale
        scale = _symbol_scale(svg_path)
        sort_first = scale == "48:1"
        return 0 if sort_first else 1, scale

    symbols_by_id: dict[str, inkex.Symbol] = {}
    for svg_path in sorted(symbol_distribution.svg_paths, key=nonstandard_scales_last):
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


def _symbols_equal(sym1: inkex.Symbol, sym2: inkex.Symbol) -> bool:
    id1 = sym1.get("id")
    id2 = sym2.get("id")
    id_prefix = id1 + ":"

    def normalize_attrib(attrib: Mapping[str, str]) -> Mapping[str, str]:
        return {k: v for k, v in attrib.items() if k != "id" or v.startswith(id_prefix)}

    def strip_text(text: str | None) -> str:
        if text is None:
            return ""
        return text.strip()

    def ensure_text(text: str | None) -> str:
        if text is None:
            return ""
        return text

    def elements_equal(e1: inkex.BaseElement, e2: inkex.BaseElement) -> bool:
        if e1.tag != e2.tag:
            return False
        if len(e1) != len(e2):
            return False
        if strip_text(e1.tail) != strip_text(e2.tail):
            return False
        normalize_text = strip_text
        if len(e1) == 0 and strip_text(e1.text) != "":
            # text node with non-ws content, compare verbatim
            normalize_text = ensure_text
        if normalize_text(e1.text) != normalize_text(e2.text):
            return False
        if normalize_attrib(e1.attrib) != normalize_attrib(e2.attrib):
            return False
        if not all(elements_equal(c1, c2) for c1, c2 in zip(e1, e2)):
            return False
        return True

    if id1 != id2:
        return False
    return elements_equal(sym1, sym2)


@dataclass
class UpdateStats:
    total: int = 0
    known: int = 0
    updated: int = 0


def update_symbols(
    svg: inkex.SvgDocumentElement,
    symbols: Mapping[str, inkex.Symbol],
    dry_run: bool = False,
) -> UpdateStats:
    stats = UpdateStats()
    defs = svg.findone("svg:defs")
    for sym in defs.findall("./svg:symbol[@id]"):
        assert isinstance(sym, inkex.Symbol)
        stats.total += 1
        id_ = sym.get("id")
        try:
            replacement = symbols[id_]
        except KeyError:
            continue
        stats.known += 1
        if not _symbols_equal(sym, replacement):
            if dry_run:
                inkex.errormsg(f"Symbol #{id_} would be updated")
            else:
                sym.replace_with(replacement)
                inkex.errormsg(f"Symbol #{id_} updated")
            stats.updated += 1
    return stats


class UpdateSymbols(inkex.EffectExtension):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")
        pars.add_argument("--dry-run", type=inkex.Boolean, dest="dry_run")

    def effect(self) -> bool:
        dry_run = self.options.dry_run
        try:
            symbols = load_symbols()
            stats = update_symbols(self.svg, symbols, dry_run=dry_run)
        except Exception as exc:
            inkex.errormsg(exc)
            return False
        updated = f"{stats.updated} of {stats.known} known symbols"
        if stats.updated == 0:
            inkex.errormsg(f"Of {stats.known} known symbols none were out-of-date")
            return False
        elif dry_run:
            inkex.errormsg(f"DRY-RUN: would have updated {updated}")
            return False
        else:
            inkex.errormsg(f"UPDATED {updated}")
            return True


if __name__ == "__main__":
    UpdateSymbols().run()
