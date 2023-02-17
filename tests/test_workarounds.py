# mypy: ignore-errors
import ntpath
import os
import shutil
import sys

import inkex.command
import pytest

from inkex_bh.workarounds import _is_subpath
from inkex_bh.workarounds import monkeypatch_inkscape_command_for_appimage
from inkex_bh.workarounds import text_bbox_hack


@pytest.fixture
def use1(svg_maker):
    sym = svg_maker.add_symbol()
    svg_maker.add_text("1", font_size="10px", parent=sym)
    return svg_maker.add_use(sym)


@pytest.mark.xfail(reason="Bug in inkex through at least 1.2.1")
def test_text_bbox(use1):
    bbox = use1.bounding_box()
    assert bbox.y == (-10, 0)


def test_text_bbox_hack(use1):
    with text_bbox_hack(use1.root):
        bbox = use1.bounding_box()
    assert bbox.y == (-10, 0)


def test_is_subpath():
    assert not _is_subpath("/bin/inkscape", "/usr")
    assert _is_subpath("/usr/bin/inkscape", "/usr")


def test_is_subpath_different_drive(monkeypatch):
    monkeypatch.setattr("os.path", ntpath)
    assert not _is_subpath("B:\\bin\\inkscape", "C:\\bin")
    assert _is_subpath("C:\\bin\\inkscape", "C:\\bin")


@pytest.fixture
def mock_appimage(tmp_path, monkeypatch):
    monkeypatch.setenv("APPIMAGE", "/tmp/appimage")
    monkeypatch.setenv("APPDIR", os.fspath(tmp_path))
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join(
            [
                os.fspath(tmp_path / "usr/bin"),
                os.environ.get("PATH", "/usr/bin"),
            ]
        ),
    )
    inkscape = tmp_path / "usr/bin/inkscape"
    inkscape.parent.mkdir(parents=True)
    shutil.copy(sys.executable, inkscape)  # we just need an ELF executable here

    apprun = tmp_path / "AppRun"
    apprun.write_text("#!/bin/bash\n")
    apprun.chmod(0x555)

    return {
        "inkscape_path": inkscape,
        "apprun_path": apprun,
    }


@pytest.fixture
def default_inkscape(monkeypatch):
    monkeypatch.setattr(inkex.command, "INKSCAPE_EXECUTABLE_NAME", "inkscape")
    monkeypatch.delenv("INKSCAPE_COMMAND", raising=False)
    return "inkscape"


def test_monkeypatch_inkscape_command_for_appimage(mock_appimage, default_inkscape):
    monkeypatch_inkscape_command_for_appimage()
    if sys.platform == "linux":
        apprun = mock_appimage["apprun_path"]
        assert apprun.samefile(inkex.command.INKSCAPE_EXECUTABLE_NAME)
        assert apprun.samefile(os.environ["INKSCAPE_COMMAND"])
    else:
        assert inkex.command.INKSCAPE_EXECUTABLE_NAME == default_inkscape


def test_monkeypatch_inkscape_command_for_appimage_no_act_unless_linux(
    mock_appimage, default_inkscape, monkeypatch
):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch_inkscape_command_for_appimage()
    assert inkex.command.INKSCAPE_EXECUTABLE_NAME == default_inkscape


def test_monkeypatch_inkscape_command_for_appimage_no_act_unless_appimage(
    mock_appimage, default_inkscape, monkeypatch
):
    monkeypatch.delitem(os.environ, "APPIMAGE", raising=False)
    monkeypatch_inkscape_command_for_appimage()
    assert inkex.command.INKSCAPE_EXECUTABLE_NAME == default_inkscape


@pytest.mark.usefixtures("default_inkscape")
def test_monkeypatch_inkscape_command_for_appimage_missing_executable(
    mock_appimage, monkeypatch
):
    missing = "missing-command-usSf7wCG"
    monkeypatch.setattr(inkex.command, "INKSCAPE_EXECUTABLE_NAME", missing)
    monkeypatch_inkscape_command_for_appimage()
    assert inkex.command.INKSCAPE_EXECUTABLE_NAME == missing


@pytest.mark.usefixtures("default_inkscape")
def test_monkeypatch_inkscape_command_non_appimage_executable(
    mock_appimage, monkeypatch
):
    executable = "/usr/bin/true"
    monkeypatch.setattr(inkex.command, "INKSCAPE_EXECUTABLE_NAME", executable)
    monkeypatch_inkscape_command_for_appimage()
    assert inkex.command.INKSCAPE_EXECUTABLE_NAME == executable
