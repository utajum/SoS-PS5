import os, sys, json, subprocess, shutil, tempfile
import numpy as np
from PIL import Image
import UnityPy
sys.path.insert(0, os.path.dirname(__file__))
import ps5tile, bundlepatch

# Redraws the PS face-button glyphs (cross/circle/square/triangle) as A/B/X/Y in the game's own sheets.
# Writes a patch kit (texture bytes + patched bundle + apply_abxy.py); offsets and sizes never change.
# usage: abxy.py SRC_MEDIA_DIR OUT_DIR [--preview]
LETTER = {"cross": "A", "circle": "B", "square": "X", "triangle": "Y"}
# texture -> asset file, face cells (top-down x0, y0, x1, y1)
SHEETS = {
    "PS_ButtonPrompts": ("resources.assets", {"circle": (15, 15, 82, 81), "cross": (111, 15, 179, 81), "triangle": (208, 16, 274, 82), "square": (304, 16, 370, 80)}),
    "ButtonPromptSheetTemp(256,64)": ("sharedassets3.assets", {"square": (0, 0, 64, 64), "circle": (64, 0, 128, 64), "cross": (128, 0, 192, 64), "triangle": (192, 0, 256, 64)}),
    "outline_sheet_promptsheet(256,256)": ("sharedassets3.assets", {"circle": (0, 0, 64, 64), "cross": (64, 0, 128, 64), "square": (192, 64, 256, 128), "triangle": (64, 128, 128, 192)}),
    "PS5_PromptSheet_Icon(512,256)": ("sharedassets3.assets", {"square": (192, 128, 256, 192), "triangle": (256, 128, 320, 192), "circle": (320, 128, 384, 192), "cross": (384, 128, 448, 192)}),
}
BC = {10: 8, 12: 16}

def find_texture(env, name):
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            tex = obj.read()
            if tex.m_Name == name: return tex
    raise SystemExit(f"texture {name} not found")

def read_raw(media, tex):
    sd = tex.m_StreamData
    path = os.path.join(media, sd.path.split("/")[-1])
    with open(path, "rb") as f:
        f.seek(sd.offset); return path, sd.offset, f.read(sd.size)

