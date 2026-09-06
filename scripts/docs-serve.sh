#!/usr/bin/env bash
#
# Preview a documentation site locally.
#
# The shared configuration lives in willtheorangeguy/mkdocs and is pulled in
# by `INHERIT: .mkdocs-shared/...`, so a local build needs that checkout
# present. This script creates it, stages the design system exactly as CI
# does, and starts the dev server.
#
# Run from the root of the repository whose docs you want to preview.
#
# Usage:
#   scripts/docs-serve.sh            serve on :8000
#   scripts/docs-serve.sh --build    strict build only (what CI runs)
#   REF=some-branch scripts/docs-serve.sh

set -euo pipefail

REPO="https://github.com/willtheorangeguy/mkdocs"
SHARED=".mkdocs-shared"
REF="${REF:-main}"
PORT="${PORT:-8000}"
BUILD_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --build) BUILD_ONLY=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -f mkdocs.yml ]; then
  echo "No mkdocs.yml here. Run this from the root of the repository you want to preview." >&2
  exit 1
fi

# --- Obtain the shared configuration ------------------------------------

if [ -f shared/mkdocs.base.yml ]; then
  # We are inside the template repository. Mirror the local tree so edits to
  # the shared config take effect without a round trip through GitHub.
  echo "Template repository detected; using the local tree."
  rm -rf "$SHARED"
  mkdir -p "$SHARED"
  cp -r shared "$SHARED/shared"
  cp -r design-system "$SHARED/design-system"
elif [ -d "$SHARED" ]; then
  echo "Updating $SHARED ..."
  git -C "$SHARED" fetch --depth 1 origin "$REF"
  git -C "$SHARED" checkout --force FETCH_HEAD
else
  echo "Cloning shared configuration ..."
  git clone --depth 1 --branch "$REF" "$REPO" "$SHARED"
fi

# --- Stage the design system, exactly as the build workflow does ---------

echo "Staging design system ..."
DS="$SHARED/design-system"
mkdir -p docs/stylesheets docs/javascript docs/images overrides/.icons

# Owned by the design system: always overwritten.
cp -r "$DS/stylesheets/." docs/stylesheets/
cp -r "$DS/javascript/."  docs/javascript/

# No-clobber, so a repo's own overrides win.
cp -rn "$DS/overrides/." overrides/        2>/dev/null || true
cp -rn "$DS/icons/."     overrides/.icons/ 2>/dev/null || true
cp -n  "$DS/images/favicon.svg" docs/images/favicon.svg 2>/dev/null || true

# --- Dependencies --------------------------------------------------------

if ! command -v mkdocs >/dev/null 2>&1; then
  echo "Installing documentation dependencies ..."
  python3 -m pip install -r "$SHARED/shared/requirements-docs.txt"
fi

# --- Go ------------------------------------------------------------------

if [ "$BUILD_ONLY" = true ]; then
  echo "Building strictly (this is what CI runs) ..."
  mkdocs build --strict
else
  echo "Serving on http://127.0.0.1:$PORT ..."
  mkdocs serve --dev-addr "127.0.0.1:$PORT"
fi
