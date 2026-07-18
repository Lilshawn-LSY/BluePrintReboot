param(
    [ValidateRange(1, 65535)]
    [int]$Port = 3000,
    [string]$NodeHome
)

$ErrorActionPreference = "Stop"

try {
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $frontendRoot = Join-Path $repoRoot "frontend"
    $packageJson = Join-Path $frontendRoot "package.json"
    $nodeModules = Join-Path $frontendRoot "node_modules"
    $bindAddress = "127.0.0.1"
    $canonicalBrowserUrl = "http://${bindAddress}:$Port"
    . (Join-Path $PSScriptRoot "resolve_node.ps1")
    $node = Resolve-BlueprintNode -NodeHome $NodeHome

    if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
        throw "Frontend package.json was not found."
    }
    if (-not (Test-Path -LiteralPath $nodeModules -PathType Container)) {
        throw "Frontend dependencies are missing. Run .\scripts\frontend_setup.ps1 -NodeHome <portable-node-directory>."
    }

    Write-Host "Configured bind address: $bindAddress"
    Write-Host "Configured port: $Port"
    Write-Host "Canonical browser URL: $canonicalBrowserUrl"
    Write-Host "Node.js version: $($node.NodeVersion)"
    Write-Host "npm version: $($node.NpmVersion)"
    Write-Host "Node source: $($node.Source)"
    Write-Host "Post-launch reachability probe: Invoke-WebRequest -UseBasicParsing -Uri `"$canonicalBrowserUrl`" -TimeoutSec 10"
    Write-Host "If the printed URL and browser reachability disagree, inspect Get-NetTCPConnection -State Listen -LocalPort $Port and [System.Net.Dns]::GetHostAddresses(`"localhost`")."
    Write-Host "Starting the foreground frontend server. Press Ctrl+C to stop it."

    Push-Location -LiteralPath $frontendRoot
    try {
        Invoke-BlueprintNpm -Node $node -ArgumentList @("run", "dev", "--", "--hostname", $bindAddress, "--port", $Port.ToString())
        if ($LASTEXITCODE -ne 0) {
            throw "The frontend server process exited with nonzero code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
} catch {
    Write-Error $_.Exception.Message
    Write-Host "Frontend launch failed. The existing Streamlit application is unaffected."
    exit 1
}
