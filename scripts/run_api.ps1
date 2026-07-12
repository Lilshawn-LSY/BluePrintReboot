param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

try {
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $entrypoint = Join-Path $repoRoot "api\main.py"

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Missing repository environment at .venv. Run .\scripts\dev_setup.ps1 first."
    }
    if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) {
        throw "FastAPI entrypoint api\main.py was not found in the repository."
    }

    Set-Location -LiteralPath $repoRoot
    & $venvPython -c "import fastapi, uvicorn; from api.main import app; assert app.version"
    if ($LASTEXITCODE -ne 0) {
        throw "The repository environment is invalid. Reinstall requirements with .\scripts\dev_setup.ps1."
    }

    Write-Host "Starting the read-only API at http://127.0.0.1:$Port"
    & $venvPython -m uvicorn api.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "The API exited with code $LASTEXITCODE. Check whether port $Port is available."
    }
} catch {
    Write-Error $_.Exception.Message
    Write-Host "API launch failed. No server was started."
    exit 1
}
