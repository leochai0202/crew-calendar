# Only synthetic fixtures under this test module; no browser or production paths.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'cleanup_training.ps1')
$fixtureBase = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ('.runtime/cleanup-tests/' + [Guid]::NewGuid().ToString('N'))))
New-Item -ItemType Directory -Path $fixtureBase -Force | Out-Null
$originalLocation = (Get-Location).ProviderPath
$originalNativeLocation = [Environment]::CurrentDirectory
$testsPassed = 0
$fixtureProcessState = @{ Processes=@(); Fail=$false }

# Offline process inventory: never enumerate actual browser command lines.
function Get-CimInstance {
    [CmdletBinding()]
    param([string]$ClassName, [string]$Filter)
    if ($fixtureProcessState.Fail) { throw 'synthetic process inventory failure' }
    return $fixtureProcessState.Processes
}

function Assert-Check([bool]$Condition, [string]$Code) {
    if (-not $Condition) { throw ('OFFLINE_CLEANUP_ASSERTION_' + $Code) }
}

function New-Fixture([bool]$WithOwner = $true) {
    $name = 'training-login-999-' + [Guid]::NewGuid().ToString('N')
    $path = Join-Path $fixtureBase $name
    New-Item -ItemType Directory -Path $path | Out-Null
    if ($WithOwner) {
        $owner = @{kind='training-login-test-v1'; run_id='999'; root_name=$name} | ConvertTo-Json -Compress
        [IO.File]::WriteAllText((Join-Path $path '.training-run-owner.json'), $owner)
    }
    return $path
}

