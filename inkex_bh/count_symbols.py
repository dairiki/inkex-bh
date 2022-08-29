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
""" Count symbol usage

"""
import functools
from argparse import ArgumentParser
from typing import Counter
from typing import Iterable
from typing import TextIO

import inkex
from inkex.localization import inkex_gettext as _

from .constants import BH_COUNT_AS
from .constants import NSMAP

SVG_SYMBOL = inkex.addNS("symbol", "svg")


@functools.lru_cache(maxsize=None)
def _count_symbols1(use: inkex.Use) -> Counter[str]:
    href = use.href
    if href is None:
        xml_id = use.get("xlink:href")
        # FIXME: strip leading #
        inkex.errormsg(_("WARNING: found no element for href {!r}").format(xml_id))
        return Counter()

    if href.tag == SVG_SYMBOL:
        symbol = href.get(BH_COUNT_AS, f"#{href.get_id()}")
        return Counter((symbol,))

    return count_symbols(
        href.xpath(
            "descendant-or-self::svg:use[starts-with(@xlink:href,'#')]",
            namespaces=NSMAP,
        )
    )


def count_symbols(uses: Iterable[inkex.Use]) -> Counter[str]:
    """Compute counts of symbols referenced by a number of svg:use elements.

    Returns a ``collections.Counter`` instance containing reference
    counts of symbols.

    """
    return sum(map(_count_symbols1, uses), Counter())


class CountSymbols(inkex.OutputExtension):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")
        pars.add_argument("--include-hidden", type=inkex.Boolean)

    def save(self, stream: TextIO) -> None:
        pass

    def effect(self) -> None:
        document = self.document

        q = (
            "//svg:use[not(ancestor-or-self::svg:symbol)]"
            "[starts-with(@xlink:href,'#')]"
        )
        if not self.options.include_hidden:
            q += "[not(ancestor::*[contains(@style,'display:none')])]"

        counts = count_symbols(document.xpath(q, namespaces=NSMAP))
        _count_symbols1.cache_clear()

        for id_, count in counts.most_common():
            inkex.errormsg(f"{count:4}: {id_}")


if __name__ == "__main__":
    CountSymbols().run()
