#!/bin/bash

set -e

dir=$1
test -n "$dir" && cd "$dir"

if ! test -f requirements.txt; then
  echo Error: $(pwd) does not appear to be a python project 1>&2
  exit 1
fi

echo Preparing $(pwd) as a python project

if ! test -f .checklist.md; then
  echo "[✓] Tracking no items yet" > .checklist.md
  echo Created empty checklist at $(pwd)/.checklist.md
else
  echo Checklist already exists at $(pwd)/.checklist.md
fi

echo Initializing and activating venv
test -d venv || /usr/bin/python3 -m venv venv
source venv/bin/activate

echo Building project ...
pip install -e . > .prepare-build.out 2>&1
test -f requirements-dev.txt && pip install -r requirements-dev.txt >> .prepare-build.out 2>&1
echo Successful build output in $(pwd)/.prepare-build.out

extra=
grep -q pytest-timeout requirements-dev.txt 2>/dev/null && extra="--timeout=15"
echo running pytest $extra -x ...
if test -f requirements-dev.txt && grep -q pytest requirements-dev.txt; then
  if pytest $extra -x > .prepare-pytest-x.out 2>&1; then
    echo All pytests appeared to succeed.  output in $(pwd)/.prepare-pytest-x.out
  else
    echo pytest $extra -x failed'!' -- output in $(pwd)/.prepare-pytest-x.out
  fi
else
  echo No pytests detected.
fi

echo running git status ...
git status -s > .prepare-git-status.out
if ! test -s .prepare-git-status.out; then
  git status > .prepare-git-status.out
  echo No local git modifications in $(pwd)/.prepare-git-status.out
else
  git status > .prepare-git-status.out
  echo Local git modifications in $(pwd)/.prepare-git-status.out
fi
