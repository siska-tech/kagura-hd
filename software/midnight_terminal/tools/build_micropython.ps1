# SPDX-License-Identifier: Apache-2.0
param(
    [string]$MicroPython = 'build/midnight-micropython-src',
    [string]$Output = 'build/midnight-micropython',
    [string]$MpyCross = 'build/midnight-mpy-cross/mpy_cross/mpy-cross.exe',
    [string]$Python = 'python3.12',
    [ValidateSet(1,4)][int]$HostLanes = 4,
    [string]$Picotool = 'build/midnight-hardware/picotool/picotool/picotool.exe'
)
# Compatibility command; applications are deployed separately from the GPU FW.
& "$PSScriptRoot/../../kagura_runtime/tools/build.ps1" @PSBoundParameters
