# mypy: ignore-errors
import ntpath
import os
import sys
from pathlib import Path

import pytest

from inkex_bh.workarounds import _is_subpath
from inkex_bh.workarounds import mangle_cmd_for_appimage
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
    monkeypatch.setitem(os.environ, "APPIMAGE", "/tmp/appimage")
    monkeypatch.setitem(os.environ, "APPDIR", os.fspath(tmp_path))
    monkeypatch.setitem(
        os.environ,
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
    inkscape.write_text("#!/usr/bin/env python\n")
    inkscape.chmod(0o555)

    ld_linux = tmp_path / "lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"
    ld_linux.parent.mkdir(parents=True)
    ld_linux.touch()

    return {
        "inkscape_path": inkscape,
        "ldlinux_path": ld_linux,
    }


def test_mangle_cmd_for_appimage(mock_appimage):
    mangled = mangle_cmd_for_appimage(["inkscape", "arg"])
    if sys.platform == "linux":
        assert Path(mangled[0]).name.startswith("ld-linux")
        assert mangled[4:] == (os.fspath(mock_appimage["inkscape_path"]), "arg")
    else:
        assert mangled == ("inkscape", "arg")


@pytest.mark.skipif(sys.platform != "linux", reason="Only relevant for Linux")
def test_mangle_cmd_for_appimage_no_ldlinux(mock_appimage):
    mock_appimage["ldlinux_path"].unlink()
    with pytest.raises(RuntimeError) as exc_info:
        mangle_cmd_for_appimage(["inkscape", "arg"])
    assert exc_info.match("Can not find ld-linux in AppImage")


def test_mangle_cmd_for_appimage_no_mangle_unless_linux(mock_appimage, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    assert mangle_cmd_for_appimage(["inkscape", "arg"]) == ("inkscape", "arg")


def test_mangle_cmd_for_appimage_no_mangle_unless_appimage(mock_appimage, monkeypatch):
    monkeypatch.delitem(os.environ, "APPIMAGE", raising=False)
    assert mangle_cmd_for_appimage(["inkscape", "arg"]) == ("inkscape", "arg")


def test_mangle_cmd_for_appimage_no_mangle_missing_executable(mock_appimage):
    assert mangle_cmd_for_appimage(["missing", "arg"]) == ("missing", "arg")


def test_mangle_cmd_for_appimage_no_mangle_non_appimage_executable(mock_appimage):
    assert mangle_cmd_for_appimage(["/usr/bin/true", "arg"]) == ("/usr/bin/true", "arg")
