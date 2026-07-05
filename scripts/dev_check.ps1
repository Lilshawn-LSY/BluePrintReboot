param(
    [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"

function Write-Phase {
    param([string]$Message)

    Write-Host ""
    Write-Host "== $Message =="
}

function Invoke-CheckedCommand {
    param(
        [string]$Description,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    Write-Phase $Description
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

try {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    Set-Location $repoRoot

    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython -PathType Leaf)) {
        throw "Missing .venv. Run .\scripts\dev_setup.ps1 before .\scripts\dev_check.ps1."
    }

    $smokeCheckRelativePath = "scripts/smoke_check.py"
    $smokeCheckPath = Join-Path $repoRoot $smokeCheckRelativePath
    if (Test-Path $smokeCheckPath -PathType Leaf) {
        Invoke-CheckedCommand -Description "Run smoke check" -FilePath $venvPython -ArgumentList @($smokeCheckRelativePath)
    } else {
        Write-Phase "Run smoke check"
        Write-Host "Skipping smoke check because $smokeCheckRelativePath was not found."
    }

    if ($SmokeOnly) {
        Write-Host ""
        Write-Host "Smoke-only check complete."
        exit 0
    }

    Invoke-CheckedCommand -Description "Run pytest" -FilePath $venvPython -ArgumentList @("-m", "pytest")

    Write-Host ""
    Write-Host "BluePrintReboot checks complete."
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
