#!/bin/bash

USAGE="Print the full path to a Python virtual environment to be used by the current OS for ChessCraft Python scripts.

Usage:
        \$(print-venv-path.sh)/bin/python3 my_script.py
"

if [[ $@ == *"-h"* ]] ; then
    echo "$USAGE"
    exit 0
fi

PROJECT_ROOT=$(dirname $(dirname $(realpath $0)))

PLATFORM_ID=$($PROJECT_ROOT/src/print-platform-id.sh)
if [[ $? != 0 ]] ; then
    PLATFORM_ID="linux-unknown"
fi

echo $PROJECT_ROOT/venv/${PLATFORM_ID}