try {
    $valid = New-Fixture
    [IO.File]::WriteAllText((Join-Path $valid 'synthetic.txt'), 'fixture only')
    $result = Invoke-TrainingCleanup -Root $valid -TempBase $fixtureBase -Id '999' -Inspect
    Assert-Check ($result.Status -eq 'INSPECTED' -and (Test-Path -LiteralPath $valid)) 'INSPECT_ONLY'
    $testsPassed++
    $result = Invoke-TrainingCleanup -Root $valid -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Status -eq 'COMPLETE' -and -not (Test-Path -LiteralPath $valid)) 'VALID_DELETE'
    $testsPassed++
    $result = Invoke-TrainingCleanup -Root $valid -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Status -eq 'ABSENT') 'ALREADY_ABSENT'
    $testsPassed++

    $outside = New-Fixture
    $result = Invoke-TrainingCleanup -Root $outside -TempBase (Join-Path $fixtureBase 'different-parent') -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_PATH_INVALID' -and (Test-Path -LiteralPath $outside)) 'OUTSIDE_PARENT'
    $testsPassed++
    $result = Invoke-TrainingCleanup -Root $outside -TempBase $fixtureBase -Id '888'
    Assert-Check ($result.Reason -eq 'CLEANUP_ROOT_NAME_INVALID' -and (Test-Path -LiteralPath $outside)) 'WRONG_RUN_ID'
    $testsPassed++
    $null = Invoke-TrainingCleanup -Root $outside -TempBase $fixtureBase -Id '999'

    $unowned = New-Fixture $false
    $result = Invoke-TrainingCleanup -Root $unowned -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_OWNER_MISSING' -and (Test-Path -LiteralPath $unowned)) 'OWNER_MISSING'
    $testsPassed++
    [IO.File]::WriteAllText((Join-Path $unowned '.training-run-owner.json'), '{}')
    $result = Invoke-TrainingCleanup -Root $unowned -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_OWNER_INVALID') 'OWNER_INVALID'
    $testsPassed++
    $owner = @{kind='training-login-test-v1'; run_id='999'; root_name=(Split-Path -Leaf $unowned)} | ConvertTo-Json -Compress
    [IO.File]::WriteAllText((Join-Path $unowned '.training-run-owner.json'), $owner)
    $null = Invoke-TrainingCleanup -Root $unowned -TempBase $fixtureBase -Id '999'

    $linkedRoot = New-Fixture
    $linkedTarget = New-Fixture
    $sentinel = Join-Path $linkedTarget 'keep.txt'
    [IO.File]::WriteAllText($sentinel, 'synthetic sibling must survive')
    $link = Join-Path $linkedRoot 'junction'
    New-Item -ItemType Junction -Path $link -Target $linkedTarget | Out-Null
    $result = Invoke-TrainingCleanup -Root $linkedRoot -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_REPARSE_POINT_REFUSED' -and (Test-Path -LiteralPath $sentinel)) 'CHILD_JUNCTION'
    $testsPassed++
    # Delete the synthetic link itself, never recursively traverse its target.
    [IO.Directory]::Delete($link)
    $null = Invoke-TrainingCleanup -Root $linkedRoot -TempBase $fixtureBase -Id '999'
    $null = Invoke-TrainingCleanup -Root $linkedTarget -TempBase $fixtureBase -Id '999'

    $alias = Join-Path $fixtureBase 'ancestor-alias'
    $ancestorRoot = New-Fixture
    New-Item -ItemType Junction -Path $alias -Target $fixtureBase | Out-Null
    $aliasedRoot = Join-Path $alias (Split-Path -Leaf $ancestorRoot)
    $result = Invoke-TrainingCleanup -Root $aliasedRoot -TempBase $alias -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_REPARSE_POINT_REFUSED' -and (Test-Path -LiteralPath $ancestorRoot)) 'ANCESTOR_JUNCTION'
    $testsPassed++
    [IO.Directory]::Delete($alias)
    $null = Invoke-TrainingCleanup -Root $ancestorRoot -TempBase $fixtureBase -Id '999'

    $lockedRoot = New-Fixture
    $unlockedSentinel = Join-Path $lockedRoot 'a-preserved.txt'
    [IO.File]::WriteAllText($unlockedSentinel, 'must not partially delete before lock check')
    $lockedFile = Join-Path $lockedRoot 'locked-synthetic.txt'
    $handle = [IO.File]::Open($lockedFile, [IO.FileMode]::Create, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $result = Invoke-TrainingCleanup -Root $lockedRoot -TempBase $fixtureBase -Id '999'
        Assert-Check ($result.Status -eq 'FAILED_REQUIRES_LOCAL_REVIEW' -and
                      $result.Reason -in @('CLEANUP_FILE_IN_USE','CLEANUP_ACCESS_DENIED') -and
                      $result.Attempts -eq 3 -and
                      (Test-Path -LiteralPath $unlockedSentinel) -and
                      (Test-Path -LiteralPath (Join-Path $lockedRoot '.training-run-owner.json'))) 'LOCKED_FILE_BOUNDED_RETRIES'
        $testsPassed++
    }
    finally { $handle.Dispose() }
    $result = Invoke-TrainingCleanup -Root $lockedRoot -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Status -eq 'COMPLETE') 'LOCK_RELEASED'
    $testsPassed++

    $cwdRoot = New-Fixture
    Set-Location -LiteralPath $cwdRoot
    [Environment]::CurrentDirectory = $cwdRoot
    $result = Invoke-TrainingCleanup -Root $cwdRoot -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Status -eq 'COMPLETE' -and (Get-Location).ProviderPath -eq $fixtureBase -and
                  [Environment]::CurrentDirectory -eq $fixtureBase) 'WORKING_DIRECTORY_INSIDE_ROOT'
    $testsPassed++

    $selfRoot = New-Fixture
    $selfScript = Join-Path $selfRoot 'cleanup_training.ps1'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'cleanup_training.ps1') -Destination $selfScript
    $selfOutput = @(& $selfScript -RunRoot $selfRoot -RunnerTemp $fixtureBase -RunId '999')
    Assert-Check ($LASTEXITCODE -eq 2 -and $selfOutput -contains 'TRAINING_TEMP_CLEANUP_REASON=CLEANUP_SCRIPT_INSIDE_ROOT' -and
                  (Test-Path -LiteralPath $selfScript)) 'SCRIPT_INSIDE_TARGET_REFUSED'
    $testsPassed++
    $externalScript = Join-Path $fixtureBase ((Split-Path -Leaf $selfRoot) + '-cleanup.ps1')
    Copy-Item -LiteralPath $selfScript -Destination $externalScript
    $externalOutput = @(& $externalScript -RunRoot $selfRoot -RunnerTemp $fixtureBase -RunId '999')
    if ($LASTEXITCODE -ne 0) { $externalOutput | Write-Output }
    Assert-Check ($LASTEXITCODE -eq 0 -and $externalOutput -contains 'TRAINING_TEMP_CLEANUP=COMPLETE' -and
                  -not (Test-Path -LiteralPath $selfRoot) -and (Test-Path -LiteralPath $externalScript)) 'EXTERNAL_SCRIPT_CLEANUP'
    Remove-Item -LiteralPath $externalScript
    $testsPassed++

    $activeRoot = New-Fixture
    $fixtureProcessState.Processes = @([pscustomobject]@{ProcessId=($PID + 1)})
    $result = Invoke-TrainingCleanup -Root $activeRoot -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_TEST_PROCESS_ACTIVE' -and $result.Attempts -eq 1 -and
                  (Test-Path -LiteralPath (Join-Path $activeRoot '.training-run-owner.json'))) 'ACTIVE_PROCESS_REFUSED'
    $testsPassed++
    $fixtureProcessState.Processes = @()
    $fixtureProcessState.Fail = $true
    $result = Invoke-TrainingCleanup -Root $activeRoot -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Reason -eq 'CLEANUP_PROCESS_CHECK_UNAVAILABLE' -and
                  (Test-Path -LiteralPath $activeRoot)) 'UNKNOWN_PROCESS_STATE_REFUSED'
    $testsPassed++
    $fixtureProcessState.Fail = $false
    $fixtureProcessState.Processes = @([pscustomobject]@{ProcessId=$PID})
    $result = Invoke-TrainingCleanup -Root $activeRoot -TempBase $fixtureBase -Id '999'
    Assert-Check ($result.Status -eq 'COMPLETE') 'OWN_CLEANUP_PROCESS_ALLOWED'
    $fixtureProcessState.Processes = @()
    $testsPassed++
}
finally {
    Set-Location -LiteralPath $originalLocation
    [Environment]::CurrentDirectory = $originalNativeLocation
}

# Nonrecursive deletion of this now-empty synthetic parent only.
[IO.Directory]::Delete($fixtureBase)
Write-Output ('OFFLINE_CLEANUP_TESTS=PASS COUNT=' + $testsPassed)
exit 0
