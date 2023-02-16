from __future__ import annotations

import io
import os
import re
import selectors
import shutil
import subprocess
import sys
import threading
from itertools import count
from pathlib import Path
from typing import Callable
from typing import Generator
from typing import Iterator
from zipfile import ZipFile

import inkex
import pytest
from lxml import etree
from pyvirtualdisplay.display import Display

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


@pytest.fixture(scope="session")
def dist_zip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build extension distribution zip file."""
    hatch = shutil.which("hatch")
    if hatch is None:
        pytest.skip("hatch is not installed")

    distdir = tmp_path_factory.mktemp("dist")
    subprocess.run(
        (hatch, "build", "--clean", "--target=zipped-directory", distdir),
        check=True,
    )

    output = list(p for p in distdir.iterdir() if p.suffix == ".zip")
    assert len(output) == 1
    return output.pop()


@pytest.fixture
def tmp_inkscape_profile(tmp_path: Path) -> Path:
    """Install extension in tmp Inkscape profile directory."""
    profile_dir = tmp_path / "inkscape"
    os.environ["INKSCAPE_PROFILE_DIR"] = os.fspath(profile_dir)
    return profile_dir


@pytest.fixture
def extensions_installed(tmp_inkscape_profile: Path, dist_zip: Path) -> None:
    """Install extension in tmp Inkscape profile directory."""
    ZipFile(dist_zip).extractall(tmp_inkscape_profile / "extensions")


class _CanNotStartService(Exception):
    """Exception raised when server fails to start."""


@pytest.fixture(scope="session")
def xvfb_display() -> Generator[Display, None, None]:
    """Start Xvfb virtual display server."""
    try:
        display = Display(visible=False, manage_global_env=False)
    except Exception as exc:
        raise _CanNotStartService(f"can not start Xvfb: {exc}") from exc

    with display:
        yield display


@pytest.fixture
def xserver(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure that an X server is available.

    By default, this starts an Xvfb virtual server to avoid flashing of GUI on screen.
    If Xvfb is unavailable, fall back to using current X server.

    """
    try:
        xvfb_display = request.getfixturevalue("xvfb_display")
    except _CanNotStartService as exc:
        if not os.environ.get("DISPLAY"):
            pytest.skip(str(exc))
        return  # just use system X server (it's likely xvfb is not installed)

    monkeypatch.setenv("DISPLAY", xvfb_display.new_display_var)


@pytest.fixture(scope="session")
def local_session_dbus_daemon(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[str, None, None]:
    tmp = tmp_path_factory.mktemp("dbus")
    services_dir = tmp / "services"
    services_dir.mkdir()
    config_file = tmp / "dbus_cfg"
    config_file.write_text(
        # Copied from python-dbusmock
        f"""<!DOCTYPE busconfig PUBLIC
            "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
            "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd"
        >
        <busconfig>
          <type>session</type>
          <keep_umask/>
          <listen>unix:tmpdir={tmp}</listen>
          <!-- Omit standard services -->
          <servicedir>{services_dir}</servicedir>
          <policy context="default">
            <allow send_destination="*" eavesdrop="true"/>
            <allow eavesdrop="true"/>
            <allow own="*"/>
          </policy>
        </busconfig>
        """
    )

    cmd = ("dbus-daemon", "--nofork", f"--config-file={config_file}", "--print-address")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    except Exception as exc:
        pytest.skip(f"can not start dbus-daemon: {exc}")

    assert proc.stdout is not None
    session_bus_address = next(proc.stdout).strip()
    try:
        yield session_bus_address
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def local_session_dbus(
    local_session_dbus_daemon: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", local_session_dbus_daemon)


@pytest.fixture
def capture_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Capture stderr output from extensions.

    This fixture is useful when running Inkscape integration tests.  Inkscape
    normally captures any stderr from the extension itself, displaying it
    to the user in a GUI dialog.  This does not work well in our headless Xvfb
    based tests, as no one ever gets to see the dialog, and things just hang.

    """
    logfile = tmp_path / "log.txt"
    logfile.touch()
    monkeypatch.setenv("INKEX_BH_LOG_FILE", os.fspath(logfile))

    running = True

    def echo(s: str) -> None:
        sys.stderr.write(s)
        sys.stderr.flush()

    def watcher() -> None:
        with logfile.open() as fp:
            # the default EpollSelector doesn't work with regular files
            sel = selectors.SelectSelector()
            sel.register(fp, selectors.EVENT_READ)
            while running:
                for _ in sel.select(timeout=0.2):
                    echo(fp.read(1024))
            echo(fp.read())

    t = threading.Thread(target=watcher)
    t.start()
    try:
        yield
    finally:
        running = False
        t.join()
