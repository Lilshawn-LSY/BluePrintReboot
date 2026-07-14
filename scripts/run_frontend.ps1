param(
    [int]$Port = 3000,
    [string]$NodeHome
)

$ErrorActionPreference = "Stop"

try {
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $frontendRoot = Join-Path $repoRoot "frontend"
    $packageJson = Join-Path $frontendRoot "package.json"
    $nodeModules = Join-Path $frontendRoot "node_modules"
    . (Join-Path $PSScriptRoot "resolve_node.ps1")
    $node = Resolve-BlueprintNode -NodeHome $NodeHome

    if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
        throw "Frontend package.json was not found."
    }
    if (-not (Test-Path -LiteralPath $nodeModules -PathType Container)) {
        throw "Frontend dependencies are missing. Run .\scripts\frontend_setup.ps1 -NodeHome <portable-node-directory>."
    }

    Set-Location -LiteralPath $frontendRoot
    Write-Host "Using Node.js $($node.NodeVersion) and npm $($node.NpmVersion)."
    Write-Host "Starting the BluePrintReboot frontend at http://127.0.0.1:$Port"
    Invoke-BlueprintNpm -Node $node -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", $Port)
    if ($LASTEXITCODE -ne 0) {
        throw "The frontend exited with code $LASTEXITCODE."
    }
} catch {
    Write-Error $_.Exception.Message
    Write-Host "Frontend launch failed. The existing Streamlit application is unaffected."
    exit 1
}
