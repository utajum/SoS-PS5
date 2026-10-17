#!/usr/bin/env python3
# Add or update a non-Steam shortcut with artwork. Run only while Steam is stopped.
import glob, os, re, shutil, struct, sys, zlib

NAME = os.environ.get("SOS_NAME", "God of War: Sons of Sparta")
DIR = os.environ.get("SOS_DIR", "/home/deck/Games/SonsOfSparta")
EXE = '"%s/%s"' % (DIR, os.environ.get("SOS_EXE", "run.sh"))
COMPAT = os.environ.get("SOS_COMPAT")  # e.g. proton_experimental
ART = os.environ.get("SOS_ART", os.path.dirname(os.path.abspath(__file__)) + "/art")  # optional p/grid/hero/logo/icon.png
APPID = zlib.crc32((EXE + NAME).encode()) | 0x80000000


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


def s(k, v): return (1, k.encode(), v.encode())
def n(k, v): return (2, k.encode(), struct.pack("<i", v))


for vdf in glob.glob("/home/deck/.local/share/Steam/userdata/*/config/shortcuts.vdf"):
    grid = os.path.join(os.path.dirname(vdf), "grid")
    os.makedirs(grid, exist_ok=True)
    for src, dst in [("p", "p"), ("grid", ""), ("hero", "_hero"), ("logo", "_logo"), ("icon", "_icon")]:
        if os.path.exists("%s/%s.png" % (ART, src)):
            shutil.copyfile("%s/%s.png" % (ART, src), "%s/%d%s.png" % (grid, APPID, dst))
    entry = [n("appid", struct.unpack("<i", struct.pack("<I", APPID))[0]), s("AppName", NAME), s("Exe", EXE),
             s("StartDir", '"%s/"' % DIR), s("icon", "%s/%d_icon.png" % (grid, APPID)), s("ShortcutPath", ""),
             s("LaunchOptions", ""), n("IsHidden", 0), n("AllowDesktopConfig", 1), n("AllowOverlay", 1),
             n("OpenVR", 0), n("Devkit", 0), s("DevkitGameID", ""), n("DevkitOverrideAppID", 0),
             n("LastPlayTime", 0), s("FlatpakAppID", ""), s("sortas", ""), (0, b"tags", [])]
    d = open(vdf, "rb").read()
    root, end = parse(d, 0)
    assert ser(root) + d[end:] == d, "roundtrip mismatch " + vdf
    t, k, entries = root[0]
    keep = [e for e in entries if not any(kk == b"AppName" and vv == NAME.encode() for _, kk, vv in e[2])]
    keep.append((0, b"", entry))
    keep = [(et, str(i).encode(), ev) for i, (et, ek, ev) in enumerate(keep)]
    shutil.copyfile(vdf, vdf + ".bak")
    open(vdf, "wb").write(ser([(t, k, keep)] + root[1:]) + d[end:])
    print(vdf, "entries", len(keep), "appid", APPID)

if COMPAT:
    cfg = "/home/deck/.local/share/Steam/config/config.vdf"
    t = open(cfg).read()
    t = re.sub(r'\n(\t+)"%d"\n\1\{[^}]*\}' % APPID, "", t)
    m = re.search(r'\n(\t+)"CompatToolMapping"\n\1\{\n', t)
    i = m.group(1) + "\t"
    t = t[:m.end()] + '%s"%d"\n%s{\n%s\t"name"\t\t"%s"\n%s\t"config"\t\t""\n%s\t"priority"\t\t"250"\n%s}\n' % (i, APPID, i, i, COMPAT, i, i, i) + t[m.end():]
    shutil.copyfile(cfg, cfg + ".bak")
    open(cfg, "w").write(t)
    print(cfg, "compat", COMPAT, "appid", APPID)
