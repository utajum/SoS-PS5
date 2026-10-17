#!/bin/bash
# Assemble a game folder from the build and your own decrypted dump, then relink it and build the stub library.
# usage: steamos/package.sh DUMP_DIR OUT_DIR   (DUMP_DIR holds eboot.bin, sce_module, sce_sys and Media)
set -euo pipefail
repo=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
dump=$(readlink -f "$1")
out=$(readlink -m "$2")
for p in eboot.bin sce_module sce_sys Media/Modules Media/Plugins; do [ -e "$dump/$p" ] || { echo "missing $dump/$p"; exit 1; }; done
[ -f "$repo/build/core/relinker/relinker" ] || { echo "run steamos/build.sh first"; exit 1; }
mkdir -p "$out/libs" "$out/tools" "$out/source/Media" "$out/app0"
# hard links when the dump is on the same filesystem, copies otherwise
link() { cp -al "$@" 2>/dev/null || cp -a "$@"; }
cp "$repo"/build/core/libs/libs/*.prx "$out/libs/"
cp "$repo/build/core/relinker/relinker" "$repo"/steamos/tools/*.py "$out/tools/"
cp "$repo/steamos/run.sh" "$repo/steamos/prepare.sh" "$out/"
for f in "$dump"/*; do
  case "$(basename "$f")" in eboot.bin|sce_module) ;; *) link "$f" "$out/app0/" ;; esac
done
link "$dump/eboot.bin" "$dump/sce_module" "$out/source/"
link "$dump/Media/Modules" "$dump/Media/Plugins" "$out/source/Media/"
docker run --rm -u "$(id -u):$(id -g)" -v "$out":/game -w /game sos-linux-build bash -c './prepare.sh && python3 tools/mkstubs.py'
echo "ready: $out"
