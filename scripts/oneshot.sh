#!/bin/bash
scriptdir=$(cd $(dirname $0); pwd -P)

# Oneshot execution script for Cline
# Usage: scripts/oneshot.sh <prompt_file>
# Executes: cline --yolo --oneshot "Execute instructions from $prompt_file"

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <prompt_file>"
    echo "Example: $0 logist/docs/prompts/01-json_validation_unit.md"
    exit 1
fi

PROMPT_FILE="$1"

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Error: Prompt file '$PROMPT_FILE' not found"
    exit 1
fi

# Read the prompt content
PROMPT_CONTENT=$(cat "$PROMPT_FILE")

echo "Executing Cline oneshot with prompt from: $PROMPT_FILE"
echo "=================================================="

# Execute the oneshot command
exec cline --yolo --oneshot "execute instructions from $PROMPT_FILE" 2>&1 | tee -a $scriptdir/oneshot.out
