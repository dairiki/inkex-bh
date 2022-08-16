#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Count symbol usage

'''
import functools
from argparse import ArgumentParser
from typing import Counter
from typing import Iterable
from typing import TextIO

from lxml import etree

import inkex
from inkex.localization import inkex_gettext as _

SVG_SYMBOL = inkex.addNS('symbol', 'svg')

NSMAP = {
    **inkex.NSS,
    "bh": "http://dairiki.org/barnhunt/inkscape-extensions",
}
BH_COUNT_AS = f"{{{NSMAP['bh']}}}count-as"


@functools.lru_cache(maxsize=None)
def _count_symbols1(use: inkex.Use) -> Counter[str]:
    # FIXME: memoize?
    href = use.href
    if href is None:
        xml_id = use.get("xlink:href")
        # FIXME: strip leading #
        inkex.errormsg(
            _("WARNING: found no element for href {!r}").format(xml_id)
        )
        return Counter()

    if href.tag == SVG_SYMBOL:
        symbol = href.get(BH_COUNT_AS, f"#{href.eid}")
        return Counter((symbol,))
    else:
        return count_symbols(
            href.xpath(
                "descendant-or-self::svg:use[starts-with(@xlink:href,'#')]",
                namespaces=NSMAP
            )
        )


def count_symbols(uses: Iterable[inkex.Use]) -> Counter[str]:
    """Compute counts of symbols referenced by a number of svg:use elements.

    Returns a ``collections.Counter`` instance containing reference counts of symbols.

    """
    return sum(map(_count_symbols1, uses), Counter())


class CountSymbols(inkex.OutputExtension):  # type: ignore
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


if __name__ == '__main__':
    CountSymbols().run()
