#!/usr/bin/env python
"""Stub script.

Our scripts are packaged as executable python modules.  Inkscape seems
not able to call those directly, but rather wants to run a plain .py
script.

This essentially does a:

    python -m inkex_bh.<module> [args]

Where <module> is taken from the --module (or -m) command line parameter.

"""
import argparse
import os
import runpy
import sys
from contextlib import ExitStack
from importlib import import_module
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path

PACKAGE = "inkex_bh"


def import_module_from_file(module_name: str, path: str) -> None:
    """Import a module or package from a specific source (``.py``) file

    This bypasses the normal search of ``sys.path``, etc., directly
    importing the module from the specified python source file.

    The imported module is registered, as usual, in ``sys.modules``.

    If the path to the source file is relative, it is interpreted
    relative to the directory containing this script.

    """
    # Copied more-or-less verbatim from:
    # https://docs.python.org/3/library/importlib.html?highlight=import#importing-a-source-file-directly
    here = Path(__file__).parent
    spec = spec_from_file_location(module_name, here / path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Can not find {module_name}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


# Here we explicitly import inkex_bh into sys.modules. Once that's
# done, its sub-packages should be importable, regardless of whether
# it's included in sys.path or not, since they will be resolved
# via index_bh.__path__.
try:
    # Attempt normal import (from sys.path).  Python, when running a
    # script, always prepends the script's directory to sys.path, so
    # this will find any package installed alongside this script.
    import_module(PACKAGE)
except ModuleNotFoundError:
    # Import from parent directory.  This works when run-module.py is
    # installed as package data in a subdirectory of the `inkex_bh`
    # package, e.g.:
    #
    # inkex_bh
    # ├── __init__.py
    # ├── count_symbols.py
    # └── extensions
    #     ├── count-symbols.inx
    #     └── run-module.py
    #
    import_module_from_file(PACKAGE, "../__init__.py")


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--module", "-m", required=True)
opts, sys.argv[1:] = parser.parse_known_intermixed_args()

with ExitStack() as stack:
    # Support for diverting stderr to log file (primarily for tests)
    # Normally, Inkscape captures stderr and presents it in a GUI dialog
    log_file = os.environ.get("INKEX_BH_LOG_FILE")
    if log_file:
        try:
            fp = open(log_file, "a")
        except OSError as exc:
            print(f"{log_file}: {exc}", file=sys.stderr)
        else:
            sys.stderr = stack.enter_context(fp)

    runpy.run_module(f"{PACKAGE}.{opts.module}", run_name="__main__")
