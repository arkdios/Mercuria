#!/bin/bash


PROJECT_ROOT=$(dirname $(realpath $0))
source $PROJECT_ROOT/bash/print-platform-id.sh
VENV=$($PROJECT_ROOT/bash/print-venv-path.sh)

echo "Removing old venv."
rm -rf $VENV

echo "Creating venv: $VENV"
python3 -m venv $VENV

echo "Installing requirements."
$VENV/bin/pip3 install -r $PROJECT_ROOT/setup/requirements.txt
