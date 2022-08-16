#!/bin/bash -e

# : ${INKSCAPE:=/home/dairiki/Downloads/Inkscape-0a00cf5-x86_64.AppImage}
: ${INKSCAPE:=/home/dairiki/Downloads/Inkscape-9c6d41e-x86_64.AppImage}

HERE=${0%/*}
: ${HERE:=$PWD}

export XDG_CONFIG_HOME="${HERE}/test-config"

exec "$INKSCAPE" "$@"
