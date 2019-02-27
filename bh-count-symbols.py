#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Count symbol usage

'''
from collections import Counter

from lxml import etree

import inkex

inkex.localize()
_ = _                           # noqa: F821

SVG_SYMBOL = inkex.addNS('symbol', 'svg')

BH_NS = 'http://dairiki.org/barnhunt/inkscape-extensions'
BH_COUNT_AS = etree.QName(BH_NS, 'count-as')

NSMAP = inkex.NSS.copy()
NSMAP['bh'] = BH_NS


class SymbolCounter(object):
    def __init__(self, document):
        self.document = document
        self.counts = {}

    def symbol_counts(self, href):
        assert href.startswith('#') and len(href) > 1
        xml_id = href[1:]
        if xml_id not in self.counts:
            self.counts[xml_id] = self._count_symbols(xml_id)
        return self.counts[xml_id]

    def _get_elem_by_id(self, xml_id):
        elems = self.document.xpath('//*[@id=$xml_id]', xml_id=xml_id)
        if len(elems) != 1:
            inkex.errormsg(_("WARNING: found %d elements for id %r") % (
                len(elems), xml_id))
        return elems[0] if elems else None

    def _count_symbols(self, xml_id):
        elem = self._get_elem_by_id(xml_id)
        if elem is None:
            return Counter()
        elif elem.tag == SVG_SYMBOL:
            symbol = elem.get(BH_COUNT_AS, '#%s' % xml_id)
            return Counter((symbol,))
        else:
            return sum(
                map(self.symbol_counts, elem.xpath(
                    "descendant-or-self::svg:use"
                    "/@xlink:href[starts-with(.,'#')]",
                    namespaces=NSMAP)),
                Counter())


class CountSymbols(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--tab")
        self.OptionParser.add_option("--include-hidden", type="inkbool")

    def effect(self):
        document = self.document

        hrefs = ("//svg:use[not(ancestor-or-self::svg:symbol)]"
                 "/@xlink:href[starts-with(.,'#')]")
        if not self.options.include_hidden:
            hrefs += "[not(ancestor::*[contains(@style,'display:none')])]"

        symbol_counts = SymbolCounter(document).symbol_counts
        counts = sum(
            map(symbol_counts, document.xpath(hrefs, namespaces=NSMAP)),
            Counter())
        for id_, count in counts.most_common():
            inkex.errormsg("{1:4}: {0}".format(id_, count))


if __name__ == '__main__':
    CountSymbols().affect()
