# mypy: ignore-errors
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import inkex
import pytest
from inkex.command import INKSCAPE_EXECUTABLE_NAME

from inkex_bh.constants import BH_INSET_EXPORT_ID
from inkex_bh.constants import BH_INSET_VISIBLE_LAYERS
from inkex_bh.create_inset import CreateInset
from inkex_bh.create_inset import export_png
from inkex_bh.create_inset import log
from inkex_bh.create_inset import png_dimensions
from inkex_bh.create_inset import run_command


def get_inkscape_version_tuple():
    # Can set $INKSCAPE_COMMAND to specify a specific executable
    try:
        proc = subprocess.run(
            [INKSCAPE_EXECUTABLE_NAME, "--version"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return (-1,)
    m = re.match(r"Inkscape (\d+)\.(\d+)\.(\d+) ", proc.stdout)
    if m is None:
        return (-1,)
    return tuple(map(int, m.groups()))


inkscape_version = get_inkscape_version_tuple()


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


@pytest.fixture
def verbose_logging():
    saved = log.set_verbosity(True)
    try:
        yield
    finally:
        log.set_verbosity(saved)


pytestmark = pytest.mark.usefixtures("assert_quiet")


def test_png_dimensions():
    png_data = Path(__file__).parent.joinpath("test-123x456.png").read_bytes()
    assert png_dimensions(png_data) == (123, 456)


@pytest.mark.skipif(inkscape_version < (1, 0), reason="Requires Inkscape >= 1.0")
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


def test_run_command_eats_stdout(capsys):
    run_command([sys.executable, "-c", "print('output')"])


@pytest.mark.usefixtures("verbose_logging")
def test_run_command_verbose(capsys):
    run_command([sys.executable, "-c", "print('output')"])
    output = capsys.readouterr()
    assert "output" in output.err
    assert output.out == ""


def test_run_command_missing_ok(capsys):
    run_command(["this-does-not-exist-f38csed"], missing_ok=True)
    output = capsys.readouterr()
    assert "Can not find executable" in output.err
    assert output.out == ""


def test_run_command_failure(capsys):
    with pytest.raises(SystemExit):
        run_command([sys.executable, "-c", "import sys; print('failed'); sys.exit(42)"])
    output = capsys.readouterr()
    assert "failed" in output.err
    assert output.out == ""


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
