param(
    [string]$RunRoot = $env:TRAINING_RUN_ROOT,
    [string]$RunnerTemp = $env:RUNNER_TEMP,
    [string]$RunId = $env:GITHUB_RUN_ID,
    [switch]$InspectOnly
)

$script:CleanupImplementationPath = $PSCommandPath
$script:CleanupCodes = @(
    'CLEANUP_PATH_INVALID', 'CLEANUP_ROOT_NAME_INVALID',
    'CLEANUP_REPARSE_POINT_REFUSED', 'CLEANUP_OWNER_MISSING', 'CLEANUP_OWNER_INVALID',
    'CLEANUP_ACCESS_DENIED', 'CLEANUP_FILE_IN_USE', 'CLEANUP_IO_ERROR',
    'CLEANUP_UNEXPECTED_ERROR', 'CLEANUP_SCRIPT_INSIDE_ROOT',
    'CLEANUP_TEST_PROCESS_ACTIVE', 'CLEANUP_PROCESS_CHECK_UNAVAILABLE'
)

function Get-TrainingCleanupPlan {
    param([string]$Root, [string]$TempBase, [string]$Id)
    if ($Id -notmatch '^[0-9]+$' -or [string]::IsNullOrWhiteSpace($Root) -or
        [string]::IsNullOrWhiteSpace($TempBase)) { throw 'CLEANUP_PATH_INVALID' }
    $tempPath = [IO.Path]::GetFullPath($TempBase).TrimEnd('\')
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ((Split-Path -Parent $rootPath) -ne $tempPath) { throw 'CLEANUP_PATH_INVALID' }
    $namePattern = '^training-login-' + [Regex]::Escape($Id) + '-[0-9a-f]{32}$'
    if ((Split-Path -Leaf $rootPath) -notmatch $namePattern) { throw 'CLEANUP_ROOT_NAME_INVALID' }

    # Reject aliases in ancestors too. Never follow a junction to another tree.
    $ancestor = Get-Item -LiteralPath $tempPath -Force -ErrorAction Stop
    while ($null -ne $ancestor) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'CLEANUP_REPARSE_POINT_REFUSED'
        }
        $ancestor = $ancestor.Parent
    }
    if (-not (Test-Path -LiteralPath $rootPath)) {
        return @{ Root=$rootPath; Temp=$tempPath; Exists=$false; Entries=0 }
    }
    $rootItem = Get-Item -LiteralPath $rootPath -Force -ErrorAction Stop
    if (-not $rootItem.PSIsContainer) { throw 'CLEANUP_PATH_INVALID' }
    if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'CLEANUP_REPARSE_POINT_REFUSED'
    }
    $pending = [Collections.Generic.Stack[string]]::new()
    $files = [Collections.Generic.List[string]]::new()
    $pending.Push($rootPath)
    $entryCount = 0
    while ($pending.Count -gt 0) {
        # One level at a time: detect a reparse point before descending into it.
        foreach ($item in @(Get-ChildItem -LiteralPath $pending.Pop() -Force -ErrorAction Stop)) {
            $entryCount++
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'CLEANUP_REPARSE_POINT_REFUSED'
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
            else { $files.Add($item.FullName) }
        }
    }
    $ownerPath = Join-Path $rootPath '.training-run-owner.json'
    if (-not (Test-Path -LiteralPath $ownerPath -PathType Leaf)) { throw 'CLEANUP_OWNER_MISSING' }
    if ((Get-Item -LiteralPath $ownerPath -Force).Length -gt 4096) { throw 'CLEANUP_OWNER_INVALID' }
    try { $owner = [IO.File]::ReadAllText($ownerPath) | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'CLEANUP_OWNER_INVALID' }
    if ($owner.kind -ne 'training-login-test-v1' -or $owner.run_id -ne $Id -or
        $owner.root_name -ne (Split-Path -Leaf $rootPath)) { throw 'CLEANUP_OWNER_INVALID' }
    return @{ Root=$rootPath; Temp=$tempPath; Exists=$true; Entries=$entryCount; Files=$files }
}

function Assert-TrainingBrowserClosed {
    param([string]$Root)
    # No process termination. Match only this validated run's unique directory
    # name; never print command lines or inspect any browser profile contents.
    $name = Split-Path -Leaf $Root
    try {
        $processes = @(Get-CimInstance Win32_Process -Filter ("CommandLine LIKE '%" + $name + "%'") -ErrorAction Stop)
    }
    catch { throw 'CLEANUP_PROCESS_CHECK_UNAVAILABLE' }
    if (@($processes | Where-Object { $_.ProcessId -ne $PID }).Count -gt 0) {
        throw 'CLEANUP_TEST_PROCESS_ACTIVE'
    }
}

