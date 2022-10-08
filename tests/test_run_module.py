from __future__ import annotations

import os
import re
import shutil
import sys
import types
from pathlib import Path
from subprocess import run
from typing import Callable
from typing import Iterator
from typing import TYPE_CHECKING
from venv import EnvBuilder
from zipfile import ZipFile

import pytest
from conftest import SvgMaker

if TYPE_CHECKING:
    from _typeshed import StrPath
else:
    StrPath = object


if sys.version_info >= (3, 9):
    from importlib import resources
else:
    import importlib_resources as resources


@pytest.fixture
def chdir() -> Iterator[Callable[[StrPath], None]]:
    saved = os.getcwd()
    try:
        yield os.chdir
    finally:
        os.chdir(saved)


@pytest.fixture
def package_data_run_module_py() -> Iterator[Path]:
    """Get path to run-module.py in package data."""
    run_module = resources.files("inkex_bh") / "extensions/run-module.py"
    with resources.as_file(run_module) as run_module_py:
        yield run_module_py


@pytest.fixture(scope="session")
def inkex_zip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build extension zip file."""
    # Build extension zip file
    hatch = shutil.which("hatch")
    if hatch is None:
        pytest.skip("hatch is not installed")
    dist = tmp_path_factory.mktemp("dist")
    run(
        ("hatch", "build", "--clean", "--target", "zipped-directory", os.fspath(dist)),
        check=True,
    )
    # FIXME: skip test if hatch not installed
    zips = {p for p in dist.iterdir() if p.suffix == ".zip"}
    assert len(zips) == 1
    return zips.pop()


@pytest.fixture
def installed_run_module_py(inkex_zip: StrPath, tmp_path: Path) -> Path:
    """Construct a dummy Inkscape extensions directory with our extensions installed.

    Return path to run-module.py in that directory.
    """
    # Unpack in fresh "extensions" directory
    extensions = tmp_path / "extensions"
    with ZipFile(inkex_zip) as zf:
        zf.extractall(extensions)

    run_module_py = extensions / "org.dairiki.inkex_bh/run-module.py"
    assert run_module_py.is_file()
    return run_module_py


class CustomEnvBuilder(EnvBuilder):
    env_exe: str

    def post_setup(self, context: types.SimpleNamespace) -> None:
        super().post_setup(context)
        self.env_exe = context.env_exe


@pytest.fixture
def venv_python(tmp_path: Path) -> str:
    """Return path to python interpreter installed in it's own fresh private venv"""
    if sys.version_info >= (3, 9):
        builder = CustomEnvBuilder(with_pip=True, upgrade_deps=True)
    else:
        builder = CustomEnvBuilder(with_pip=True)
    builder.create(tmp_path / "venv")
    return builder.env_exe


class RunModuleTest:
    def __init__(self, svg_maker: SvgMaker):
        self.svg_maker = svg_maker

    def make_svg_file(self) -> str:
        svg_maker = self.svg_maker
        sym = svg_maker.add_symbol(id="test1")
        svg_maker.add_use(sym)
        return svg_maker.as_file()

    def __call__(self, script: StrPath, executable: StrPath | None = None) -> None:
        if executable is None:
            executable = sys.executable

        proc = run(
            (executable, script, "-m", "count_symbols", self.make_svg_file()),
            check=True,
            capture_output=True,
            text=True,
        )
        assert re.search(r"\s1:\s+#?test1\b", proc.stderr)


@pytest.fixture
def assert_run_module_works(svg_maker: SvgMaker) -> RunModuleTest:
    return RunModuleTest(svg_maker)


def test_run_module(
    package_data_run_module_py: Path, assert_run_module_works: RunModuleTest
) -> None:
    assert_run_module_works(package_data_run_module_py, sys.executable)


def test_run_module_in_extensions_dir(
    package_data_run_module_py: Path,
    chdir: Callable[[StrPath], None],
    assert_run_module_works: RunModuleTest,
) -> None:
    chdir(package_data_run_module_py.parent)
    assert_run_module_works(package_data_run_module_py.name, sys.executable)


def test_run_module_in_installed_extensions(
    venv_python: StrPath,
    installed_run_module_py: StrPath,
    assert_run_module_works: RunModuleTest,
) -> None:
    run((venv_python, "-m", "pip", "install", "inkex"), check=True)
    assert_run_module_works(installed_run_module_py, venv_python)
