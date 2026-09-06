<#
.SYNOPSIS
    Preview a documentation site locally.

.DESCRIPTION
    The shared configuration lives in willtheorangeguy/mkdocs and is pulled in
    by `INHERIT: .mkdocs-shared/...`, so a local build needs that checkout
    present. This script creates it, stages the design system exactly as CI
    does, and starts the dev server.

    Run from the root of the repository whose docs you want to preview.

    When run inside the template repository itself, the local tree is used
    instead of cloning, so changes to the shared config are visible
    immediately.

.PARAMETER Ref
    Branch or tag of the template repository to build against. Defaults to main.

.PARAMETER Port
    Port for the dev server. Defaults to 8000.

.PARAMETER Build
    Run a strict build instead of serving. This is the check CI performs.

.EXAMPLE
    .\scripts\docs-serve.ps1

.EXAMPLE
    .\scripts\docs-serve.ps1 -Build
#>
[CmdletBinding()]
param(
    [string]$Ref = 'main',
    [int]$Port = 8000,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$repo = 'https://github.com/willtheorangeguy/mkdocs'
$shared = '.mkdocs-shared'

if (-not (Test-Path 'mkdocs.yml')) {
    throw "No mkdocs.yml here. Run this from the root of the repository you want to preview."
}

# --- Obtain the shared configuration ------------------------------------

if (Test-Path 'shared/mkdocs.base.yml') {
    # We are inside the template repository. Mirror the local tree so edits
    # to the shared config take effect without a round trip through GitHub.
    Write-Host "Template repository detected; using the local tree." -ForegroundColor Cyan
    if (Test-Path $shared) { Remove-Item $shared -Recurse -Force }
    New-Item -ItemType Directory $shared | Out-Null
    Copy-Item 'shared' "$shared/shared" -Recurse
    Copy-Item 'design-system' "$shared/design-system" -Recurse
}
elseif (Test-Path $shared) {
    Write-Host "Updating $shared ..." -ForegroundColor Cyan
    git -C $shared fetch --depth 1 origin $Ref
    git -C $shared checkout --force FETCH_HEAD
}
else {
    Write-Host "Cloning shared configuration ..." -ForegroundColor Cyan
    git clone --depth 1 --branch $Ref $repo $shared
}

# --- Stage the design system, exactly as the build workflow does ---------

Write-Host "Staging design system ..." -ForegroundColor Cyan

$ds = Join-Path $shared 'design-system'
foreach ($dir in 'docs/stylesheets', 'docs/javascript', 'docs/images', 'overrides/.icons') {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory $dir -Force | Out-Null }
}

# Owned by the design system: always overwritten.
Copy-Item "$ds/stylesheets/*" 'docs/stylesheets/' -Recurse -Force
Copy-Item "$ds/javascript/*"  'docs/javascript/'  -Recurse -Force

# No-clobber, so a repo's own overrides win.
Get-ChildItem "$ds/overrides" -Recurse -File | ForEach-Object {
    $target = Join-Path 'overrides' $_.FullName.Substring((Resolve-Path "$ds/overrides").Path.Length + 1)
    if (-not (Test-Path $target)) {
        $parent = Split-Path $target -Parent
        if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory $parent -Force | Out-Null }
        Copy-Item $_.FullName $target
    }
}
Get-ChildItem "$ds/icons" -Recurse -File | ForEach-Object {
    $target = Join-Path 'overrides/.icons' $_.FullName.Substring((Resolve-Path "$ds/icons").Path.Length + 1)
    if (-not (Test-Path $target)) {
        $parent = Split-Path $target -Parent
        if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory $parent -Force | Out-Null }
        Copy-Item $_.FullName $target
    }
}
if (-not (Test-Path 'docs/images/favicon.svg')) {
    Copy-Item "$ds/images/favicon.svg" 'docs/images/favicon.svg'
}

# --- Dependencies --------------------------------------------------------

if (-not (Get-Command mkdocs -ErrorAction SilentlyContinue)) {
    Write-Host "Installing documentation dependencies ..." -ForegroundColor Cyan
    python -m pip install -r "$shared/shared/requirements-docs.txt"
}

# --- Go ------------------------------------------------------------------

if ($Build) {
    Write-Host "Building strictly (this is what CI runs) ..." -ForegroundColor Cyan
    mkdocs build --strict
}
else {
    Write-Host "Serving on http://127.0.0.1:$Port ..." -ForegroundColor Green
    mkdocs serve --dev-addr "127.0.0.1:$Port"
}
