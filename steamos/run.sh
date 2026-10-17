#!/bin/bash
# Steam launch entry: God of War Sons of Sparta via AnyPS5 (native Linux).
cd "$(dirname "$(readlink -f "$0")")"
mkdir -p logs
[ -x SonsOfSparta-PS5.elf ] || ./prepare.sh >logs/prepare.out 2>&1 || exit 1
export LD_LIBRARY_PATH="$PWD/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
preload="$PWD/libs/libsos_stubs.so"
# tcmalloc: the draw threads free each other's allocations; glibc arenas serialize that on a lock.
[ -f libs/libtcmalloc_minimal.so.4 ] && preload="$PWD/libs/libtcmalloc_minimal.so.4:$preload"
export LD_PRELOAD="$preload${LD_PRELOAD:+:$LD_PRELOAD}"
# Steam's in-process overlay layer wraps every Vulkan call; gamescope draws the overlay anyway.
export DISABLE_VK_LAYER_VALVE_steam_overlay_1=1
export APS5_GC_WAIT_MS=${APS5_GC_WAIT_MS:-5}
# Same zone; lets glibc cache it instead of re-reading it on each call of the title's DST search at startup.
export TZ=${TZ:-:/etc/localtime}
export SOS_START_BORDERLESS=${SOS_START_BORDERLESS:-1}
exec ./SonsOfSparta-PS5.elf "$@" >logs/game.log 2>logs/game.err
