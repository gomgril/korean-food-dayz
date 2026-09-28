"""0.4.9 group 3: textures derived from existing PAA files (needs Blender for image IO).

  seasonedgim/pack.png -> source/KF_Pantry/data/r049_seasonedgim_pack_co.paa
      copy of r043_atlases_seasonedgim_c4a67fe_co.paa whose pack-art half (top) is made opaque:
      the cut-out photo's alpha is composited over the white film colour and the noisy baked
      background columns at the left/right edges are replaced by clean film. The seaweed half
      (bottom) is copied unchanged. Used only by the closed seasonedgim.p3d.

Run:
  blender.exe -b --factory-startup --python tools/models/fixes/tex_g3_blender.py -- [--paa]
"""
import sys, subprocess
from pathlib import Path
import numpy as np
import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tex_g3  # noqa: E402  (write_png, fbm, paths)

TOOLS, REPO = tex_g3.TOOLS, tex_g3.REPO
WORK = TOOLS / 'work' / 'g3tex'


def load_paa(rel):
    WORK.mkdir(parents=True, exist_ok=True)
    png = WORK / (Path(rel).stem + '.png')
    subprocess.run([tex_g3.IMAGETOPAA, str(REPO / 'source' / rel), str(png)], check=True, stdout=subprocess.DEVNULL)
    img = bpy.data.images.load(str(png)); w, h = img.size
    a = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1].copy()   # top-down, linear? (PNG 8-bit sRGB values as stored)


def seasonedgim_pack():
    a = load_paa(r'KF_Pantry\data\r043_atlases_seasonedgim_c4a67fe_co.paa')
    h, w = a.shape[:2]
    top = a[:h // 2]
    art = top[int(0.05 * h):int(0.45 * h), int(0.25 * w):int(0.75 * w)]
    bright = art[(art[..., 3] > 0.5) & (art[..., :3].min(axis=2) > 0.8)][:, :3]
    film = np.median(bright, axis=0)   # match the art's own film colour
    rng = np.random.default_rng(49020)
    tex = film[None, None, :] * (0.97 + 0.05 * tex_g3.fbm(rng, w, 8, 4)[:h // 2, :, None])
    # keep the printed art (logo / name / weight) and replace everything else - the cut-out's
    # hatched alpha fringe and the baked photo background columns - with clean film
    x0, x1, y0, y1 = int(0.24 * w), int(0.77 * w), int(0.02 * h), int(0.495 * h)
    hx = np.clip((np.arange(w) - x0) / 40.0, 0, 1) * np.clip((x1 - np.arange(w)) / 40.0, 0, 1)
    hy = np.clip((np.arange(h // 2) - y0) / 20.0, 0, 1) * np.clip((y1 - np.arange(h // 2)) / 6.0, 0, 1)
    al = (hy[:, None] * hx[None, :])[..., None] * (top[..., 3:4] > 0.5)
    out = a[..., :3].copy()
    out[:h // 2] = top[..., :3] * al + tex * (1 - al)
    return out


OUT = {'seasonedgim': ('pack.png', seasonedgim_pack, 'KF_Pantry', 'r049_seasonedgim_pack_co.paa')}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for topic, (fname, fn, addon, paa) in OUT.items():
        png = TOOLS / 'textures' / topic / fname
        tex_g3.write_png(png, fn())
        print('png', png)
        if '--paa' in argv:
            dst = REPO / 'source' / addon / 'data' / paa
            subprocess.run([tex_g3.IMAGETOPAA, str(png), str(dst)], check=True, stdout=subprocess.DEVNULL)
            print('paa', dst, dst.stat().st_size)


main()
