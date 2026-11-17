param(
    [Parameter(Mandatory = $true)]
    [string]$Repository,
    [Parameter(Mandatory = $true)]
    [string]$TargetSha,
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [Parameter(Mandatory = $true)]
    [string]$RunnerTemp,
    [string]$ApiBase = "https://api.github.com",
    [string]$AllowedArchiveHost = "codeload.github.com",
    [int]$MaxAttempts = 3,
    [int[]]$RetryDelaysSeconds = @(5, 15),
    [ValidateRange(1, 90)]
    [int]$RequestTimeoutSeconds = 90,
    [ValidateRange(1, 240)]
    [int]$ArchiveTimeoutSeconds = 240
)

$ErrorActionPreference = "Stop"

if ($TargetSha -notmatch "^[0-9a-fA-F]{40}$") {
    throw "TargetSha must be a full 40-character Git commit SHA"
}
if ([string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
    throw "GITHUB_TOKEN is required"
}
if ($MaxAttempts -lt 1 -or $MaxAttempts -gt 3) {
    throw "MaxAttempts must be between 1 and 3"
}
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') {
    throw "Invalid repository identity"
}
$apiBaseUri = [Uri]$ApiBase
$localTestEndpoint = $apiBaseUri.IsLoopback -and $apiBaseUri.Scheme -eq 'http'
if (-not $localTestEndpoint -and (
    $apiBaseUri.Scheme -ne 'https' -or $apiBaseUri.Host -ne 'api.github.com' -or
    -not $apiBaseUri.IsDefaultPort -or $apiBaseUri.UserInfo -or
    $apiBaseUri.AbsolutePath -ne '/' -or $apiBaseUri.Query -or $apiBaseUri.Fragment -or
    $AllowedArchiveHost -ne 'codeload.github.com'
)) { throw "Untrusted GitHub API/archive endpoint" }
$script:archiveDirectRetry = $false
$script:downloadStage = 'API_REDIRECT'
$script:downloadBytes = 0L

function Assert-RepositoryArchive {
    # Python is already required by both consuming production workflows.
    # stdlib validation drains every entry (CRC included) before replacement.
    $validator = @'
import sys, zipfile
from pathlib import PurePosixPath
path, repo, sha = sys.argv[1:]
with zipfile.ZipFile(path) as archive:
    entries = archive.infolist()
    assert entries
    roots = set()
    for item in entries:
        p = PurePosixPath(item.filename)
        assert not p.is_absolute() and '..' not in p.parts and '\\' not in item.filename
        assert ':' not in item.filename and '.git' not in p.parts
        assert (item.external_attr >> 16) & 0o170000 != 0o120000
        roots.add(p.parts[0])
    assert roots == {repo.replace('/', '-') + '-' + sha[:7]}
    assert archive.testzip() is None
'@
    $validation = & python -B -c $validator $zipPath $Repository $TargetSha 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Archive integrity or fixed-SHA identity validation failed" }
}

function New-GitHubHttpClient {
    param([Parameter(Mandatory = $true)][int]$TimeoutSeconds, [switch]$Direct)
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.UseProxy = -not $Direct.IsPresent
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd(
        "crew-calendar-archive-bootstrap"
    )
    return $client
}

function Invoke-WithLimitedRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )
    $lastError = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return & $Action
        }
        catch {
            $lastError = $_
            $cause = $_.Exception
            while ($cause.InnerException) { $cause = $cause.InnerException }
            Write-Host "ARCHIVE_STAGE=$script:downloadStage"
            Write-Host "ARCHIVE_ERROR_TYPE=$($cause.GetType().Name)"
            Write-Host "ARCHIVE_PARTIAL_BYTES=$script:downloadBytes"
            # Only transport failure on the trusted archive host enables the
            # next bounded direct attempt. API requests always inherit proxy.
            if ($script:downloadStage -in @('ARCHIVE_HEADERS', 'ARCHIVE_BODY') -and (
                $cause -is [OperationCanceledException] -or $cause -is [TimeoutException] -or
                $cause -is [IO.IOException] -or $cause -is [System.Net.Http.HttpRequestException] -or
                $cause -is [System.Net.Sockets.SocketException]
            )) { $script:archiveDirectRetry = $true }
            # Close streams in the action's finally blocks, then remove partial
            # bytes before backoff (including the final failed attempt).
            if (Test-Path -LiteralPath $zipPath) {
                Remove-Item -LiteralPath $zipPath -Force
            }
            Write-Host "$Label attempt $attempt/$MaxAttempts failed"
            if ($attempt -lt $MaxAttempts) {
                $delayIndex = [Math]::Min(
                    $attempt - 1,
                    $RetryDelaysSeconds.Count - 1
                )
                $delay = [Math]::Max(0, $RetryDelaysSeconds[$delayIndex])
                if ($delay -gt 0) {
                    Start-Sleep -Seconds $delay
                }
            }
        }
    }
    throw "$Label failed after $MaxAttempts attempts: $($lastError.Exception.GetType().Name)"
}

