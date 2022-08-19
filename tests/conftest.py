from __future__ import annotations

import io
import os
from typing import Callable
from typing import Iterator

import inkex
import pytest


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
