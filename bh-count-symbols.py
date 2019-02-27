#! /usr/bin/python
# Copyright (C) 2019 Geoffrey T. Dairiki <dairiki@dairiki.org>
''' Count symbol usage

'''
from collections import Counter, Mapping


from lxml import etree

import inkex

inkex.localize()
_ = _                           # noqa: F821

SVG_SVG = inkex.addNS('svg', 'svg')
SVG_G = inkex.addNS('g', 'svg')
SVG_USE = inkex.addNS('use', 'svg')
SVG_RECT = inkex.addNS('rect', 'svg')
SVG_SYMBOL = inkex.addNS('symbol', 'svg')
INKSCAPE_GROUPMODE = inkex.addNS('groupmode', 'inkscape')
INKSCAPE_LABEL = inkex.addNS('label', 'inkscape')
SODIPODI_INSENSTIVE = inkex.addNS('insensitive', 'sodipodi')
XLINK_HREF = inkex.addNS('href', 'xlink')

BH_NS = 'http://dairiki.org/barnhunt/inkscape-extensions'
BH_RAT_PLACEMENT = etree.QName(BH_NS, 'rat-placement')
BH_RAT_GUIDE_MODE = etree.QName(BH_NS, 'rat-guide-mode')

NSMAP = inkex.NSS.copy()
NSMAP['bh'] = BH_NS


class IdIndex(Mapping):
    def __init__(self, document):
        self.document = document

    def __getitem__(self, xml_id):
        elems = self.document.xpath('//*[@id=$xml_id]', xml_id=xml_id)
        # FIXME: warn if len(elems) > 1
        if len(elems) == 0:
            raise KeyError(xml_id)
        return elems[0]

    def __iter__(self):
        return iter(set(self.document.xpath('//@id')))

    def __len__(self):
        return len(set(self.document.xpath('//@id')))


class SymbolReferenceCounts(object):
    def __init__(self, document):
        self.document = document
        self.by_id = IdIndex(document)
        self.counts = {}

    def __getitem__(self, xml_id):
        if xml_id not in self.counts:
            elem = self.by_id[xml_id]
            self.counts[xml_id] = self._count_refs(elem)
        return self.counts[xml_id]

    def _count_refs(self, elem):
        if elem.tag == SVG_SYMBOL:
            symbol = elem.get('id')
            return Counter((symbol,))
        else:
            use_refs = elem.xpath(
                "descendant::svg:use/@xlink:href[starts-with(.,'#')]",
                namespaces=NSMAP)
            return sum((self[href[1:]] for href in use_refs),
                       Counter())


class CountSymbols(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--tab")

    def effect(self):
        document = self.document
        symbol_counts = SymbolReferenceCounts(document)

        use_refs = document.xpath(
            "//svg:use"
            "[not("
            "  ancestor-or-self::svg:symbol"
            "  | ancestor::*[contains(@style,'display:none')]"
            ")]"
            "/@xlink:href[starts-with(.,'#')]",
            namespaces=NSMAP)

        counts = sum((symbol_counts[href[1:]] for href in use_refs),
                     Counter())
        for id_, count in counts.most_common():
            inkex.errormsg("{1:4}: {0}".format(id_, count))


if __name__ == '__main__':
    CountSymbols().affect()
