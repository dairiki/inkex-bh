#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Count symbol usage

'''
from collections import Counter

from lxml import etree

import inkex
from inkex.localization import inkex_gettext as _

SVG_SYMBOL = inkex.addNS('symbol', 'svg')

NSMAP = {
    **inkex.NSS,
    "bh": "http://dairiki.org/barnhunt/inkscape-extensions",
}
BH_COUNT_AS = f"{{{NSMAP['bh']}}}count-as"


class SymbolCounts:
    """Compute counts of symbols used by href.

    This is a callable that, when passed an href, returns a
    ``collections.Counter`` instance containing the counts of symbols
    contained within the symbol or groups at href.

    """
    def __init__(self, document):
        self.document = document
        self.counts = {}

    def __call__(self, href):
        assert href.startswith('#') and len(href) > 1
        xml_id = href[1:]
        if xml_id not in self.counts:
            self.counts[xml_id] = self._count_symbols(xml_id) 
        return self.counts[xml_id]
        
    def _get_elem_by_id(self, xml_id):
        elems = self.document.xpath('//*[@id=$xml_id]', xml_id=xml_id)
        if len(elems) != 1:
            inkex.errormsg(
                _("WARNING: found {} elements for id {!r}").format(
                    len(elems), xml_id
                )
            )
        return elems[0] if elems else None

    def _count_symbols(self, xml_id):
        elem = self._get_elem_by_id(xml_id)
        if elem is None:
            return Counter()
        elif elem.tag == SVG_SYMBOL:
            symbol = elem.get(BH_COUNT_AS, '#%s' % xml_id)
            return Counter((symbol,))
        else:
            subrefs = elem.xpath(
                "descendant-or-self::svg:use"
                "/@xlink:href[starts-with(.,'#')]",
                namespaces=NSMAP
            )
            return sum(map(self, subrefs), Counter())


class CountSymbols(inkex.OutputExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--include-hidden", type=inkex.Boolean)

    def save(self, stream):
        pass
    
    def effect(self):
        document = self.document

        q = (
            "//svg:use[not(ancestor-or-self::svg:symbol)]"
            "/@xlink:href[starts-with(.,'#')]"
        )
        if not self.options.include_hidden:
            q += "[not(ancestor::*[contains(@style,'display:none')])]"

        hrefs = document.xpath(q, namespaces=NSMAP)
        symbol_counts = SymbolCounts(document)
        counts = sum(map(symbol_counts, hrefs), Counter())

        for id_, count in counts.most_common():
            inkex.errormsg(f"{count:4}: {id_}")


if __name__ == '__main__':
    CountSymbols().run()
