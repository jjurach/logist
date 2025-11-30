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

# Get the base filename for clear display
PROMPT_BASENAME=$(basename "$PROMPT_FILE")

# Get project root path for AGENTS.md
PROJECT_ROOT=$(cd "$scriptdir/../.."; pwd -P)
AGENTS_MD="$PROJECT_ROOT/AGENTS.md"

# Verify meta-prompt file exists
META_PROMPT_FILE="$scriptdir/../docs/prompts/_meta_prompt_instructions.md"
if [[ ! -f "$META_PROMPT_FILE" ]]; then
    echo "Warning: Meta-prompt file '$META_PROMPT_FILE' not found"
    if [[ -f "$AGENTS_MD" ]]; then
        FILE_ARGS="--file $AGENTS_MD --file $PROMPT_FILE"
    else
        FILE_ARGS="--file $PROMPT_FILE"
    fi
elif [[ -f "$AGENTS_MD" ]]; then
    FILE_ARGS="--file $AGENTS_MD --file $META_PROMPT_FILE --file $PROMPT_FILE"
else
    FILE_ARGS="--file $META_PROMPT_FILE --file $PROMPT_FILE"
fi

echo "Executing Cline oneshot: $PROMPT_BASENAME"
echo "=================================================="

SHORT_NAME=$(basename "$PROMPT_FILE")

# Execute the oneshot command with attached files
exec cline --yolo --oneshot $FILE_ARGS "Execute $SHORT_NAME" 2>&1 | tee -a $scriptdir/oneshot.out