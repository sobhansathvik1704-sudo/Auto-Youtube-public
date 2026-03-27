#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="youtube-ai-mvp"
OUTPUT_FILE="youtube-ai-mvp.zip"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Directory '$PROJECT_DIR' not found."
  exit 1
fi

rm -f "$OUTPUT_FILE"
zip -r "$OUTPUT_FILE" "$PROJECT_DIR"
echo "Created $OUTPUT_FILE"