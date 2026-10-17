#!/bin/bash

# Print a platform ID like 'ubuntu-1804'

# Use /etc/os-release because lsb_release is not a core tool.
source /etc/os-release 2>/dev/null

if [[ -z $VERSION_ID ]] ; then
    VERSION_ID="unknown"
fi
# remove '.' chars
VERSION_ID=${VERSION_ID//./}

if [[ -z $ID ]] ; then
    ID="linux"
fi

echo ${ID}-${VERSION_ID}