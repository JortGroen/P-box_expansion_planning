param(
    [switch] $Recreate
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath ".").Path
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if ($Recreate -and (Test-Path -LiteralPath $VenvDir)) {
    Write-Error "Refusing to remove .venv automatically. Delete it manually, then rerun this script."
    exit 1
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$env:PIP_NO_INDEX = "0"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& $VenvPython -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Ready: $VenvPython"
