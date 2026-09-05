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
    [int[]]$RetryDelaysSeconds = @(5, 15, 30)
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

function New-DirectHttpClient {
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(90)
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
    Invoke-WithLimitedRetry -Label "Archive download" -Action {
        if (Test-Path -LiteralPath $zipPath) {
            Remove-Item -LiteralPath $zipPath -Force
        }
        $apiClient = New-DirectHttpClient
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
            $apiResponse = $apiClient.SendAsync($apiRequest).GetAwaiter().GetResult()
            try {
                $status = [int]$apiResponse.StatusCode
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
            }
            finally {
                $apiResponse.Dispose()
                $apiRequest.Dispose()
            }
        }
        finally {
            $apiClient.Dispose()
        }

        $archiveClient = New-DirectHttpClient
        try {
            $archiveResponse = $archiveClient.GetAsync(
                $archiveUri,
                [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
            ).GetAwaiter().GetResult()
            try {
                if (-not $archiveResponse.IsSuccessStatusCode) {
                    throw "Archive host returned HTTP $([int]$archiveResponse.StatusCode)"
                }
                $inputStream = $archiveResponse.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
                try {
                    $outputStream = [IO.File]::Create($zipPath)
                    try {
                        $inputStream.CopyTo($outputStream)
                    }
                    finally {
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
        }
        if (-not (Test-Path -LiteralPath $zipPath)) {
            throw "Archive file was not created"
        }
        if ((Get-Item -LiteralPath $zipPath).Length -le 0) {
            throw "Archive file is empty"
        }
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
