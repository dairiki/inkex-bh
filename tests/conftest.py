from __future__ import annotations

import io
import os
import re
from itertools import count
from pathlib import Path
from typing import Callable
from typing import Iterator

import inkex
import pytest
from lxml import etree

from inkex_bh.constants import NSMAP


@pytest.fixture
def run_effect(
    effect: inkex.InkscapeExtension,
) -> Callable[..., inkex.SvgDocumentElement | None]:
    def run_effect(
        *cmd: bytes | str | os.PathLike[str],
    ) -> inkex.SvgDocumentElement | None:
        # Dereference any Paths in the command sequence
        str_cmd = tuple(
            arg if isinstance(arg, (bytes, str)) else os.fspath(arg) for arg in cmd
        )
        outfp = io.BytesIO()

        effect.run(str_cmd, output=outfp)

        if outfp.tell() == 0:
            return None  # no output
        outfp.seek(0)
        return inkex.load_svg(outfp).getroot()

    return run_effect


@pytest.fixture
def assert_no_stdout(capsys: pytest.CaptureFixture[str]) -> Iterator[None]:
    try:
        yield
    finally:
        assert capsys.readouterr().out == ""


@pytest.fixture
def assert_quiet(capsys: pytest.CaptureFixture[str]) -> Iterator[None]:
    try:
        yield
    finally:
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err == ""


class SvgMaker:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.counter = count(1)
        self.document = inkex.load_svg(Path(__file__).parent.joinpath("drawing.svg"))
        self.svg = self.document.getroot()
        defs = self.svg.find("./svg:defs", NSMAP)
        assert defs is not None
        layer1 = self.svg.find("./svg:g[@inkscape:groupmode='layer']", NSMAP)
        assert layer1 is not None
        self.defs = defs
        self.layer1 = layer1

    def _add(
        self,
        tag: str,
        parent: etree._Element | None = None,
        attrib: dict[str, str] | None = None,
    ) -> etree._Element:
        if parent is None:
            parent = self.layer1
        if attrib is None:
            attrib = {}
        # FIXME: use etree to parse tag
        m = re.search(r"\W(\w+)$", tag)
        assert m is not None

        def _qname(name: str) -> str:
            if name.startswith("{"):
                return name
            prefix, sep, localname = name.rpartition(":")
            if sep:
                return f"{{{NSMAP[prefix]}}}{localname}"
            return name

        attrib = {_qname(key): val for key, val in attrib.items()}
        attrib.setdefault("id", f"{m.group(1)}{next(self.counter)}")
        return etree.SubElement(parent, _qname(tag), attrib)

    def add_symbol(self, *, id: str | None = None) -> etree._Element:
        attrib = {}
        if id is not None:
            attrib["id"] = id
        return self._add("svg:symbol", parent=self.defs, attrib=attrib)

    def add_layer(
        self,
        label: str = "A Layer",
        *,
        visible: bool = True,
        parent: etree._Element | None = None,
    ) -> etree._Element:
        if parent is None:
            parent = self.svg
        return self._add(
            "svg:g",
            parent,
            attrib={
                "inkscape:label": label,
                "inkscape:groupmode": "layer",
                "style": "" if visible else "display:none",
            },
        )

    def add_group(
        self,
        label: str | None = None,
        *,
        parent: etree._Element | None = None,
    ) -> etree._Element:
        attrib = {}
        if label is not None:
            attrib["inkscape:label"] = label
        return self._add("svg:g", parent, attrib)

    def add_use(
        self,
        href: etree._Element,
        *,
        x: float = 0,
        y: float = 0,
        parent: etree._Element | None = None,
    ) -> etree._Element:
        return self._add(
            "svg:use",
            parent,
            attrib={
                "xlink:href": "#" + href.attrib["id"],
                "x": str(x),
                "y": str(y),
            },
        )

    def add_rectangle(
        self,
        *,
        x: float = 0,
        y: float = 0,
        width: float = 0,
        height: float = 0,
        parent: etree._Element | None = None,
    ) -> etree._Element:
        return self._add(
            "svg:rect",
            parent,
            attrib={
                "x": str(x),
                "y": str(y),
                "width": str(width),
                "height": str(height),
            },
        )

    def add_text(
        self,
        text: str,
        *,
        font_size: str = "12px",
        parent: etree._Element | None = None,
    ) -> etree._Element:
        text_elem = self._add("svg:text", parent)
        return self._add(
            "svg:tspan",
            text_elem,
            attrib={
                "style": f"font-size: {font_size};",
            },
        )

    def as_file(self) -> str:
        fn = self.tmp_path / f"svgmaker{next(self.counter)}.svg"
        with fn.open("wb") as fp:
            self.document.write(fp)
        return os.fspath(fn)

    def __str__(self) -> str:
        return etree.tostring(self.svg, pretty_print=True, encoding="unicode")


@pytest.fixture
def svg_maker(tmp_path: Path) -> SvgMaker:
    return SvgMaker(tmp_path)
