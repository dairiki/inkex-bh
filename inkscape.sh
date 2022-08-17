#!/bin/bash -e

# 1.0.2
# AppImage broken: https://gitlab.com/inkscape/inkscape/-/issues/1306
#: ${INKSCAPE:=/home/dairiki/Downloads/Inkscape-e86c870-x86_64.AppImage}

# 1.1.2
#: ${INKSCAPE:=/home/dairiki/Downloads/Inkscape-0a00cf5-x86_64.AppImage}

# 1.2.1
: ${INKSCAPE:=/home/dairiki/Downloads/Inkscape-9c6d41e-x86_64.AppImage}

HERE=${0%/*}
: ${HERE:=$PWD}

HERE=$(realpath "$HERE")
export XDG_CONFIG_HOME="${HERE}/test-config"


exec "$INKSCAPE" "$@"
