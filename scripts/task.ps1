param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("test", "run", "figures")]
    [string] $Task
)

$ErrorActionPreference = "Stop"

switch ($Task) {
    "test" {
        python -m pytest
        exit $LASTEXITCODE
    }
    "run" {
        python -m src.runner configs/bootstrap_manifest.yaml --output-dir experiments/bootstrap
        exit $LASTEXITCODE
    }
    "figures" {
        python -m paper.figures.build
        exit $LASTEXITCODE
    }
}
