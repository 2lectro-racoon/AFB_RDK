#!/bin/bash

# Usage: ./copy.sh <source_file_or_folder> <count> [destination]

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: ./copy.sh <source_file_or_folder> <count> [destination]"
    exit 1
fi

SRC_PATH="$1"
COUNT="$2"
DEST_DIR="${3:-.}"   # default = current directory

# Validate source
if [ ! -e "$SRC_PATH" ]; then
    echo "❌ Source not found: $SRC_PATH"
    exit 1
fi

# Validate count
if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
    echo "❌ Count must be a number"
    exit 1
fi

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Extract base name
BASENAME=$(basename -- "$SRC_PATH")

# Detect file vs directory
if [ -d "$SRC_PATH" ]; then
    NAME="$BASENAME"
    EXT=""
    IS_DIR=true
else
    NAME="${BASENAME%.*}"
    EXT="${BASENAME##*.}"

    if [ "$NAME" = "$EXT" ]; then
        EXT=""
    else
        EXT=".$EXT"
    fi

    IS_DIR=false
fi

# Copy loop
for ((i=1; i<=COUNT; i++))
do
    NUM=$(printf "%02d" $i)
    NEW_PATH="${DEST_DIR}/${NUM}_${NAME}${EXT}"

    # Remove existing target to allow overwrite
    if [ -e "$NEW_PATH" ]; then
        rm -rf "$NEW_PATH"
    fi

    if [ "$IS_DIR" = true ]; then
        cp -r "$SRC_PATH" "$NEW_PATH"
    else
        cp "$SRC_PATH" "$NEW_PATH"
    fi

    echo "Created: $NEW_PATH"
done

echo "✅ Done creating $COUNT copies in $DEST_DIR"