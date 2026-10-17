import json, os, shutil, sys
# apply_abxy.py MEDIA_DIR PATCH_DIR [--revert]
# Byte patches go into fresh copies that replace the originals by rename, so hardlinked twins stay untouched.
media, pdir = sys.argv[1], sys.argv[2]
revert = "--revert" in sys.argv
backup = os.path.join(pdir, "backup")
patches = json.load(open(os.path.join(pdir, "patches.json")))
byfile = {}
for p in patches: byfile.setdefault(p["file"], []).append(p)

def replace(path, edit):
    tmp = path + ".abxy-tmp"
    shutil.copyfile(path, tmp)
    with open(tmp, "r+b") as f: edit(f)
    os.replace(tmp, path)

os.makedirs(backup, exist_ok=True)
for name, items in byfile.items():
    path = os.path.join(media, name)
    def edit(f):
        for p in items:
            key = os.path.join(backup, f"{name}.{p['offset']}")
            f.seek(p["offset"])
            if revert:
                f.write(open(key, "rb").read())
                continue
            cur = f.read(p["size"])
            if not os.path.exists(key): open(key, "wb").write(cur)
            f.seek(p["offset"])
            f.write(open(os.path.join(pdir, p["texture"] + ".bin"), "rb").read())
    replace(path, edit)
    print(("reverted " if revert else "patched ") + name, len(items))

bundle = os.path.join(media, "StreamingAssets/aa/PS5/defaultlocalgroup_assets_.bundle")
saved = os.path.join(backup, "defaultlocalgroup_assets_.bundle")
src = saved if revert else os.path.join(pdir, "defaultlocalgroup_assets_.bundle")
if not revert and not os.path.exists(saved): shutil.copyfile(bundle, saved)
shutil.copyfile(src, bundle + ".abxy-tmp")
os.replace(bundle + ".abxy-tmp", bundle)
print(("reverted " if revert else "patched ") + "defaultlocalgroup_assets_.bundle")
