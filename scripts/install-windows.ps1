<#
.SYNOPSIS
Install or update closed-review for native Windows Hermes and Hermes Desktop.

.DESCRIPTION
Installs or updates the creview runner with uv, then installs or updates the managed
journal-article-review skill in the active Hermes profile, then runs `creview hermes doctor`.
Use the same command to install and to update.

The first run installs from -Source, or from the public GitHub repository if -Source is not given.
Later runs without -Source upgrade from the source that uv recorded. If the runner was installed
from a local folder (the old download-and-copy method), the script switches it to the Git source
so that updates fetch new commits.

.PARAMETER Source
Any source that `uv tool install` accepts: a git+ssh:// or git+https:// URL, or a local folder.

.PARAMETER GatewayUrl
The trusted model gateway's OpenAI-compatible base URL, for example http://192.168.1.20:8000/v1.
Stored with `creview config gateway`. Optional: when no gateway is stored, the script runs
`creview config detect --apply`, which adopts the Hermes profile's local or private model server.

.PARAMETER Model
The review model's name on that gateway. Required together with -GatewayUrl.

.PARAMETER TrustedModel
Other models on the same gateway that Hermes routes may use, such as a larger planning model.

.PARAMETER HermesProfile
The Hermes profile to install the skill into. Defaults to the profile creview resolves:
HERMES_SESSION_PROFILE, otherwise "default" under HERMES_HOME or %LOCALAPPDATA%\hermes.

.PARAMETER ReplaceUnmanaged
Move a hand-copied skill folder to a backup without asking first.

.PARAMETER NoGitPull
Do not update the Git checkout this script runs from. By default, run from a Git clone, the script
first fast-forwards that clone (setting local edits aside with `git stash` and restoring them), so
the script and skill files match what it installs.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 -GatewayUrl http://192.168.1.20:8000/v1 -Model qwen3-32b

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 -Source C:\path\to\closed-review
#>
[CmdletBinding()]
param(
    [string]$Source,
    [string]$GatewayUrl,
    [string]$Model,
    [string[]]$TrustedModel,
    [Alias('Profile')]
    [string]$HermesProfile,
    [switch]$ReplaceUnmanaged,
    [switch]$NoGitPull
)

$ErrorActionPreference = 'Stop'
$DefaultSource = 'git+https://github.com/junhewk/closed-review.git'

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "'$File $($Arguments -join ' ')' failed with exit code $LASTEXITCODE"
    }
}

