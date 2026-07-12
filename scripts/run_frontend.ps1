param(
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

try {
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $frontendRoot = Join-Path $repoRoot "frontend"
    $packageJson = Join-Path $frontendRoot "package.json"
    $nodeModules = Join-Path $frontendRoot "node_modules"
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue

    if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
        throw "Frontend package.json was not found."
    }
    if (-not $npm) {
        throw "Node.js and npm were not found on PATH. Install Node.js 22.13 or newer."
    }
    if (-not (Test-Path -LiteralPath $nodeModules -PathType Container)) {
        throw "Frontend dependencies are missing. Run npm install in the frontend directory."
    }

    Set-Location -LiteralPath $frontendRoot
    Write-Host "Starting the BluePrintReboot frontend at http://127.0.0.1:$Port"
    & $npm.Source run dev -- --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "The frontend exited with code $LASTEXITCODE."
    }
} catch {
    Write-Error $_.Exception.Message
    Write-Host "Frontend launch failed. The existing Streamlit application is unaffected."
    exit 1
}
