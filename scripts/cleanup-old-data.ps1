<#
Manually remove the retired local database and its old secrets after switching
to .runtime/current. This script never touches the active database.
Preview: .\scripts\cleanup-old-data.ps1 -WhatIf
Run:     .\scripts\cleanup-old-data.ps1
#>
[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$taskProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskRuntime = [System.IO.Path]::GetFullPath((Join-Path $taskProject '.runtime'))
$taskConfig = Join-Path $taskProject '.env'
$taskCurrentDatabase = Join-Path $taskRuntime 'current\team-nav.db'
if (-not (Test-Path -LiteralPath $taskCurrentDatabase -PathType Leaf)) {
    throw 'The new active database does not exist. Nothing was removed.'
}
if (-not (Test-Path -LiteralPath $taskConfig -PathType Leaf)) {
    throw 'Cannot confirm the active database configuration. Nothing was removed.'
}
$taskSettings = Get-Content -LiteralPath $taskConfig
if (-not ($taskSettings -match '^TEAM_NAV_DATABASE_URL=.*[/\\]current[/\\]team-nav\.db$')) {
    throw 'The active database is not .runtime/current/team-nav.db. Nothing was removed.'
}
$taskRetiredFiles = @(
    'team-nav.db',
    'team-nav.db-wal',
    'team-nav.db-shm',
    'backups\before-independent-accounts.db',
    'secrets\credential.key',
    'secrets\setup-token'
)
foreach ($taskRelativeFile in $taskRetiredFiles) {
    $taskTarget = [System.IO.Path]::GetFullPath((Join-Path $taskRuntime $taskRelativeFile))
    if (-not $taskTarget.StartsWith($taskRuntime + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'A retired file resolved outside the application runtime.'
    }
    if ($taskTarget.StartsWith((Join-Path $taskRuntime 'current') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'The active database directory must never be removed.'
    }
    if (Test-Path -LiteralPath $taskTarget -PathType Leaf) {
        if ($PSCmdlet.ShouldProcess($taskTarget, 'Delete retired application data')) {
            Remove-Item -LiteralPath $taskTarget -Force -ErrorAction Stop
            Write-Output "Removed: $taskTarget"
        }
    }
}
