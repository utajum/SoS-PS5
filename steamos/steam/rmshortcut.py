#!/usr/bin/env python3
# Remove a non-Steam shortcut by appid, plus its artwork and config.vdf blocks. Run only while Steam is stopped.
import glob, os, re, shutil, struct, sys

APPID = int(sys.argv[1])


def parse(d, i):
    m = []
    while True:
        t = d[i]; i += 1
        if t == 8: return m, i
        j = d.index(b"\0", i); k = d[i:j]; i = j + 1
        if t == 0: v, i = parse(d, i)
        elif t == 1: j = d.index(b"\0", i); v = d[i:j]; i = j + 1
        elif t == 2: v = d[i:i + 4]; i += 4
        elif t == 7: v = d[i:i + 8]; i += 8
        else: raise ValueError("type %d at %d" % (t, i))
        m.append((t, k, v))


def ser(m):
    o = b""
    for t, k, v in m:
        o += bytes([t]) + k + b"\0"
        o += ser(v) if t == 0 else (v + b"\0" if t == 1 else v)
    return o + b"\x08"


key = struct.pack("<I", APPID)
for vdf in glob.glob("/home/deck/.local/share/Steam/userdata/*/config/shortcuts.vdf"):
    d = open(vdf, "rb").read()
    root, end = parse(d, 0)
    assert ser(root) + d[end:] == d, "roundtrip mismatch " + vdf
    t, k, entries = root[0]
    keep = [e for e in entries if not any(kk.lower() == b"appid" and vv == key for _, kk, vv in e[2])]
    keep = [(et, str(i).encode(), ev) for i, (et, ek, ev) in enumerate(keep)]
    shutil.copyfile(vdf, vdf + ".bak")
    open(vdf, "wb").write(ser([(t, k, keep)] + root[1:]) + d[end:])
    for art in glob.glob(os.path.join(os.path.dirname(vdf), "grid", "%d*" % APPID)): os.remove(art)
    print(vdf, "removed", len(entries) - len(keep), "left", len(keep))

cfg = "/home/deck/.local/share/Steam/config/config.vdf"
t = open(cfg).read()
pat = r'\n(\t+)"%d"\n\1\{[^}]*\}' % APPID
n = len(re.findall(pat, t))
shutil.copyfile(cfg, cfg + ".bak")
open(cfg, "w").write(re.sub(pat, "", t))
print(cfg, "blocks removed", n)
