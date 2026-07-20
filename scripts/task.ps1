param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("test", "run", "figures", "ownership")]
    [string] $Task
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath ".").Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Error "Project .venv not found. Run: .\scripts\setup_venv.ps1"
    exit 1
}

if (-not $env:NUMBA_CACHE_DIR) {
    $NumbaCacheDir = Join-Path $RepoRoot ".tmp\numba_cache"
    New-Item -ItemType Directory -Force -Path $NumbaCacheDir | Out-Null
    $env:NUMBA_CACHE_DIR = $NumbaCacheDir
}

switch ($Task) {
    "test" {
        & $VenvPython scripts/check_agent_ownership.py --base-ref origin/main
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        & $VenvPython -m pytest
        exit $LASTEXITCODE
    }
    "run" {
        & $VenvPython -m src.runner configs/bootstrap_manifest.yaml --output-dir experiments/bootstrap
        exit $LASTEXITCODE
    }
    "figures" {
        & $VenvPython -m paper.figures.build
        exit $LASTEXITCODE
    }
    "ownership" {
        & $VenvPython scripts/check_agent_ownership.py --base-ref origin/main
        exit $LASTEXITCODE
    }
}
