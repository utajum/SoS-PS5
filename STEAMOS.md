# SteamOS install (native Linux, AMD)

This fork adds SteamOS support on top of the open Linux port ([upstream PR #11](https://github.com/OverkillLabs3/SoS-PS5/pull/11)), plus fixes for stutter and AMD rendering.
No Proton: the game runs as a native Linux process from a Steam shortcut.

Tested on a Lenovo Legion Go S (Ryzen Z2 Go, SteamOS 3.8.28, Mesa 26.2 RADV) with PPSA28997 v01.008.001.
The Steam Deck runs the same SteamOS and driver, but it is untested.

**Status:** the game is playable from the logos through the opening areas. Menus run at 60 FPS, gameplay at 46-60 FPS. The heaviest scenes run at about 46 FPS on the Z2 Go.

## You need

- Your own decrypted dump: `eboot.bin`, `sce_module`, `sce_sys` and `Media`. `Media/Modules` and `Media/Plugins` must be decrypted ELF files too. No game files are included.
- A Linux PC with Docker and git, for the build and the relink.
- About 30 GB free on the handheld, and SSH or a USB drive to copy the folder.

## 1. Build (PC)

```
git clone --recursive -b steamos https://github.com/utajum/SoS-PS5.git
cd SoS-PS5
steamos/build.sh
```

## 2. Package with your dump (PC)

```
steamos/package.sh /path/to/PPSA28997 out/SonsOfSparta
```

This copies the libraries and relinks the game. It also converts the modules and builds `libsos_stubs.so`, which stubs out the PS5 imports that are not implemented yet.

## 3. Copy to the handheld

```
rsync -a out/SonsOfSparta/ deck@<handheld-ip>:Games/SonsOfSparta/
```

Optional, but faster: on the handheld, in Konsole or over SSH, run:

```
cp -L /usr/lib/libtcmalloc_minimal.so.4 ~/Games/SonsOfSparta/libs/
```

## 4. Add to Steam

1. Switch to Desktop Mode.
2. In Steam, choose **Games > Add a Non-Steam Game > Browse** and pick `~/Games/SonsOfSparta/run.sh`.
3. Leave **Compatibility** off.
4. Return to Game Mode.

To script it instead, stop Steam and run `python3 steamos/steam/addshortcut.py`. Set the `SOS_DIR`, `SOS_NAME` and `SOS_ART` (optional `p`/`grid`/`hero`/`logo`/`icon.png`) environment variables to change the defaults. To remove a shortcut, run `steamos/steam/rmshortcut.py APPID`.

## 5. Optional: A/B/X/Y face-button icons

The launcher's Xbox icon option (`SOS_CONTROLLER_BUTTON_ICONS`) only works on Windows. This step redraws the PlayStation face-button icons in the game's own sheets from your own files:

| PlayStation | Becomes |
|---|---|
| Cross | A |
| Circle | B |
| Square | X |
| Triangle | Y |

On the PC (needs ImageMagick `convert`):

```
python3 -m venv v && v/bin/pip install UnityPy numpy pillow
v/bin/python steamos/glyphs/abxy.py out/SonsOfSparta/app0/Media out/abxy
rsync -a out/abxy deck@<handheld-ip>:Games/SonsOfSparta/
```

On the handheld:

```
cd ~/Games/SonsOfSparta && python3 abxy/apply_abxy.py app0/Media abxy
```

To undo, add `--revert` to the same command. Patched files are written as new files, so hard-linked copies of the dump are not changed.

## Notes

- Saves are in `_sd/` and logs in `logs/`, both in the game folder.
- On the first start, shaders compile, so expect a brief stutter. Later starts use the cache.
- In Settings, switch between the left and right columns with L2/R2. The d-pad only moves inside a column.
- Set GPU clocks and TDP in Steam's Quick Access menu. A Steam shortcut runs inside the Steam Linux Runtime, where `/sys` is read-only.

## Changes in this fork

| Change | Effect |
|---|---|
| Guest GC stop-the-world: mark arrival at handler entry, take the baseline before `pthread_kill`, no wake-all herd | 130-270 ms freezes about once a second are gone; fixes a deadlock |
| Unwind: keep `PT_GNU_EH_FRAME` and cache module lookups | Guest C++ exceptions work; 150 ms stalls per throw are gone |
| Per-address umtx wait buckets | Kernel time drops from 48% to 20% |
| `DrawBackend` spins on `pause` instead of `sched_yield` | One core no longer burns while idle |
| Recompiler: helper lanes are spared in the final kill | Works around a Mesa ACO miscompile that froze frames on RADV |
| `DB_RENDER_CONTROL` stencil clear | Supports draws that were rejected before |
| `PROCMAP_QUERY` fallback | Builds against older kernel headers |
| `run.sh`: tcmalloc preload and Steam overlay layer off | Gameplay goes from about 43 to about 47 FPS in heavy scenes |

## Uninstall

Remove the shortcut in Steam, then delete `~/Games/SonsOfSparta`.
