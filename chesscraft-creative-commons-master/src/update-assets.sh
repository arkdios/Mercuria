#!/bin/bash

PROJECT_ROOT=$(dirname $(dirname $(realpath $0)))

set -eu
cd $PROJECT_ROOT

ASSETS_SOURCE=$HOME/projects/chesscraft/src/unity/Assets

if [ ! -d $ASSETS_SOURCE ] ; then
    echo "Source directory does not exist: $ASSETS_SOURCE"
    exit 1
fi

DEST=$PROJECT_ROOT/assets
echo "Clearing $DEST..."
rm -rf $DEST
mkdir -p $DEST

copy_files() {
    local source_dir=$1
    shift
    while read -r src ; do
        rel=${src#$ASSETS_SOURCE/}
        dest=$DEST/$rel
        mkdir -p "$(dirname $dest)"
        cp "$src" "$dest"
        (( ++count ))
    done < <(find $ASSETS_SOURCE/$source_dir "$@")
}

count=0
for source_dir in Resources Sprites ; do
    echo "Copying PNGs from Assets/$source_dir..."
    copy_files $source_dir -name "*.png"
done

for source_dir in Sounds Music ; do
    echo "Copying audio from Assets/$source_dir..."
    copy_files $source_dir \( -name "*.wav" -o -name "*.mp3" -o -name "*.ogg" -o -name "*.flac" -o -name "*.aiff" -o -name "*.m4a" \)
done

echo "Copied $count files."

# Schemas
SCHEMAS_SOURCE=$HOME/projects/chesscraft/src/web/schemas
echo "Copying schemas from $SCHEMAS_SOURCE..."
if [ ! -d $SCHEMAS_SOURCE ] ; then
    echo "Source directory does not exist: $SCHEMAS_SOURCE"
    exit 1
fi
rm -rf $PROJECT_ROOT/schemas
cp -a $SCHEMAS_SOURCE $PROJECT_ROOT/schemas
echo "Done."