def decode(raw, tex):
    w, h, fmt = tex.m_Width, tex.m_Height, int(tex.m_TextureFormat)
    if fmt in BC:
        blocks = ps5tile.detile(raw, w // 4, h // 4, BC[fmt])
        im = Image.frombytes("RGBA", (w, h), blocks.tobytes(), "bcn", 3 if fmt == 12 else 1)
        return np.asarray(im)[::-1].copy(), blocks
    return ps5tile.detile(raw, w, h, 4)[::-1].copy(), None

def circle_fit(cell):
    a = cell[..., 3] > 16
    ys, xs = np.nonzero(a)
    return (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2, (xs.max() - xs.min() + 1) / 2

def radial(cell, cx, cy):
    h, w = cell.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    return np.hypot(x + 0.5 - cx, y + 0.5 - cy)

def face_style(cross):
    """fill colour, inner ring radius and symbol ink, read straight up from the centre (the X arms are diagonal)"""
    cell = cross.astype(float)
    cx, cy, R = circle_fit(cross)
    col = int(cx)
    up = [cell[int(cy) - k, col] for k in range(0, int(R))]
    fill = np.median(up[int(R * 0.25):int(R * 0.45)], axis=0)
    ring = next(k for k in range(int(R * 0.45), len(up)) if np.abs(up[k] - fill).max() > 40)
    r = radial(cell, cx, cy)
    sym = (r < ring * 0.8) & (np.abs(cell - fill).max(axis=2) > 60)
    return fill, ring, np.median(cell[sym], axis=0)

def letter_masks(abxy):
    masks = {}
    for i, L in enumerate("ABXY"):
        cell = abxy[0:64, i * 64:(i + 1) * 64].astype(float)
        cx, cy, R = circle_fit(cell.astype(np.uint8))
        m = cell[..., 3] / 255 * (radial(cell, cx, cy) < R * 0.78)
        ys, xs = np.nonzero(m > 0.05)
        masks[L] = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return masks

def rebuild(img, cells, masks):
    x0, y0, x1, y1 = cells["cross"]
    fill, ring, ink = face_style(img[y0:y1, x0:x1])
    out = img.copy()
    for name, (x0, y0, x1, y1) in cells.items():
        cell = img[y0:y1, x0:x1]
        cx, cy, _ = circle_fit(cell)
        # clear the old symbol: fill the disk inside the ring, feathered over 1 px
        a = np.clip(ring - 0.5 - radial(cell, cx, cy), 0, 1)[..., None]
        b = cell * (1 - a) + fill * a
        m = masks[LETTER[name]]
        scale = ring * 0.95 / m.shape[0]
        mw, mh = max(1, round(m.shape[1] * scale)), max(1, round(m.shape[0] * scale))
        mi = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((mw, mh), Image.LANCZOS)) / 255
        canvas = np.zeros(cell.shape[:2])
        ox, oy = int(round(cx - mw / 2)), int(round(cy - mh / 2))
        canvas[oy:oy + mh, ox:ox + mw] = mi
        k = canvas[..., None]
        out[y0:y1, x0:x1] = np.clip(b * (1 - k) + ink * k, 0, 255).round().astype(np.uint8)
    return out

def encode_bc3(img_bottom_up):
    """DXT5 blocks (row-major, rows from texture row 0) via ImageMagick"""
    h, w = img_bottom_up.shape[:2]
    with tempfile.TemporaryDirectory() as tmp:
        Image.fromarray(img_bottom_up, "RGBA").save(os.path.join(tmp, "in.png"))
        subprocess.run(["convert", os.path.join(tmp, "in.png"), "-define", "dds:compression=dxt5", "-define", "dds:mipmaps=0",
                        "-define", "dds:cluster-fit=true", os.path.join(tmp, "out.dds")], check=True)
        data = open(os.path.join(tmp, "out.dds"), "rb").read()
    return np.frombuffer(data[128:128 + (w // 4) * (h // 4) * 16], np.uint8).reshape(h // 4, w // 4, 16)

def main():
    src, out = sys.argv[1], sys.argv[2]
    preview = "--preview" in sys.argv
    os.makedirs(out, exist_ok=True)
    envs = {"resources.assets": UnityPy.load(os.path.join(src, "resources.assets"))}
    abxy = None
    for obj in envs["resources.assets"].objects:
        if obj.type.name == "Texture2D":
            t = obj.read()
            if t.m_Name == "ABXY_Controller_Sheet(384,256)" and int(t.m_TextureFormat) == 4: abxy = decode(read_raw(src, t)[2], t)[0]
    masks = letter_masks(abxy)
    patches = []
    for name, (asset, cells) in SHEETS.items():
        env = envs.setdefault(asset, UnityPy.load(os.path.join(src, asset)))
        tex = find_texture(env, name)
        path, offset, raw = read_raw(src, tex)
        img, blocks = decode(raw, tex)
        new = rebuild(img, cells, masks)
        if preview:
            Image.fromarray(np.hstack([img, new]), "RGBA").save(os.path.join(out, f"{name}.png"))
        up = new[::-1].copy()
        fmt = int(tex.m_TextureFormat)
        if fmt in BC:
            enc = encode_bc3(up)
            merged = blocks.copy()
            H = tex.m_Height
            for (x0, y0, x1, y1) in cells.values():
                by0, by1 = (H - y1) // 4, (H - y0 + 3) // 4
                merged[by0:by1, x0 // 4:(x1 + 3) // 4] = enc[by0:by1, x0 // 4:(x1 + 3) // 4]
            data = ps5tile.tile(merged, len(raw), BC[fmt], base=raw)
        else:
            data = ps5tile.tile(up, len(raw), 4, base=raw)
        patches.append({"file": os.path.basename(path), "offset": offset, "size": len(raw), "texture": name})
        with open(os.path.join(out, f"{name}.bin"), "wb") as f: f.write(data)
    json.dump(patches, open(os.path.join(out, "patches.json"), "w"), indent=1)
    # the Addressables bundle carries its own copy of PS_ButtonPrompts
    bundle = os.path.join(src, "StreamingAssets/aa/PS5/defaultlocalgroup_assets_.bundle")
    offset, size = bundlepatch.texture_offset(bundle, "PS_ButtonPrompts")
    bundlepatch.patch_bundle(bundle, os.path.join(out, "defaultlocalgroup_assets_.bundle"), offset,
                             open(os.path.join(out, "PS_ButtonPrompts.bin"), "rb").read())
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply_abxy.py"), out)
    print(json.dumps(patches, indent=1))

main()
