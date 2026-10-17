import sys
import UnityPy
from UnityPy.streams import EndianBinaryReader


def texture_offset(path, name):
    """offset and size of a texture's data in the bundle's .resS"""
    for obj in UnityPy.load(path).objects:
        if obj.type.name == "Texture2D":
            tex = obj.read()
            if tex.m_Name == name: return tex.m_StreamData.offset, tex.m_StreamData.size
    raise SystemExit(f"{name} not in {path}")


def patch_bundle(src, dst, offset, patch):
    """overwrite bytes of the bundle's .resS; every other file in the bundle is kept verbatim"""
    env = UnityPy.load(src)
    bundle = list(env.files.values())[0]
    for name, f in list(bundle.files.items()):
        if type(f).__name__ == "SerializedFile":
            raw = EndianBinaryReader(bytes(f.reader.bytes))
        else:
            data = bytearray(f.bytes)
            if name.endswith(".resS"):
                assert len(data) >= offset + len(patch)
                data[offset:offset + len(patch)] = patch
            raw = EndianBinaryReader(bytes(data))
        raw.flags = f.flags
        bundle.files[name] = raw
    open(dst, "wb").write(bundle.save(packer="original"))


if __name__ == "__main__":
    # bundlepatch.py IN.bundle OUT.bundle OFFSET PATCH.bin
    patch_bundle(sys.argv[1], sys.argv[2], int(sys.argv[3]), open(sys.argv[4], "rb").read())
