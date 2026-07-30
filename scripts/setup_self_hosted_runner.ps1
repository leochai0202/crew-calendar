[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^https://github\.com/[^/]+/[^/]+/?$")]
    [string]$RepositoryUrl,

    [string]$RegistrationToken = "",

    [string]$RunnerRoot = "C:\actions-runner\crew-calendar",

    [string]$DataRoot = "C:\crew-calendar-data",

    [string]$RunnerName = "$env:COMPUTERNAME-crew-calendar"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )) {
        throw "Run this script from an elevated PowerShell window."
    }
}

function ConvertFrom-SecureValue {
    param([Security.SecureString]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing $Name. $InstallHint"
    }
}

Assert-Administrator
Assert-Command -Name "python" -InstallHint "Install Python 3.11 and retry."
Assert-Command -Name "pwsh" -InstallHint "Install PowerShell 7 and retry."

$edgeCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
if (-not ($edgeCandidates | Where-Object { Test-Path -LiteralPath $_ })) {
    throw "Microsoft Edge Stable was not found."
}

$repositoryRoot = (Resolve-Path -LiteralPath (
    Join-Path $PSScriptRoot ".."
)).Path
$requirements = Join-Path $repositoryRoot "requirements.txt"
if (-not (Test-Path -LiteralPath $requirements)) {
    throw "requirements.txt was not found."
}

$profileDir = Join-Path $DataRoot "browser-profile"
$backupDir = Join-Path $DataRoot "auth-backup"
$diagnosticDir = Join-Path $DataRoot "diagnostics"
foreach ($directory in @(
    $RunnerRoot,
    $profileDir,
    $backupDir,
    $diagnosticDir
)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

# Grant the runner service access only to its dedicated data directory.
& icacls.exe $DataRoot /grant "*S-1-5-20:(OI)(CI)M" /T /C |
    Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to grant the runner service access to the data directory."
}

python -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed."
}

python -c (
    "from playwright.sync_api import sync_playwright; " +
    "p=sync_playwright().start(); " +
    "b=p.chromium.launch(headless=True, channel='msedge'); " +
    "b.close(); p.stop()"
)
if ($LASTEXITCODE -ne 0) {
    throw "Playwright could not start Microsoft Edge."
}

$configCommand = Join-Path $RunnerRoot "config.cmd"
if (-not (Test-Path -LiteralPath $configCommand)) {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/actions/runner/releases/latest" `
        -Headers @{ "User-Agent" = "crew-calendar-runner-setup" }
    $asset = $release.assets |
        Where-Object { $_.name -like "actions-runner-win-x64-*.zip" } |
        Select-Object -First 1
    if ($null -eq $asset) {
        throw "The Windows X64 Actions Runner package was not found."
    }

    $archive = Join-Path $env:TEMP $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $RunnerRoot -Force
    Remove-Item -LiteralPath $archive -Force
}

if (-not (Test-Path -LiteralPath (Join-Path $RunnerRoot ".runner"))) {
    if (-not $RegistrationToken) {
        $secureToken = Read-Host `
            "Enter the one-time GitHub runner registration token" `
            -AsSecureString
        $RegistrationToken = ConvertFrom-SecureValue $secureToken
        $secureToken = $null
    }
    if (-not $RegistrationToken) {
        throw "The runner registration token cannot be empty."
    }

    Push-Location -LiteralPath $RunnerRoot
    try {
        & .\config.cmd `
            --unattended `
            --url $RepositoryUrl `
            --token $RegistrationToken `
            --name $RunnerName `
            --labels "crew-calendar" `
            --work "_work" `
            --replace
        if ($LASTEXITCODE -ne 0) {
            throw "Runner registration failed."
        }
    }
    finally {
        Pop-Location
        $RegistrationToken = $null
    }
}

Push-Location -LiteralPath $RunnerRoot
try {
    & .\svc.cmd install
    if ($LASTEXITCODE -ne 0) {
        throw "Runner service installation failed."
    }
    & .\svc.cmd start
    if ($LASTEXITCODE -ne 0) {
        throw "Runner service startup failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Windows self-hosted runner installed and started."
Write-Host "Dedicated browser profile: $profileDir"
Write-Host "Confirm that the runner is Idle in GitHub Actions > Runners."
