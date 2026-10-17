import numpy as np
# PS5/GFX10 2D texture (de)tiling, 1 mip, SW_4KB_S / SW_64KB_S; port of AnyPS5 TextureDetile.comp
LOG2_4KB = {1: (6, 6), 2: (6, 5), 4: (5, 5), 8: (5, 4), 16: (4, 4)}
LOG2_64KB = {1: (8, 8), 2: (8, 7), 4: (7, 7), 8: (7, 6), 16: (6, 6)}

def _std(x, y, bpe):
    if bpe == 1:
        return ((y << 4) & 0x1f0) ^ ((y << 5) & 0x400) ^ (x & 0x00f) ^ ((x << 5) & 0x200) ^ ((x << 6) & 0x800)
    if bpe == 2:
        return ((y << 4) & 0x070) ^ ((y << 5) & 0x100) ^ ((y << 6) & 0x400) ^ ((x << 1) & 0x00e) ^ ((x << 4) & 0x080) ^ ((x << 5) & 0x200) ^ ((x << 6) & 0x800)
    if bpe == 4:
        return ((y << 4) & 0x070) ^ ((y << 5) & 0x100) ^ ((y << 6) & 0x400) ^ ((x << 2) & 0x00c) ^ ((x << 5) & 0x080) ^ ((x << 6) & 0x200) ^ ((x << 7) & 0x800)
    if bpe == 8:
        return ((y << 4) & 0x030) ^ ((y << 6) & 0x100) ^ ((y << 7) & 0x400) ^ ((x << 3) & 0x008) ^ ((x << 5) & 0x0c0) ^ ((x << 6) & 0x200) ^ ((x << 7) & 0x800)
    return ((y << 4) & 0x030) ^ ((y << 6) & 0x100) ^ ((y << 7) & 0x400) ^ ((x << 6) & 0x0c0) ^ ((x << 7) & 0x200) ^ ((x << 8) & 0x800)

def _std64(x, y, bpe):
    if bpe == 1: return ((x << 7) & 0x2000) ^ ((x << 8) & 0x8000) ^ ((y << 6) & 0x1000) ^ ((y << 7) & 0x4000)
    if bpe == 2: return ((x << 7) & 0x2000) ^ ((x << 8) & 0x8000) ^ ((y << 7) & 0x1000) ^ ((y << 8) & 0x4000)
    if bpe == 4: return ((x << 8) & 0x2000) ^ ((x << 9) & 0x8000) ^ ((y << 7) & 0x1000) ^ ((y << 8) & 0x4000)
    if bpe == 8: return ((x << 8) & 0x2000) ^ ((x << 9) & 0x8000) ^ ((y << 8) & 0x1000) ^ ((y << 9) & 0x4000)
    return ((x << 9) & 0x2000) ^ ((x << 10) & 0x8000) ^ ((y << 8) & 0x1000) ^ ((y << 9) & 0x4000)

def offsets(w, h, bpe=4, mode="4KB_S"):
    """byte offset of each element in the tiled surface; w/h in elements"""
    y, x = np.mgrid[0:h, 0:w].astype(np.uint64)
    lw, lh = (LOG2_4KB if mode == "4KB_S" else LOG2_64KB)[bpe]
    bb = 4096 if mode == "4KB_S" else 65536
    o = _std(x, y, bpe)
    if bb > 4096: o ^= _std64(x, y, bpe)
    o &= np.uint64(bb - 1)
    bpr = (w + (1 << lw) - 1) >> lw
    return ((y >> np.uint64(lh)) * np.uint64(bpr) + (x >> np.uint64(lw))) * np.uint64(bb) + o

def detile(data, w, h, bpe=4, mode="4KB_S"):
    off = offsets(w, h, bpe, mode)
    src = np.frombuffer(data, np.uint8)
    idx = off[..., None] + np.arange(bpe, dtype=np.uint64)
    return src[idx.astype(np.int64)].reshape(h, w, bpe)

def tile(elems, size, bpe=4, mode="4KB_S", base=None):
    h, w = elems.shape[:2]
    off = offsets(w, h, bpe, mode)
    dst = np.frombuffer(base, np.uint8).copy() if base is not None else np.zeros(size, np.uint8)
    idx = off[..., None] + np.arange(bpe, dtype=np.uint64)
    dst[idx.astype(np.int64)] = elems.reshape(h, w, bpe)
    return dst.tobytes()
