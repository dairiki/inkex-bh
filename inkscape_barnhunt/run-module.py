#!/usr/bin/env python
"""Stub script.

Our scripts are packaged as executable python modules.  Inkscape seems
not able to call those directly, but rather wants to run a plain .py
script.

This essentially does a:

    python -m <module> [args]

Where <module> is taken from the --module (or -m) command line parameter.

"""
import argparse
import runpy
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--module", "-m", required=True)

opts, sys.argv[1:] = parser.parse_known_intermixed_args()
runpy.run_module(opts.module, run_name="__main__")
