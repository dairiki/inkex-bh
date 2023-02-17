# mypy: ignore-errors
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import inkex
import pytest
from inkex.command import INKSCAPE_EXECUTABLE_NAME

from inkex_bh.constants import BH_INSET_EXPORT_ID
from inkex_bh.constants import BH_INSET_VISIBLE_LAYERS
from inkex_bh.create_inset import CreateInset
from inkex_bh.create_inset import export_png
from inkex_bh.create_inset import png_dimensions


_inkscape_version = None


def inkscape_version():
    # Can set $INKSCAPE_COMMAND to specify a specific executable
    global _inkscape_version
    if _inkscape_version is None:
        try:
            proc = subprocess.run(
                [INKSCAPE_EXECUTABLE_NAME, "--version"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            _inkscape_version = (-1,)
        else:
            m = re.search(r"(?m)^Inkscape (\d+)\.(\d+)\.(\d+) ", proc.stdout)
            assert m is not None
            _inkscape_version = tuple(map(int, m.groups()))
    return _inkscape_version


requires_inkscape_10 = pytest.mark.skipif(
    inkscape_version() < (1, 0), reason="Requires Inkscape >= 1.0"
)


@pytest.fixture
def effect():
    return CreateInset()


def bogus_export_png(
    svg: inkex.SvgDocumentElement,
    export_id: str,
    *,
    dpi: float = 96,
    scale: float = 0.5,
    background: str = "#ffffff",
    background_opacity: float = 1.0,
    optipng_level: int | None = None,
) -> tuple[bytes, float, float]:
    elem = svg.getElementById(export_id)
    bbox = elem.bounding_box(elem.getparent().composed_transform())
    png_w = round(scale * dpi * bbox.width / 96.0)
    png_h = round(scale * dpi * bbox.height / 96.0)
    image_scale = 96.0 / dpi
    return b"bogus png", png_w * image_scale, png_h * image_scale


@pytest.fixture
def mock_export_png(monkeypatch):
    monkeypatch.setattr("inkex_bh.create_inset.export_png", bogus_export_png)


pytestmark = pytest.mark.usefixtures("assert_quiet")


def test_png_dimensions():
    png_data = Path(__file__).parent.joinpath("test-123x456.png").read_bytes()
    assert png_dimensions(png_data) == (123, 456)


@requires_inkscape_10
@pytest.mark.parametrize("optipng_level", [None, 2])
def test_export_png(svg_maker, optipng_level):
    if optipng_level is not None and shutil.which("optipng") is None:
        raise pytest.skip("Requires optipng")

    boundary = svg_maker.add_rectangle(width=100, height=200)
    export_id = boundary.attrib["id"]
    png_data, width, height = export_png(
        svg_maker.svg, export_id, optipng_level=optipng_level
    )
    assert width == 50
    assert height == 100


@pytest.mark.usefixtures("mock_export_png")
def test_create_inset_image_size(svg_maker, run_effect, tmp_path):
    boundary = svg_maker.add_rectangle(width=100, height=200)
    svg_maker.add_layer("hidden layer", visible=False)

    export_id = boundary.attrib["id"]
    output = run_effect("--id", export_id, svg_maker.as_file())
    image = output.findone("//svg:image")
    assert image.width == 50
    assert image.height == 100
    assert image.get(BH_INSET_EXPORT_ID) == export_id
    assert image.get(BH_INSET_VISIBLE_LAYERS) == svg_maker.layer1.attrib["id"]
    assert image.get("xlink:href").startswith("data:image/png;base64,")


@pytest.mark.usefixtures("mock_export_png")
def test_recreate_inset_image(svg_maker, run_effect, tmp_path):
    boundary = svg_maker.add_rectangle(width=100, height=200)
    export_id = boundary.attrib["id"]
    image = svg_maker._add(
        "svg:image",
        attrib={
            BH_INSET_EXPORT_ID: export_id,
            BH_INSET_VISIBLE_LAYERS: svg_maker.layer1.attrib["id"],
        },
    )

    image_id = image.attrib["id"]
    output = run_effect("--id", image_id, svg_maker.as_file())

    image = output.findone("//svg:image")
    assert image.get("id") == image_id
    assert image.width == 50
    assert image.height == 100
    assert image.get(BH_INSET_EXPORT_ID) == export_id
    assert image.get(BH_INSET_VISIBLE_LAYERS) == svg_maker.layer1.attrib["id"]


@pytest.mark.usefixtures("mock_export_png")
def test_recreate_stale_inset(svg_maker, run_effect, tmp_path, capsys):
    image = svg_maker._add(
        "svg:image",
        attrib={
            BH_INSET_EXPORT_ID: "missing_id",
            BH_INSET_VISIBLE_LAYERS: svg_maker.layer1.attrib["id"],
        },
    )

    image_id = image.attrib["id"]
    assert run_effect("--id", image_id, svg_maker.as_file()) is None
    output = capsys.readouterr()
    assert "missing_id" in output.err
    assert output.out == ""


@pytest.mark.usefixtures("mock_export_png")
def test_recreate_inset_spurious_selections(svg_maker, run_effect, tmp_path, capsys):
    boundary = svg_maker.add_rectangle(width=100, height=200)
    export_id = boundary.attrib["id"]
    image = svg_maker._add(
        "svg:image",
        attrib={
            BH_INSET_EXPORT_ID: export_id,
            BH_INSET_VISIBLE_LAYERS: svg_maker.layer1.attrib["id"],
        },
    )
    image_id = image.attrib["id"]
    run_effect("--id", image_id, "--id", export_id, svg_maker.as_file())
    output = capsys.readouterr()
    assert "Ignoring non-insets in selection" in output.err
    assert output.out == ""


def test_create_inset_no_selection(svg_maker, run_effect, tmp_path, capsys):
    assert run_effect(svg_maker.as_file()) is None
    output = capsys.readouterr()
    assert "No objects selected" in output.err
    assert output.out == ""


def test_create_inset_multiple_selections(svg_maker, run_effect, tmp_path, capsys):
    id1 = svg_maker.add_rectangle().attrib["id"]
    id2 = svg_maker.add_rectangle().attrib["id"]

    assert run_effect("--id", id1, "--id", id2, svg_maker.as_file()) is None
    output = capsys.readouterr()
    assert "Select exactly one object" in output.err
    assert output.out == ""


@requires_inkscape_10
@pytest.mark.usefixtures(
    "extensions_installed", "xserver", "local_session_dbus", "capture_stderr"
)
@pytest.mark.parametrize("assert_quiet", [None])  # defeat module-wide assert_quiet
def test_integration(svg_maker, tmp_path, monkeypatch):
    # set explicit PATH so to avoid issues with extensions be run with the
    # wrong python interpreter
    command = shutil.which(INKSCAPE_EXECUTABLE_NAME)
    monkeypatch.setenv("PATH", "/bin:/usr/bin:/usr/local/bin")
    monkeypatch.setenv("INKSCAPE_COMMAND", command)

    id1 = svg_maker.add_rectangle(width=200, height=100).attrib["id"]
    outfile = tmp_path / "output.svg"
    actions = [
        f"select-by-id:{id1}",
        "org.dairiki.bh.create-inset.noprefs",
    ]
    cmd = (
        command,
        "--batch-process",
        f"--actions={';'.join(actions)}",
        f"--export-filename={outfile}",
        svg_maker.as_file(),
    )
    subprocess.run(cmd, check=True, close_fds=False)
    output = inkex.load_svg(outfile).getroot()
    image = output.findone("//svg:image")
    assert image.width == 100
    assert image.height == 50
