import os
import re
import sys
from pathlib import Path
from subprocess import run
from typing import Callable
from typing import Iterator
from typing import TYPE_CHECKING

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
def svg_file(svg_maker: SvgMaker) -> str:
    sym = svg_maker.add_symbol(id="test1")
    svg_maker.add_use(sym)
    return svg_maker.as_file()


@pytest.fixture
def run_module_py() -> Iterator[Path]:
    run_module = resources.files("inkex_bh") / "extensions/run-module.py"
    with resources.as_file(run_module) as run_module_py:
        yield run_module_py


def test_run_module_in_extensions_dir(
    run_module_py: Path, svg_file: str, chdir: Callable[[StrPath], None]
) -> None:
    chdir(run_module_py.parent)
    proc = run(
        [sys.executable, run_module_py.name, "-m", "count_symbols", svg_file],
        check=True,
        capture_output=True,
        text=True,
    )
    assert re.search(r"\s1:\s+#?test1\b", proc.stderr)


def test_run_module_in_current_dir(run_module_py: Path, svg_file: str) -> None:
    proc = run(
        [sys.executable, os.fspath(run_module_py), "-m", "count_symbols", svg_file],
        check=True,
        capture_output=True,
        text=True,
    )
    assert re.search(r"\s1:\s+#?test1\b", proc.stderr)
