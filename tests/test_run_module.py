from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path
from subprocess import run
from typing import Callable
from typing import Iterator
from typing import TYPE_CHECKING
from venv import EnvBuilder

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


@pytest.fixture
def installed_run_module_py(
    tmp_inkscape_profile: Path, extensions_installed: None
) -> Path:
    """Construct a dummy Inkscape extensions directory with our extensions installed.

    Return path to run-module.py in that directory.
    """
    run_module_py = tmp_inkscape_profile.joinpath(
        "extensions/org.dairiki.inkex_bh/run-module.py"
    )
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

    def check_output(self, output: str) -> None:
        assert re.search(r"\s1:\s+#?test1\b", output)

    def run_script(self, script: StrPath, executable: StrPath | None = None) -> str:
        if executable is None:
            executable = sys.executable

        proc = run(
            (executable, script, "-m", "count_symbols", self.make_svg_file()),
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stderr

    def __call__(self, script: StrPath, executable: StrPath | None = None) -> None:
        output = self.run_script(script, executable)
        self.check_output(output)


@pytest.fixture
def run_module_test(svg_maker: SvgMaker) -> RunModuleTest:
    return RunModuleTest(svg_maker)


def test_run_module(
    package_data_run_module_py: Path, run_module_test: RunModuleTest
) -> None:
    run_module_test(package_data_run_module_py, sys.executable)


def test_run_module_in_extensions_dir(
    package_data_run_module_py: Path,
    chdir: Callable[[StrPath], None],
    run_module_test: RunModuleTest,
) -> None:
    chdir(package_data_run_module_py.parent)
    run_module_test(package_data_run_module_py.name, sys.executable)


def test_run_module_in_installed_extensions(
    venv_python: StrPath,
    installed_run_module_py: StrPath,
    run_module_test: RunModuleTest,
) -> None:
    run((venv_python, "-m", "pip", "install", "inkex"), check=True)
    run_module_test(installed_run_module_py, venv_python)


def test_run_module_diverts_stderr(
    installed_run_module_py: StrPath,
    run_module_test: RunModuleTest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "log.txt"
    monkeypatch.setenv("INKEX_BH_LOG_FILE", os.fspath(log_file))
    output = run_module_test.run_script(installed_run_module_py)
    run_module_test.check_output(log_file.read_text())
    assert output == ""
