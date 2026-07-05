param(
    [int]$Port = 8501
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
        throw "Missing .venv. Run .\scripts\dev_setup.ps1 before .\scripts\run_app.ps1."
    }

    if (-not (Test-Path (Join-Path $repoRoot "app.py") -PathType Leaf)) {
        throw "Streamlit entrypoint app.py was not found in $repoRoot."
    }

    Invoke-CheckedCommand -Description "Verify Streamlit import" -FilePath $venvPython -ArgumentList @("-c", "import streamlit")

    Write-Phase "Launch BluePrintReboot"
    Write-Host "Opening Streamlit on http://localhost:$Port"
    & $venvPython -m streamlit run app.py --server.port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Streamlit exited with code $LASTEXITCODE. Check that port $Port is available, or try .\scripts\run_app.ps1 -Port 8502."
    }

    exit 0
} catch {
    Write-Error $_.Exception.Message
    Write-Host "Launch failed. If this is a fresh clone, run .\scripts\dev_setup.ps1 first."
    exit 1
}
