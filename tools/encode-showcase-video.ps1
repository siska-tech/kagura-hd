# SPDX-License-Identifier: Apache-2.0
param([string]$Ffmpeg='ffmpeg')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$out=Join-Path $root 'build/showcase/preview'
& $Ffmpeg -hide_banner -y -framerate 8 -i (Join-Path $out 'frames/frame_%04d.png') -i (Join-Path $out 'tiny-horizon.wav') -filter_complex '[0:v]scale=1280:720:flags=neighbor,fps=60[v];[1:a]adelay=28000|28000,apad=whole_dur=36[a]' -map '[v]' -map '[a]' -t 36 -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart (Join-Path $out 'kagura-hd-pc-preview.mp4')
if($LASTEXITCODE -ne 0){throw 'PC preview encoding failed'}
$binary=(Get-Command $Ffmpeg).Source
$probe=Join-Path (Split-Path -Parent $binary) 'ffprobe.exe'
if(Test-Path -LiteralPath $probe){
    & $probe -v error -show_entries 'stream=codec_type,width,height,r_frame_rate,sample_rate,channels' -show_entries 'format=duration' -of json (Join-Path $out 'kagura-hd-pc-preview.mp4') | Set-Content -LiteralPath (Join-Path $root 'build/showcase/video-probe.json') -Encoding utf8
    if($LASTEXITCODE -ne 0){throw 'PC preview media probe failed'}
}
