#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Render the PC preview (WAV + 30 fps video). FFMPEG may point to a Windows
# ffmpeg.exe when run from WSL or Git Bash.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../.." && pwd)"
out="${1:-$root/build/fm-megademo}"; ff="${FFMPEG:-ffmpeg}"
bin="$("$here/build_pc.sh" "$out")"
"$bin" --wav "$out/pc.wav"
"$bin" --video - --stats | "$ff" -hide_banner -loglevel error -y -f rawvideo -pix_fmt rgb24 -s 640x360 -r 30 -i - \
    -i "$out/pc.wav" -vf scale=1280:720:flags=neighbor -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -shortest "$out/fm-pc-preview.mp4"
echo "$out/fm-pc-preview.mp4"
