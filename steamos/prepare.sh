#!/bin/bash
# Relink the decrypted dump for AnyPS5 on Linux (mirrors the Windows launcher's first-start step).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
mkdir -p prep/sce_module logs
cp source/eboot.bin prep/eboot.elf
for d in sce_module Media/Modules Media/Plugins; do cp source/$d/*.prx prep/sce_module/; done
rm -f SonsOfSparta-PS5.elf SonsOfSparta-PS5.registry.json
tools/relinker --registry --skip-syscall-check \
  --exclude-sce-module CommonDialog.prx --exclude-sce-module libSceNpCppWebApi.prx \
  --defer-sce-module PSN.prx --defer-sce-module SaveData.prx \
  --defer-sce-module VoiceInputPlugin.prx --defer-sce-module lib_burst_generated.prx \
  prep/eboot.elf SonsOfSparta-PS5.elf >logs/prepare.log 2>&1 || { tail -20 logs/prepare.log; exit 1; }
# The Linux writer ignores --defer-sce-module; unlisting them lets sceKernelLoadStartModule init them with their args.
for m in PSN SaveData VoiceInputPlugin lib_burst_generated; do
  patchelf --remove-needed "\$ORIGIN/app0/sce_module/$m.prx.guest.prx" SonsOfSparta-PS5.elf
done
python3 tools/hostbind.py app0/sce_module/libc.prx.guest.prx
chmod +x SonsOfSparta-PS5.elf
echo "prepared: $(ls app0/sce_module | wc -l) guest modules"