$workspaceFull = [IO.Path]::GetFullPath($Workspace)
$workspaceRoot = [IO.Path]::GetPathRoot($workspaceFull)
if (
    [string]::IsNullOrWhiteSpace($workspaceFull) -or
    $workspaceFull -eq $workspaceRoot -or
    $workspaceFull.Length -le ($workspaceRoot.Length + 2)
) {
    throw "Unsafe GITHUB_WORKSPACE path"
}
$runnerTempFull = [IO.Path]::GetFullPath($RunnerTemp)
[IO.Directory]::CreateDirectory($runnerTempFull) | Out-Null
$operationRoot = Join-Path $runnerTempFull (
    "crew-calendar-bootstrap-" + [Guid]::NewGuid().ToString("N")
)
$zipPath = Join-Path $operationRoot "repository.zip"
$extractPath = Join-Path $operationRoot "extracted"
[IO.Directory]::CreateDirectory($operationRoot) | Out-Null

$stopwatch = [Diagnostics.Stopwatch]::StartNew()
try {
    Write-Host "ARCHIVE_TIMEOUT_SECONDS=$ArchiveTimeoutSeconds"
    Invoke-WithLimitedRetry -Label "Archive download" -Action {
        $script:downloadStage = 'API_REDIRECT'
        $script:downloadBytes = 0L
        if (Test-Path -LiteralPath $zipPath) {
            Remove-Item -LiteralPath $zipPath -Force
        }
        $apiClient = New-GitHubHttpClient -TimeoutSeconds $RequestTimeoutSeconds
        $apiTimeout = [Threading.CancellationTokenSource]::new(
            [TimeSpan]::FromSeconds($RequestTimeoutSeconds)
        )
        try {
            $archiveApiUri = (
                $ApiBase.TrimEnd("/") + "/repos/" + $Repository +
                "/zipball/" + $TargetSha
            )
            $apiRequest = [System.Net.Http.HttpRequestMessage]::new(
                [System.Net.Http.HttpMethod]::Get,
                $archiveApiUri
            )
            $apiRequest.Headers.Authorization = (
                [System.Net.Http.Headers.AuthenticationHeaderValue]::new(
                    "Bearer",
                    $env:GITHUB_TOKEN
                )
            )
            $apiRequest.Headers.Accept.ParseAdd("application/vnd.github+json")
            $apiRequest.Headers.Add("X-GitHub-Api-Version", "2022-11-28")
            $apiResponse = $apiClient.SendAsync(
                $apiRequest, $apiTimeout.Token
            ).GetAwaiter().GetResult()
            try {
                $status = [int]$apiResponse.StatusCode
                Write-Host "ARCHIVE_API_HTTP_STATUS=$status"
                if ($status -notin @(301, 302, 307, 308)) {
                    throw "Archive API returned HTTP $status instead of a redirect"
                }
                $archiveUri = $apiResponse.Headers.Location
                if ($null -eq $archiveUri) {
                    throw "Archive API redirect did not include Location"
                }
                if (-not $archiveUri.IsAbsoluteUri) {
                    $archiveUri = [Uri]::new([Uri]$archiveApiUri, $archiveUri)
                }
                if ($archiveUri.Host -ine $AllowedArchiveHost) {
                    throw "Archive redirect host was not the approved host"
                }
                if (-not $localTestEndpoint -and (
                    $archiveUri.Scheme -ne 'https' -or -not $archiveUri.IsDefaultPort -or
                    $archiveUri.UserInfo -or $archiveUri.Fragment -or
                    $archiveUri.AbsolutePath -cne "/$Repository/legacy.zip/$TargetSha"
                )) { throw "Archive redirect was not the trusted fixed-SHA HTTPS resource" }
            }
            finally {
                $apiResponse.Dispose()
                $apiRequest.Dispose()
            }
        }
        finally {
            $apiClient.Dispose()
            $apiTimeout.Dispose()
        }

        $archiveClient = New-GitHubHttpClient -TimeoutSeconds $ArchiveTimeoutSeconds -Direct:$script:archiveDirectRetry
        Write-Host ("ARCHIVE_NETWORK_PATH=" + $(if ($script:archiveDirectRetry) { 'DIRECT_RECOVERY' } else { 'ENVIRONMENT_DEFAULT' }))
        $archiveTimeout = [Threading.CancellationTokenSource]::new(
            [TimeSpan]::FromSeconds($ArchiveTimeoutSeconds)
        )
        try {
            $script:downloadStage = 'ARCHIVE_HEADERS'
            $archiveResponse = $archiveClient.GetAsync(
                $archiveUri,
                [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead,
                $archiveTimeout.Token
            ).GetAwaiter().GetResult()
            try {
                if (-not $archiveResponse.IsSuccessStatusCode) {
                    $script:downloadStage = 'ARCHIVE_HTTP_STATUS'
                    Write-Host "ARCHIVE_HTTP_STATUS=$([int]$archiveResponse.StatusCode)"
                    throw "Archive host returned HTTP $([int]$archiveResponse.StatusCode)"
                }
                $script:downloadStage = 'ARCHIVE_BODY'
                $expectedBytes = $archiveResponse.Content.Headers.ContentLength
                $inputStream = $archiveResponse.Content.ReadAsStreamAsync(
                    $archiveTimeout.Token
                ).GetAwaiter().GetResult()
                try {
                    $outputStream = [IO.File]::Create($zipPath)
                    try {
                        $inputStream.CopyToAsync(
                            $outputStream, 81920, $archiveTimeout.Token
                        ).GetAwaiter().GetResult()
                    }
                    finally {
                        $script:downloadBytes = $outputStream.Length
                        $outputStream.Dispose()
                    }
                }
                finally {
                    $inputStream.Dispose()
                }
            }
            finally {
                $archiveResponse.Dispose()
            }
        }
        finally {
            $archiveClient.Dispose()
            $archiveTimeout.Dispose()
        }
        if (-not (Test-Path -LiteralPath $zipPath)) {
            throw "Archive file was not created"
        }
        if ((Get-Item -LiteralPath $zipPath).Length -le 0) {
            throw "Archive file is empty"
        }
        $script:downloadStage = 'ARCHIVE_VALIDATE'
        if ($null -ne $expectedBytes -and (Get-Item -LiteralPath $zipPath).Length -ne $expectedBytes) {
            throw "Archive response length mismatch"
        }
        Assert-RepositoryArchive
    } | Out-Null

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        if ($zip.Entries.Count -eq 0) {
            throw "Archive contains no entries"
        }
    }
    finally {
        $zip.Dispose()
    }
    [IO.Directory]::CreateDirectory($extractPath) | Out-Null
    [IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $extractPath)
    $topLevel = @(Get-ChildItem -LiteralPath $extractPath -Force)
    if ($topLevel.Count -ne 1 -or -not $topLevel[0].PSIsContainer) {
        throw "Archive must contain exactly one top-level repository directory"
    }
    $expectedPrefix = ($Repository -replace "/", "-") + "-"
    if (-not $topLevel[0].Name.StartsWith(
        $expectedPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Archive top-level directory did not match the repository"
    }
    $repositoryRoot = $topLevel[0].FullName
    if (Test-Path -LiteralPath (Join-Path $repositoryRoot ".git")) {
        throw "Archive unexpectedly contains a .git directory"
    }

    [IO.Directory]::CreateDirectory($workspaceFull) | Out-Null
    Get-ChildItem -LiteralPath $workspaceFull -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
    Get-ChildItem -LiteralPath $repositoryRoot -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $workspaceFull -Recurse -Force
    }
    $stopwatch.Stop()
    Write-Host "BOOTSTRAP_MAIN_SHA=$TargetSha"
    Write-Host "ARCHIVE_DOWNLOAD=SUCCESS"
    Write-Host ("ARCHIVE_TIME={0:N3}" -f $stopwatch.Elapsed.TotalSeconds)
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_OUTPUT)) {
        "bootstrap_main_sha=$TargetSha" |
            Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
        "archive_time_seconds=$($stopwatch.Elapsed.TotalSeconds)" |
            Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
    }
}
finally {
    if (Test-Path -LiteralPath $operationRoot) {
        Remove-Item -LiteralPath $operationRoot -Recurse -Force
    }
}
