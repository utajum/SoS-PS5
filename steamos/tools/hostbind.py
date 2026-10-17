#!/usr/bin/env python3
# Give NIDs local binding in a guest module so the loader resolves them in the host libraries,
# as Windows does. The bundled libc's time functions never report a DST change on Linux, which
# leaves the title's DST search loop (the "Sony Interactive Entertainment presents" screen) spinning.
import struct, sys

TIME = ["wLlFkwG9UcQ", "1mecP7RgI2A", "efhK-YSUYYQ", "n7AepwR0s34", "-VVn74ZyhEs",
        "Av3zjWi64Kw", "5bBacGLyLOs", "fiiNDnNBKVY", "jT3xiGpA3B4"]  # time gmtime localtime mktime difftime strftime gmtime_s localtime_s asctime

path = sys.argv[1]
d = bytearray(open(path, "rb").read())
phoff = struct.unpack_from("<Q", d, 0x20)[0]
phent, phnum = struct.unpack_from("<HH", d, 0x36)
loads, dyn = [], None
for i in range(phnum):
    t, _, off, va, _, fs, _, _ = struct.unpack_from("<IIQQQQQQ", d, phoff + i * phent)
    if t == 1: loads.append((va, off, fs))
    if t == 2: dyn = (off, fs)
v2o = lambda v: next(o + v - a for a, o, s in loads if a <= v < a + s)
tags = {}
for i in range(0, dyn[1], 16):
    k, v = struct.unpack_from("<qQ", d, dyn[0] + i)
    if k == 0: break
    tags.setdefault(k, v)
sym, strtab = v2o(tags[6]), v2o(tags[5])
count = struct.unpack_from("<I", d, v2o(tags[4]) + 4)[0]  # DT_HASH nchain
want, done = set(TIME), 0
for i in range(count):
    o = sym + i * 24
    name_off, info = struct.unpack_from("<IB", d, o)
    name = d[strtab + name_off:d.index(b"\0", strtab + name_off)].decode()
    if name in want:
        d[o + 4] = info & 0x0f  # STB_LOCAL
        done += 1
open(path, "wb").write(d)
print("%s: %d of %d NIDs bound to the host" % (path, done, len(want)))
