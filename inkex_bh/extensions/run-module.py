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
import runpy
import sys
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path

PACKAGE = "inkex_bh"

# Here we explicitly import inkex_bh from our parent directly.  Once
# it is in sys.modules, its sub-packages should be importable,
# regarless of whether it's included in sys.path or not.

# Note that Inkscape adds the users extensions directory to sys.path,
# so if inkex_bh were installed there, these contortions are not
# strictly necessary.  However, this should work, even if inkex_bh is
# installed in a sub-directory the extensions directory.  (And it
# ensures that we get the exact correct version of inkex_bh.)

# Copied more-or-less verbatim from:
# https://docs.python.org/3/library/importlib.html?highlight=import#importing-a-source-file-directly
spec = spec_from_file_location(PACKAGE, Path(__file__).parent / "../__init__.py")
if spec is None or spec.loader is None:
    raise ModuleNotFoundError(f"Can not find {PACKAGE}")
module = module_from_spec(spec)
sys.modules[PACKAGE] = module
spec.loader.exec_module(module)

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--module", "-m", required=True)
opts, sys.argv[1:] = parser.parse_known_intermixed_args()

runpy.run_module(f"{PACKAGE}.{opts.module}", run_name="__main__")