# Windows PowerShell 5.1 turns native stderr into terminating errors under 'Stop'.
function Invoke-Captured {
    param([string]$File, [string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $File @Arguments 2>&1 | ForEach-Object { "$_" }
        return @{ Code = $LASTEXITCODE; Output = ($output -join "`n") }
    } finally {
        $ErrorActionPreference = $previous
    }
}

# 0. This checkout. An old copy of the script would install the newest runner but skip whatever
# the old copy did not know about, so bring the clone up to date first.
$repoRoot = Split-Path -Parent $PSScriptRoot
$hasGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if ($NoGitPull -or $env:CREVIEW_INSTALLER_UPDATED -eq '1') {
    # Skipped on request, or this is the updated copy re-running.
} elseif (-not $hasGit -or (Invoke-Captured git @('-C', $repoRoot, 'rev-parse', '--is-inside-work-tree')).Code -ne 0) {
    Write-Host "==> $repoRoot is not a Git checkout; not updating it"
} elseif ((Invoke-Captured git @('-C', $repoRoot, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')).Code -ne 0) {
    Write-Host "==> $repoRoot has no upstream branch; not updating it"
} else {
    Write-Host "==> Updating this checkout ($repoRoot)"
    $before = (Invoke-Captured git @('-C', $repoRoot, 'rev-parse', 'HEAD')).Output.Trim()
    $scriptBefore = (Get-FileHash -Algorithm SHA256 $PSCommandPath).Hash
    $stashed = $false
    if ((Invoke-Captured git @('-C', $repoRoot, 'status', '--porcelain')).Output.Trim()) {
        Invoke-Checked git @('-C', $repoRoot, 'stash', 'push', '--include-untracked', '-m', 'creview installer')
        $stashed = $true
        Write-Host '    Set local edits aside with git stash'
    }
    $pull = Invoke-Captured git @('-C', $repoRoot, 'pull', '--ff-only')
    Write-Host $pull.Output
    if ($pull.Code -ne 0) {
        if ($stashed) { Invoke-Captured git @('-C', $repoRoot, 'stash', 'pop') | Out-Null }
        Write-Host "Could not fast-forward $repoRoot (it has diverged from its upstream)."
        Write-Host 'Resolve it with git, or rerun with -NoGitPull.'
        exit 1
    }
    if ($stashed) {
        if ((Invoke-Captured git @('-C', $repoRoot, 'stash', 'pop')).Code -eq 0) {
            Write-Host '    Restored local edits'
        } else {
            Write-Host 'Your local edits conflict with the update. They are kept in `git stash list`'
            Write-Host "and the conflicting files are marked in $repoRoot; resolve them, then rerun."
            exit 1
        }
    }
    $after = (Invoke-Captured git @('-C', $repoRoot, 'rev-parse', 'HEAD')).Output.Trim()
    if ($before -eq $after) {
        Write-Host "    Already up to date at $($after.Substring(0, 12))"
    } else {
        Write-Host "    Updated $($before.Substring(0, 12)) -> $($after.Substring(0, 12))"
        if ((Get-FileHash -Algorithm SHA256 $PSCommandPath).Hash -ne $scriptBefore) {
            Write-Host '==> The script itself changed; running the updated version'
            $env:CREVIEW_INSTALLER_UPDATED = '1'
            try {
                & $PSCommandPath @PSBoundParameters
                $code = $LASTEXITCODE
            } finally {
                Remove-Item Env:CREVIEW_INSTALLER_UPDATED -ErrorAction SilentlyContinue
            }
            exit $code
        }
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv is not installed. Install it, open a new PowerShell window, and rerun this script:'
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    exit 1
}

# 1. The creview runner.
$toolDir = (& uv tool dir).Trim()
if (Test-Path (Join-Path $toolDir 'hermes-review')) {
    # The package was called hermes-review (command hreview) before it was renamed.
    Write-Host '==> Removing hermes-review, the old name of closed-review'
    Invoke-Checked uv @('tool', 'uninstall', 'hermes-review')
}
$receipt = Join-Path $toolDir 'closed-review\uv-receipt.toml'
$fromGit = (Test-Path $receipt) -and (Select-String -Path $receipt -Pattern '\bgit\s*=' -Quiet)
$installFrom = $null
if ($Source) {
    $installFrom = $Source
} elseif (-not $fromGit) {
    if (Test-Path $receipt) {
        Write-Host "creview was installed from a local folder; switching to $DefaultSource."
    }
    $installFrom = $DefaultSource
}
if (($installFrom -like 'git+*' -or (-not $installFrom -and $fromGit)) -and
    -not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host 'git is required to install from a Git URL. Install Git for Windows, or pass'
    Write-Host '-Source with the path of a downloaded copy of the repository.'
    exit 1
}
if ($installFrom) {
    Write-Host "==> Installing creview from $installFrom"
    Invoke-Checked uv @('tool', 'install', '--force', $installFrom)
} else {
    Write-Host '==> Updating creview'
    Invoke-Checked uv @('tool', 'upgrade', 'closed-review')
}

$binDir = (& uv tool dir --bin).Trim()
$exe = if ($env:OS -eq 'Windows_NT') { 'creview.exe' } else { 'creview' }
$creview = Join-Path $binDir $exe
if (-not (Test-Path $creview)) {
    throw "creview was not found at $creview after installation"
}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$onPath = @($userPath -split ';' | Where-Object { $_.TrimEnd('\') -ieq $binDir.TrimEnd('\') })
if ($env:OS -eq 'Windows_NT' -and -not $onPath) {
    Write-Host "==> Adding $binDir to your user PATH so Hermes Desktop can run creview"
    Invoke-Checked uv @('tool', 'update-shell')
}
Invoke-Checked $creview @('--version')

# 2. The managed skill in the Hermes profile.
$profileArgs = if ($HermesProfile) { @('--profile', $HermesProfile) } else { @() }
$installArgs = @('hermes', 'install', '--apply') + $profileArgs
if (-not $ReplaceUnmanaged) {
    $dryRun = Invoke-Captured $creview (@('hermes', 'install') + $profileArgs)
    if ($dryRun.Code -ne 0 -and $dryRun.Output -match 'unmanaged skill') {
        Write-Host ''
        Write-Host 'The journal-article-review skill folder was copied by hand, so creview cannot'
        Write-Host 'update it safely. It can be moved to a backup folder (outside skills\, so Hermes'
        Write-Host 'will not load it) and replaced with a managed copy that future runs update.'
        $answer = Read-Host 'Move it to a backup and install the managed copy? [y/N]'
        if ($answer -notmatch '^(y|yes)$') {
            Write-Host 'Skill left unchanged. Rerun with -ReplaceUnmanaged when ready.'
            exit 1
        }
        $ReplaceUnmanaged = $true
    } elseif ($dryRun.Code -ne 0) {
        throw "creview hermes install failed: $($dryRun.Output)"
    }
}
if ($ReplaceUnmanaged) {
    $installArgs += '--replace-unmanaged'
}
Write-Host '==> Installing the journal-article-review skill'
Invoke-Checked $creview $installArgs

# 3. The trusted gateway: the only endpoint confidential material may reach. There is no default.
if ($GatewayUrl -or $Model) {
    if (-not ($GatewayUrl -and $Model)) {
        throw 'Pass -GatewayUrl and -Model together.'
    }
    $gatewayArgs = @('config', 'gateway', '--url', $GatewayUrl, '--model', $Model)
    foreach ($name in @($TrustedModel)) {
        if ($name) { $gatewayArgs += @('--trusted-model', $name) }
    }
    Write-Host '==> Storing the trusted model gateway'
    Invoke-Checked $creview $gatewayArgs
} else {
    $shown = Invoke-Captured $creview @('config', 'show')
    $stored = $null
    try { $stored = ($shown.Output | ConvertFrom-Json).url } catch { $stored = $null }
    if ($stored) {
        Write-Host "==> Trusted gateway: $stored (stored; rerun with -GatewayUrl to change it)"
    } else {
        Write-Host '==> Trusted gateway: none stored; looking for a local model server'
        $found = Invoke-Captured $creview (@('config', 'detect', '--apply') + $profileArgs)
        Write-Host $found.Output
        if ($found.Code -ne 0) {
            Write-Host 'No model server was adopted. Start it, or rerun with -GatewayUrl URL -Model MODEL.'
        }
    }
}

# 4. Doctor. A failure here usually means the profile still needs the trusted model settings.
Write-Host '==> Checking the Hermes profile'
$doctor = Invoke-Captured $creview (@('hermes', 'doctor') + $profileArgs)
Write-Host $doctor.Output
Write-Host ''
if ($doctor.Code -eq 0) {
    Write-Host 'Done. Fully quit and restart Hermes Desktop, then start a new chat.'
} else {
    Write-Host 'Installed, but the doctor check failed (see above). Fix the reported problems in'
    Write-Host 'the Hermes profile, restart Hermes Desktop, and let the skill rerun the check.'
    Write-Host 'Do not supply confidential material until it passes.'
    exit 3
}
