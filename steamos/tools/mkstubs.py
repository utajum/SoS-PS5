#!/usr/bin/env python3
# Build libs/libsos_stubs.so: every PS5 import no host library or guest module provides.
# Each stub logs its NID once to stderr and returns 0.
import glob, os, re, subprocess, sys, tempfile

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NID = re.compile(r"^[A-Za-z0-9+\-]{11}$")


def syms(path, undefined):
    out = subprocess.run(["nm", "-D", "--undefined-only" if undefined else "--defined-only", path],
                         capture_output=True, text=True, check=True).stdout
    return {p[-1] for p in (l.split() for l in out.splitlines()) if p and not (undefined and p[-2] == "w")}


def needed(path):
    out = subprocess.run(["readelf", "-d", path], capture_output=True, text=True).stdout
    return re.findall(r"\(NEEDED\).*\[(.*)\]", out)


guests = glob.glob("app0/sce_module/*.guest.prx")
# Only libraries the loader really maps can satisfy a lookup.
loaded, todo = set(), ["SonsOfSparta-PS5.elf"] + guests
while todo:
    f = todo.pop()
    if f in loaded: continue
    loaded.add(f)
    for n in needed(f):
        p = n.replace("$ORIGIN", os.path.dirname(f)) if "$ORIGIN" in n else "libs/" + n
        if os.path.exists(p): todo.append(os.path.normpath(p))
defined = set().union(*(syms(f, False) for f in loaded))
missing = sorted({s for f in ["SonsOfSparta-PS5.elf"] + guests for s in syms(f, True) if NID.match(s)} - defined)

asm = ["\t.text"]
for i, s in enumerate(missing):
    asm += ['\t.globl "%s"' % s, '\t.type "%s", @function' % s, '"%s":' % s, "\tmovl $%d, %%edi" % i, "\tjmp sos_stub_hit@PLT"]
asm += ["\t.section .data.rel.ro", "\t.globl sos_stub_names", "sos_stub_names:"] + ['\t.quad .Ln%d' % i for i in range(len(missing))]
asm += ["\t.section .rodata"] + ['.Ln%d:\t.asciz "%s"' % (i, s) for i, s in enumerate(missing)]
asm += ['\t.section .note.GNU-stack,"",@progbits']
c = """#include <stdio.h>
extern const char *const sos_stub_names[];
static unsigned char seen[%d];
long sos_stub_hit(int i) {
    if (!seen[i]) { seen[i] = 1; fprintf(stderr, "[sos-stub] unimplemented NID %%s\\n", sos_stub_names[i]); }
    return 0;
}
""" % max(len(missing), 1)
with tempfile.TemporaryDirectory() as t:
    open(t + "/s.S", "w").write("\n".join(asm) + "\n")
    open(t + "/h.c", "w").write(c)
    subprocess.run([os.environ.get("CC", "gcc"), "-shared", "-fPIC", "-O2", "-o", "libs/libsos_stubs.so", t + "/h.c", t + "/s.S"], check=True)
print("libsos_stubs.so: %d stubs" % len(missing))
