# SPDX-License-Identifier: Apache-2.0
[CmdletBinding()]
param([string]$BuildDir='build/psram-wrap-target/candidate')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
& (Join-Path $root 'tools/check-nano9k-timing.ps1') -BuildDir $BuildDir -BaseName psram_wrap_target -ReportOnly | Out-Null
$build=Join-Path $root $BuildDir
$status=Get-Content (Join-Path $build 'timing-status.json') -Raw | ConvertFrom-Json
$status.scope='Independent diagnostic numeric STA; external PSRAM IO timing/hardware unverified'
$status | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $build 'timing-status.json') -Encoding ascii
$log=Get-Content (Join-Path $build 'build.log') -Raw
$fs=Join-Path $build 'impl/pnr/psram_wrap_target.fs'
$routed=$log.Contains('Placement and routing completed') -and $log.Contains('Bitstream generation completed') -and
    $log -notmatch 'ERROR|[Uu]nrouted|[Rr]outing failed' -and (Test-Path -LiteralPath $fs)
$pass=$null -ne $status.worst.Setup -and $null -ne $status.worst.Hold -and
    $status.worst.Setup.slack_ns -ge 0.100 -and $status.worst.Hold.slack_ns -ge 0 -and
    $status.setup_violated_endpoints -eq 0 -and $status.hold_violated_endpoints -eq 0 -and
    $status.negative_analyses.Count -eq 0 -and $routed
$result=[ordered]@{
    scope='Independent wrap-target observation; numeric internal STA only; external IO not certified'
    quality_gate_pass=[bool]$pass
    setup_gate_ns=0.100
    setup_slack_ns=$status.worst.Setup.slack_ns
    hold_slack_ns=$status.worst.Hold.slack_ns
    setup_violated_endpoints=$status.setup_violated_endpoints
    hold_violated_endpoints=$status.hold_violated_endpoints
    routing_completed=[bool]$routed
    routing_evidence='PnR completion + successful bitstream generation; no error/unrouted message'
    bitstream_sha256=(Get-FileHash -LiteralPath $fs -Algorithm SHA256).Hash.ToLowerInvariant()
    device_programmed=$false
    hardware_pass=$false
    release_ready=$false
}
$result | ConvertTo-Json | Set-Content (Join-Path $build 'diagnostic-gate.json') -Encoding ascii
$result | ConvertTo-Json
if(!$pass) {throw 'Diagnostic numeric quality gate failed; do not program'}
