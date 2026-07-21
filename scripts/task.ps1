param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("test", "test-fast", "test-full", "run", "figures", "ownership")]
    [string] $Task,

    [string[]] $Paths = @()
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath ".").Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Error "Project .venv not found. Run: .\scripts\setup_venv.ps1"
    exit 1
}

$TmpRoot = Join-Path $RepoRoot ".tmp"
New-Item -ItemType Directory -Force -Path $TmpRoot | Out-Null

if (-not $env:NUMBA_CACHE_DIR) {
    $NumbaCacheDir = Join-Path $TmpRoot "numba_cache"
    New-Item -ItemType Directory -Force -Path $NumbaCacheDir | Out-Null
    $env:NUMBA_CACHE_DIR = $NumbaCacheDir
}

switch ($Task) {
    { $_ -in @("test", "test-full") } {
        & $VenvPython scripts/check_agent_ownership.py --base-ref origin/main
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        $PytestBaseTemp = Join-Path $TmpRoot "pytest-full"
        & $VenvPython -m pytest --basetemp $PytestBaseTemp
        exit $LASTEXITCODE
    }
    "test-fast" {
        & $VenvPython scripts/check_agent_ownership.py --base-ref origin/main
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        $PytestBaseTemp = Join-Path $TmpRoot "pytest-fast"
        & $VenvPython -m pytest -m "not slow" --basetemp $PytestBaseTemp
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
        $OwnershipArgs = @("scripts/check_agent_ownership.py", "--base-ref", "origin/main")
        if ($Paths.Count -gt 0) {
            $OwnershipArgs += "--paths"
            $OwnershipArgs += $Paths
        }
        & $VenvPython @OwnershipArgs
        exit $LASTEXITCODE
    }
}
