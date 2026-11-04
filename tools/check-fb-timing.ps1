# SPDX-License-Identifier: Apache-2.0
[CmdletBinding()]
param([string]$BuildDir='build/kagura-fb',[switch]$ReportOnly)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'check-nano9k-timing.ps1') -BuildDir $BuildDir -BaseName kagura_fb -ReportOnly | Out-Null
$statusPath=Join-Path (Join-Path $root $BuildDir) 'timing-status.json'
$status=Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
$status.scope='Kagura-FB numeric STA; draft CDC bounds; external PSRAM IO timing and hardware unverified'
$status | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statusPath -Encoding ascii
$status | ConvertTo-Json -Depth 6
if(!$ReportOnly -and ($status.setup_violated_endpoints -gt 0 -or $status.hold_violated_endpoints -gt 0 -or $status.negative_analyses.Count -gt 0 -or $status.worst.Setup.slack_ns -lt 0.10)) {
    throw 'Kagura-FB numeric timing gate failed'
}
