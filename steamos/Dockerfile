FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++-14 gcc-14 cmake ninja-build git python3 pkg-config nasm yasm ca-certificates patchelf binutils \
    libx11-dev libxext-dev libxrandr-dev libxcursor-dev libxi-dev libxss-dev libxfixes-dev \
    libxkbcommon-dev libwayland-dev wayland-protocols libdecor-0-dev libegl-dev libgl-dev \
    libdrm-dev libgbm-dev libvulkan-dev libudev-dev libdbus-1-dev \
    libpulse-dev libasound2-dev libpipewire-0.3-dev libjack-jackd2-dev \
 && rm -rf /var/lib/apt/lists/*
ENV CC=gcc-14 CXX=g++-14
