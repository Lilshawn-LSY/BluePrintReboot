param(
    [string]$NodeHome
)

$ErrorActionPreference = "Stop"

try {
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $frontendRoot = Join-Path $repoRoot "frontend"
    $packageJson = Join-Path $frontendRoot "package.json"
    $packageLock = Join-Path $frontendRoot "package-lock.json"

    if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
        throw "Frontend package.json was not found at frontend/package.json."
    }
    if (-not (Test-Path -LiteralPath $packageLock -PathType Leaf)) {
        throw "Frontend package-lock.json was not found. Deterministic npm ci setup cannot continue."
    }

    . (Join-Path $PSScriptRoot "resolve_node.ps1")
    $node = Resolve-BlueprintNode -NodeHome $NodeHome

    Write-Host "Resolved Node.js $($node.NodeVersion) via $($node.Source)."
    Write-Host "Resolved npm $($node.NpmVersion)."
    Write-Host "Installing frontend dependencies from package-lock.json with npm ci..."

    Push-Location -LiteralPath $frontendRoot
    try {
        Invoke-BlueprintNpm -Node $node -ArgumentList @("ci")
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed with exit code $LASTEXITCODE. The frontend dependency setup is incomplete."
        }
    } finally {
        Pop-Location
    }

    Write-Host "Frontend dependency setup complete."
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
