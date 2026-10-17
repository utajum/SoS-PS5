#!/bin/bash
# Build the compatibility libraries and the relinker in a container. Output: build/core/libs/libs, build/core/relinker.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
docker build -t sos-linux-build steamos
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/src -w /src sos-linux-build bash -c \
  'cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DBUILD_WERROR=OFF && cmake --build build --target libs relinker'
