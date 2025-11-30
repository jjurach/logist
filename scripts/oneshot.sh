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

# Verify meta-prompt file exists
META_PROMPT_FILE="$scriptdir/../docs/prompts/_meta_prompt_instructions.md"
if [[ ! -f "$META_PROMPT_FILE" ]]; then
    echo "Warning: Meta-prompt file '$META_PROMPT_FILE' not found"
    META_PROMPT_CONTENT=""
else
    META_PROMPT_CONTENT=$(cat "$META_PROMPT_FILE")
fi

# Read the prompt content
PROMPT_CONTENT=$(cat "$PROMPT_FILE")

echo "Executing Cline oneshot: $PROMPT_BASENAME"
echo "=================================================="

# Combine meta-prompt and prompt content with clear file source indicator
COMBINED_CONTENT="[META-PROMPT: $META_PROMPT_FILE]
${META_PROMPT_CONTENT}

[PROMPT FILE: $PROMPT_FILE]
${PROMPT_CONTENT}"

# Execute the oneshot command with combined content
echo "$COMBINED_CONTENT" | exec cline --yolo --oneshot "Execute the instructions. Meta-prompt provides common procedures, prompt file contains the specific task." 2>&1 | tee -a $scriptdir/oneshot.out