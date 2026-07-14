param(
    [switch]$SmokeOnly,
    [switch]$PythonOnly,
    [string]$NodeHome,
    [switch]$WriteEvidence
)

$ErrorActionPreference = "Stop"

function Write-Phase {
    param([string]$Message)

    Write-Host ""
    Write-Host "== $Message =="
}

function Invoke-ValidationCommand {
    param(
        [pscustomobject]$Phase,
        [string]$Description,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    Write-Phase $Description
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        $Phase.state = "failed"
        throw "$Description failed with exit code $LASTEXITCODE."
    }
    $Phase.state = "passed"
}

function Invoke-ValidationNpmCommand {
    param(
        [pscustomobject]$Phase,
        [string]$Description,
        [pscustomobject]$Node,
        [string[]]$ArgumentList
    )

    Write-Phase $Description
    Invoke-BlueprintNpm -Node $Node -ArgumentList $ArgumentList
    if ($LASTEXITCODE -ne 0) {
        $Phase.state = "failed"
        throw "$Description failed with exit code $LASTEXITCODE."
    }
    $Phase.state = "passed"
}

function Get-GitEvidence {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        return [pscustomobject]@{ sha = $null; dirty = $null }
    }

    $sha = (& $git.Source rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sha)) {
        return [pscustomobject]@{ sha = $null; dirty = $null }
    }
    $status = (& $git.Source status --porcelain=v1 2>$null | Out-String).Trim()
    return [pscustomobject]@{ sha = $sha; dirty = -not [string]::IsNullOrWhiteSpace($status) }
}

function Write-ValidationEvidence {
    param(
        [string]$RepositoryRoot,
        [string]$ValidationScope,
        [string]$OverallState,
        [string]$PythonVersion,
        [AllowNull()][string]$NodeVersion,
        [AllowNull()][string]$NpmVersion,
        [object[]]$Phases
    )

    $git = Get-GitEvidence
    $summary = [ordered]@{
        schema_version = "1.0"
        timestamp_utc = [DateTime]::UtcNow.ToString("o")
        git_commit_sha = $git.sha
        working_tree_dirty = $git.dirty
        python_version = $PythonVersion
        node_version = $NodeVersion
        npm_version = $NpmVersion
        validation_scope = $ValidationScope
        overall_state = $OverallState
        phases = $Phases
    }

    $artifacts = Join-Path $RepositoryRoot "artifacts"
    New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
    $evidencePath = Join-Path $artifacts "validation-summary.json"
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $evidencePath -Encoding UTF8
    Write-Host "Validation evidence written to artifacts/validation-summary.json."
}

$phases = @(
    [pscustomobject][ordered]@{ name = "python_smoke"; command = "python scripts/smoke_check.py"; state = "skipped" },
    [pscustomobject][ordered]@{ name = "python_pytest"; command = "python -m pytest"; state = "skipped" },
    [pscustomobject][ordered]@{ name = "frontend_lint"; command = "npm run lint"; state = "skipped" },
    [pscustomobject][ordered]@{ name = "frontend_test_build"; command = "npm test"; state = "skipped" }
)
$validationScope = if ($SmokeOnly -or $PythonOnly) { "partial" } else { "full" }
$overallState = "failed"
$pythonVersion = $null
$nodeVersion = $null
$npmVersion = $null
$exitCode = 1
$failureMessage = $null

try {
    if ($SmokeOnly -and $PythonOnly) {
        throw "-SmokeOnly and -PythonOnly cannot be combined. Choose the single partial-validation mode you intend to run."
    }
    if (($SmokeOnly -or $PythonOnly) -and -not [string]::IsNullOrWhiteSpace($NodeHome)) {
        throw "-NodeHome is not used by partial validation. Remove -NodeHome or run the default full validation."
    }

    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    Set-Location -LiteralPath $repoRoot

    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Missing .venv. Run .\scripts\dev_setup.ps1 before .\scripts\dev_check.ps1."
    }
    $pythonVersion = (& $venvPython --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "The repository Python environment could not report its version. Re-run .\scripts\dev_setup.ps1."
    }

    $smokeCheckRelativePath = "scripts/smoke_check.py"
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $smokeCheckRelativePath) -PathType Leaf)) {
        $phases[0].state = "failed"
        throw "$smokeCheckRelativePath was not found; smoke validation cannot run."
    }
    Invoke-ValidationCommand -Phase $phases[0] -Description "Run smoke check" -FilePath $venvPython -ArgumentList @($smokeCheckRelativePath)

    if ($SmokeOnly) {
        $overallState = "passed"
        $exitCode = 0
        Write-Host ""
        Write-Host "PARTIAL VALIDATION: smoke check passed. Pytest and all frontend checks were skipped. This result is not release-qualified." -ForegroundColor Yellow
    } else {
        Invoke-ValidationCommand -Phase $phases[1] -Description "Run full pytest" -FilePath $venvPython -ArgumentList @("-m", "pytest")

        if ($PythonOnly) {
            $overallState = "passed"
            $exitCode = 0
            Write-Host ""
            Write-Host "PARTIAL VALIDATION: Python smoke and pytest passed; frontend lint and test/build were deliberately skipped. This result is not release-qualified." -ForegroundColor Yellow
        } else {
            . (Join-Path $PSScriptRoot "resolve_node.ps1")
            try {
                $node = Resolve-BlueprintNode -NodeHome $NodeHome
            } catch {
                $phases[2].state = "failed"
                throw
            }
            $nodeVersion = $node.NodeVersion
            $npmVersion = $node.NpmVersion
            Write-Phase "Resolve frontend runtime"
            Write-Host "Node.js $nodeVersion via $($node.Source); npm $npmVersion."

            $frontendRoot = Join-Path $repoRoot "frontend"
            foreach ($requiredFile in @("package.json", "package-lock.json")) {
                if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot $requiredFile) -PathType Leaf)) {
                    $phases[2].state = "failed"
                    throw "frontend/$requiredFile is missing; full validation cannot run."
                }
            }
            if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules") -PathType Container)) {
                $phases[2].state = "failed"
                throw "Frontend dependencies are missing. Run .\scripts\frontend_setup.ps1 -NodeHome <portable-node-directory>, then rerun full validation."
            }

            Push-Location -LiteralPath $frontendRoot
            try {
                Invoke-ValidationNpmCommand -Phase $phases[2] -Description "Run frontend lint" -Node $node -ArgumentList @("run", "lint")
                Invoke-ValidationNpmCommand -Phase $phases[3] -Description "Run frontend build and rendered/bridge tests" -Node $node -ArgumentList @("test")
            } finally {
                Pop-Location
            }

            $overallState = "passed"
            $exitCode = 0
            Write-Host ""
            Write-Host "FULL VALIDATION PASSED: Python smoke, full pytest, frontend lint, and frontend test/build all passed." -ForegroundColor Green
        }
    }
} catch {
    $failureMessage = $_.Exception.Message
    $overallState = "failed"
    $exitCode = 1
}

if ($WriteEvidence) {
    try {
        if (-not $repoRoot) {
            $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
        }
        Write-ValidationEvidence -RepositoryRoot $repoRoot -ValidationScope $validationScope -OverallState $overallState -PythonVersion $pythonVersion -NodeVersion $nodeVersion -NpmVersion $npmVersion -Phases $phases
    } catch {
        $failureMessage = "Validation evidence could not be written safely: $($_.Exception.Message)"
        $exitCode = 1
    }
}

if ($exitCode -ne 0) {
    Write-Error $failureMessage -ErrorAction Continue
}
exit $exitCode
