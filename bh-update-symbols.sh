#! /bin/sh
set -e

exec 3>&1 1>&2

usage_error () {
    echo "Usage:" 1>&2
    echo 1>&2
    echo "    ${0##*/} [--verbose={true|false}] <src.svg>" 1>&2
    exit 64 # EX_USAGE
}


xsltproc_opts="--nowrite"

opts=$(getopt -o '' -l 'verbose:' -l 'tab:,id:' -- "$@")
[ $? -eq 0 ] || usage_error
eval set -- "$opts"
while [ $# -gt 0 ]; do
    case "$1" in
        --verbose)
            if [ "$2" = 'true' ]; then
                xsltproc_opts="$xsltproc_opts --stringparam verbose true"
            fi
            shift 2
            ;;
        --tab|--id)
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            usage_error
            ;;
    esac
done
[ $# -eq 1 ] || usage_error

INPUT_SVG="$1"
TRANSFORM_XSLT="${0%/*}/bh-update-symbols.xslt"

SYMBOLS_PATH=$(readlink -f ${0%/*}/../symbols)
unset library
for symbol_svg in "$SYMBOLS_PATH"/bh-*.svg; do
    echo "Using symbols from ${symbol_svg##*/}" 1>&2
    library="${library}${library:+ | }document('${symbol_svg}')"
done

exec xsltproc $xsltproc_opts --param library "$library" \
     "$TRANSFORM_XSLT" "$INPUT_SVG" 1>&3
