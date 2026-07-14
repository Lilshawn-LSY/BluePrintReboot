param(
    [switch]$IncludeFrontend,
    [string]$NodeHome
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

function Resolve-PythonCommand {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return [pscustomobject]@{
            File = $pyLauncher.Source
            Args = @("-3")
            Label = "py -3"
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{
            File = $python.Source
            Args = @()
            Label = "python"
        }
    }

    throw "Python was not found. Install Python 3, then reopen PowerShell and run .\scripts\dev_setup.ps1 again."
}

try {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    Set-Location $repoRoot

    $venvDir = Join-Path $repoRoot ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $requirementsPath = Join-Path $repoRoot "requirements.txt"

    if (-not (Test-Path $requirementsPath -PathType Leaf)) {
        throw "requirements.txt was not found at $requirementsPath."
    }

    Write-Phase "Resolve repository"
    Write-Host "Repository root: $repoRoot"

    $pythonCommand = Resolve-PythonCommand
    Write-Host "Using Python command: $($pythonCommand.Label)"

    if (-not (Test-Path $venvPython -PathType Leaf)) {
        $venvArgs = @()
        $venvArgs += $pythonCommand.Args
        $venvArgs += @("-m", "venv", $venvDir)
        Invoke-CheckedCommand -Description "Create .venv" -FilePath $pythonCommand.File -ArgumentList $venvArgs
    } else {
        Write-Phase "Create .venv"
        Write-Host ".venv already exists; leaving it in place."
    }

    if (-not (Test-Path $venvPython -PathType Leaf)) {
        throw "Virtual environment Python was not created at $venvPython."
    }

    Invoke-CheckedCommand -Description "Upgrade pip" -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-CheckedCommand -Description "Install requirements.txt" -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "-r", $requirementsPath)
    Invoke-CheckedCommand -Description "Verify expected imports" -FilePath $venvPython -ArgumentList @("-c", "import streamlit, pytest; print('Verified imports: streamlit, pytest')")

    if ($IncludeFrontend) {
        Write-Phase "Set up frontend dependencies"
        $frontendSetup = Join-Path $PSScriptRoot "frontend_setup.ps1"
        $frontendArguments = @{}
        if (-not [string]::IsNullOrWhiteSpace($NodeHome)) {
            $frontendArguments["NodeHome"] = $NodeHome
        }
        & $frontendSetup @frontendArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend setup failed with exit code $LASTEXITCODE."
        }
    } elseif (-not [string]::IsNullOrWhiteSpace($NodeHome)) {
        throw "-NodeHome is used with -IncludeFrontend. Run .\scripts\dev_setup.ps1 -IncludeFrontend -NodeHome <portable-node-directory>."
    }

    Write-Host ""
    Write-Host "BluePrintReboot setup complete."
    if ($IncludeFrontend) {
        Write-Host "Next: .\scripts\dev_check.ps1 -NodeHome <portable-node-directory>"
    } else {
        Write-Host "Python setup is complete. For the full release gate, also run .\scripts\frontend_setup.ps1 and then .\scripts\dev_check.ps1."
    }
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