function Assert-TrainingFilesUnlocked {
    param($Paths)
    # Check every remaining file before deleting anything. Open for read only;
    # do not read bytes, change ACLs, or try to break an existing file handle.
    foreach ($path in $Paths) {
        $handle = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
        $handle.Dispose()
    }
}

function Get-TrainingCleanupFailure {
    param([Management.Automation.ErrorRecord]$Record)
    $errorObject = $Record.Exception.GetBaseException()
    $nativeCode = $errorObject.HResult -band 0xffff
    $reason = if ($Record.Exception.Message -in $script:CleanupCodes) {
        $Record.Exception.Message
    } elseif ($nativeCode -in @(32, 33)) {
        'CLEANUP_FILE_IN_USE'
    } elseif ($nativeCode -eq 5 -or $errorObject -is [UnauthorizedAccessException]) {
        'CLEANUP_ACCESS_DENIED'
    } elseif ($errorObject -is [IO.IOException]) {
        'CLEANUP_IO_ERROR'
    } else { 'CLEANUP_UNEXPECTED_ERROR' }
    return @{ Reason=$reason; NativeCode=$nativeCode }
}

function Invoke-TrainingCleanup {
    param([string]$Root, [string]$TempBase, [string]$Id, [switch]$Inspect)
    $ErrorActionPreference = 'Stop'
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            # Recheck all boundaries and reparse points before every attempt.
            $plan = Get-TrainingCleanupPlan -Root $Root -TempBase $TempBase -Id $Id
            if (-not $plan.Exists) {
                return @{ Status='ABSENT'; Reason='NONE'; NativeCode=0; Attempts=$attempt }
            }
            if ($Inspect) {
                return @{ Status='INSPECTED'; Reason='NONE'; NativeCode=0; Attempts=$attempt }
            }
            $implementation = [IO.Path]::GetFullPath($script:CleanupImplementationPath)
            if ($implementation.StartsWith($plan.Root + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw 'CLEANUP_SCRIPT_INSIDE_ROOT'
            }
            $current = [IO.Path]::GetFullPath((Get-Location).ProviderPath).TrimEnd('\')
            $nativeCurrent = [IO.Path]::GetFullPath([Environment]::CurrentDirectory).TrimEnd('\')
            if ($current -eq $plan.Root -or $current.StartsWith($plan.Root + '\', [StringComparison]::OrdinalIgnoreCase) -or
                $nativeCurrent -eq $plan.Root -or $nativeCurrent.StartsWith($plan.Root + '\', [StringComparison]::OrdinalIgnoreCase)) {
                Set-Location -LiteralPath $plan.Temp
                [Environment]::CurrentDirectory = $plan.Temp
            }
            Assert-TrainingBrowserClosed -Root $plan.Root
            Assert-TrainingFilesUnlocked -Paths $plan.Files
            # Keep the owner marker until children are gone, so a lock failure
            # cannot turn a subsequent safe retry into an unowned-directory deletion.
            foreach ($item in @(Get-ChildItem -LiteralPath $plan.Root -Force)) {
                if ($item.Name -ne '.training-run-owner.json') {
                    Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop
                }
            }
            Remove-Item -LiteralPath $plan.Root -Recurse -Force -ErrorAction Stop
            return @{ Status='COMPLETE'; Reason='NONE'; NativeCode=0; Attempts=$attempt }
        }
        catch {
            $failure = Get-TrainingCleanupFailure $_
            if (-not $Inspect -and $attempt -lt 3 -and
                $failure.Reason -in @('CLEANUP_FILE_IN_USE', 'CLEANUP_ACCESS_DENIED')) {
                Start-Sleep -Seconds $attempt
                continue
            }
            return @{ Status='FAILED_REQUIRES_LOCAL_REVIEW'; Reason=$failure.Reason;
                      NativeCode=$failure.NativeCode; Attempts=$attempt }
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $result = Invoke-TrainingCleanup -Root $RunRoot -TempBase $RunnerTemp -Id $RunId -Inspect:$InspectOnly
    Write-Output ('TRAINING_TEMP_CLEANUP=' + $result.Status)
    Write-Output ('TRAINING_TEMP_CLEANUP_REASON=' + $result.Reason)
    Write-Output ('TRAINING_TEMP_CLEANUP_NATIVE_CODE=' + $result.NativeCode)
    Write-Output ('TRAINING_TEMP_CLEANUP_ATTEMPTS=' + $result.Attempts)
    if ($result.Status -eq 'FAILED_REQUIRES_LOCAL_REVIEW') { exit 2 }
    exit 0
}
