$script:BlueprintMinimumNodeVersion = [version]"22.13.0"

function Assert-BlueprintNodeVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$VersionText
    )

    $match = [regex]::Match($VersionText.Trim(), '^v?(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)')
    if (-not $match.Success) {
        throw "Node.js returned an unrecognized version '$VersionText'. Install Node.js $script:BlueprintMinimumNodeVersion or newer."
    }

    $version = [version]("{0}.{1}.{2}" -f $match.Groups['major'].Value, $match.Groups['minor'].Value, $match.Groups['patch'].Value)
    if ($version -lt $script:BlueprintMinimumNodeVersion) {
        throw "Node.js $version is too old. BluePrintReboot requires Node.js $script:BlueprintMinimumNodeVersion or newer. Supply -NodeHome, set BLUEPRINT_NODE_HOME, or update the Node.js installation on PATH."
    }

    return $version
}

function Resolve-BlueprintNode {
    [CmdletBinding()]
    param(
        [string]$NodeHome
    )

    $source = "PATH"
    $candidateHome = $null
    if (-not [string]::IsNullOrWhiteSpace($NodeHome)) {
        $candidateHome = $NodeHome
        $source = "-NodeHome"
    } elseif (-not [string]::IsNullOrWhiteSpace($env:BLUEPRINT_NODE_HOME)) {
        $candidateHome = $env:BLUEPRINT_NODE_HOME
        $source = "BLUEPRINT_NODE_HOME"
    }

    if ($candidateHome) {
        if (-not (Test-Path -LiteralPath $candidateHome -PathType Container)) {
            throw "Node home from $source does not exist or is not a directory: $candidateHome. Point it to a portable Node directory containing node.exe and npm.cmd."
        }
        $resolvedHome = (Resolve-Path -LiteralPath $candidateHome).Path
        $nodePath = Join-Path $resolvedHome "node.exe"
        $npmPath = Join-Path $resolvedHome "npm.cmd"
    } else {
        $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
        $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $nodeCommand -or -not $npmCommand) {
            throw "Node.js and npm were not found on PATH. Supply -NodeHome <portable-node-directory>, set BLUEPRINT_NODE_HOME, or add Node.js $script:BlueprintMinimumNodeVersion or newer to PATH for this session."
        }
        $nodePath = $nodeCommand.Source
        $npmPath = $npmCommand.Source
    }

    if (-not (Test-Path -LiteralPath $nodePath -PathType Leaf)) {
        throw "node.exe was not found for $source at $nodePath. Point NodeHome to a directory containing both node.exe and npm.cmd."
    }
    if (-not (Test-Path -LiteralPath $npmPath -PathType Leaf)) {
        throw "npm.cmd was not found for $source at $npmPath. Point NodeHome to a directory containing both node.exe and npm.cmd."
    }

    $nodePath = (Resolve-Path -LiteralPath $nodePath).Path
    $npmPath = (Resolve-Path -LiteralPath $npmPath).Path

    $nodeVersionText = (& $nodePath --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "node.exe from $source could not run. Verify the portable Node directory and try again."
    }
    $nodeVersion = Assert-BlueprintNodeVersion -VersionText $nodeVersionText

    $npmVersion = (& $npmPath --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($npmVersion)) {
        throw "npm.cmd from $source could not run. Verify that the Node distribution is complete and try again."
    }

    return [pscustomobject]@{
        NodePath = $nodePath
        NpmPath = $npmPath
        NodeVersion = $nodeVersion.ToString()
        NpmVersion = $npmVersion
        Source = $source
    }
}

function Invoke-BlueprintNpm {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Node,
        [string[]]$ArgumentList
    )

    $previousPath = $env:PATH
    $nodeDirectory = Split-Path -Parent $Node.NodePath
    try {
        $env:PATH = "$nodeDirectory$([IO.Path]::PathSeparator)$previousPath"
        & $Node.NpmPath @ArgumentList
        $npmExitCode = $LASTEXITCODE
    } finally {
        $env:PATH = $previousPath
    }
    $global:LASTEXITCODE = $npmExitCode
}
