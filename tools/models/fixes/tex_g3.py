"""0.4.9 group 3: procedural textures (numpy + stdlib PNG writer, deterministic seeds).

Writes PNG sources to tools/models/textures/<topic>/ and, with --paa, converts them with
ImageToPAA into source/KF_Pantry/data/r049_<topic>_<name>_co.paa.

  opened_contents/contents.png  512x512, 2x2 atlas (u right, v down):
      [0.0-0.5, 0.0-0.5] instant-coffee-mix powder (tan powder, coffee granules, sugar crystals)
      [0.5-1.0, 0.0-0.5] freeze-dried doenjang soup block (ochre porous block, greens, tofu bits)
      [0.0-0.5, 0.5-1.0] freeze-dried egg soup block (yellow egg curds, green onion, seaweed bits)
      [0.5-1.0, 0.5-1.0] block side/crumb (neutral porous, used for the block sides)
  paper_cup/band.png        512x512, white paper with a subtle, horizontally seamless printed band
                            (u wraps around the cup, v = 0 at the rim).

Run with a Python that has numpy (Blender's bundled python):
  <python> tools/models/fixes/tex_g3.py [--paa]
"""
import sys, zlib, struct, subprocess
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
IMAGETOPAA = r"C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe"


def write_png(path, rgb):
    a = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    h, w = a.shape[:2]
    raw = b''.join(b'\x00' + a[y].tobytes() for y in range(h))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) \
        + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(png)


def value_noise(rng, n, cells, wrap=True):
    """Tileable bilinear value noise n x n with `cells` cells."""
    g = rng.random((cells, cells))
    x = np.arange(n) * cells / n
    i0 = np.floor(x).astype(int); t = x - i0; t = t * t * (3 - 2 * t)
    i1 = (i0 + 1) % cells
    a = g[i0][:, i0] * (1 - t)[None, :] + g[i0][:, i1] * t[None, :]
    b = g[i1][:, i0] * (1 - t)[None, :] + g[i1][:, i1] * t[None, :]
    return a * (1 - t)[:, None] + b * t[:, None]


def fbm(rng, n, base=4, octaves=5):
    out = np.zeros((n, n)); amp = 1.0; tot = 0
    for o in range(octaves):
        out += amp * value_noise(rng, n, base * 2 ** o); tot += amp; amp *= 0.5
    return out / tot


def blobs(rng, n, count, rmin, rmax, soft=0.35):
    """Tileable mask of `count` soft round blobs."""
    yy, xx = np.mgrid[0:n, 0:n]
    m = np.zeros((n, n))
    for _ in range(count):
        cx, cy = rng.random(2) * n; r = rmin + rng.random() * (rmax - rmin)
        dx = np.minimum(abs(xx - cx), n - abs(xx - cx)); dy = np.minimum(abs(yy - cy), n - abs(yy - cy))
        d = np.sqrt(dx * dx + dy * dy) / r
        m = np.maximum(m, np.clip((1 - d) / soft, 0, 1))
    return m


def flakes(rng, n, count, lmin, lmax, wmin, wmax):
    """Tileable mask of thin elongated flakes (green onion / seaweed bits)."""
    yy, xx = np.mgrid[0:n, 0:n]
    m = np.zeros((n, n))
    for _ in range(count):
        cx, cy = rng.random(2) * n; ang = rng.random() * np.pi
        L = lmin + rng.random() * (lmax - lmin); W = wmin + rng.random() * (wmax - wmin)
        dx = (xx - cx + n / 2) % n - n / 2; dy = (yy - cy + n / 2) % n - n / 2
        a = dx * np.cos(ang) + dy * np.sin(ang); b = -dx * np.sin(ang) + dy * np.cos(ang)
        d = np.maximum(abs(a) / (L / 2), abs(b) / (W / 2))
        m = np.maximum(m, np.clip((1 - d) / 0.3, 0, 1))
    return m


def squares(rng, n, count, smin, smax):
    yy, xx = np.mgrid[0:n, 0:n]
    m = np.zeros((n, n))
    for _ in range(count):
        cx, cy = rng.random(2) * n; s = smin + rng.random() * (smax - smin); ang = rng.random() * np.pi / 2
        dx = (xx - cx + n / 2) % n - n / 2; dy = (yy - cy + n / 2) % n - n / 2
        a = dx * np.cos(ang) + dy * np.sin(ang); b = -dx * np.sin(ang) + dy * np.cos(ang)
        d = np.maximum(abs(a), abs(b)) / (s / 2)
        m = np.maximum(m, np.clip((1 - d) / 0.25, 0, 1))
    return m


def mix(base, col, mask):
    return base * (1 - mask[..., None]) + np.array(col)[None, None, :] * mask[..., None]


def coffee_powder(n, rng):
    grain = fbm(rng, n, 16, 4)
    fine = rng.random((n, n))
    base = np.array([0.80, 0.66, 0.48])[None, None, :] * (0.86 + 0.18 * grain[..., None] + 0.06 * fine[..., None])
    base = mix(base, (0.34, 0.19, 0.09), (rng.random((n, n)) > 0.965).astype(float) * 0.9)   # coffee granules
    base = mix(base, (0.52, 0.34, 0.18), blobs(rng, n, 60, 1.5, 3.5, 0.6) * 0.8)
    base = mix(base, (0.96, 0.95, 0.90), (rng.random((n, n)) > 0.975).astype(float) * 0.85)  # sugar
    return base


def porous(rng, n, col, dark, light):
    f = fbm(rng, n, 6, 5)
    pores = blobs(rng, n, 220, 1.2, 3.5, 0.5)
    base = np.array(col)[None, None, :] * (0.80 + 0.35 * f[..., None])
    base = mix(base, dark, pores * 0.55)
    base = mix(base, light, blobs(rng, n, 90, 2, 6, 0.8) * 0.35)
    return base


def doenjang_block(n, rng):
    base = porous(rng, n, (0.63, 0.45, 0.24), (0.38, 0.25, 0.12), (0.78, 0.62, 0.38))
    base = mix(base, (0.93, 0.90, 0.80), squares(rng, n, 16, 9, 15) * 0.8)       # tofu cubes
    base = mix(base, (0.24, 0.40, 0.14), flakes(rng, n, 26, 10, 26, 3, 6) * 0.9)  # spinach / green onion
    base = mix(base, (0.14, 0.18, 0.10), flakes(rng, n, 14, 8, 18, 3, 7) * 0.8)   # seaweed
    return base


def egg_block(n, rng):
    base = porous(rng, n, (0.93, 0.79, 0.38), (0.72, 0.56, 0.22), (1.0, 0.93, 0.62))
    base = mix(base, (0.99, 0.90, 0.55), blobs(rng, n, 50, 6, 14, 0.7) * 0.6)     # egg curds
    base = mix(base, (0.30, 0.52, 0.18), flakes(rng, n, 30, 8, 22, 3, 6) * 0.9)   # green onion
    base = mix(base, (0.12, 0.15, 0.09), flakes(rng, n, 10, 6, 14, 3, 6) * 0.75)  # seaweed
    return base


def block_side(n, rng):
    return porous(rng, n, (0.70, 0.56, 0.33), (0.45, 0.32, 0.17), (0.85, 0.72, 0.48))


def contents(n=512):
    h = n // 2
    img = np.zeros((n, n, 3))
    img[:h, :h] = coffee_powder(h, np.random.default_rng(49001))
    img[:h, h:] = doenjang_block(h, np.random.default_rng(49002))
    img[h:, :h] = egg_block(h, np.random.default_rng(49003))
    img[h:, h:] = block_side(h, np.random.default_rng(49004))
    return img


def paper_band(n=512):
    rng = np.random.default_rng(49010)
    paper = np.array([0.935, 0.935, 0.915])[None, None, :] * (0.975 + 0.035 * fbm(rng, n, 32, 3)[..., None])
    img = paper.copy()
    v = (np.arange(n) + 0.5) / n
    u = (np.arange(n) + 0.5) / n
    V, U = np.meshgrid(v, u, indexing='ij')
    teal = np.array([0.20, 0.46, 0.56]); pale = np.array([0.80, 0.89, 0.91])
    b0, b1 = 0.42, 0.60          # band (v, measured from the rim)
    band = ((V > b0) & (V < b1)).astype(float)
    img = mix(img, pale, band * 0.85)
    for c in (b0, b1):
        line = np.clip(1 - abs(V - c) * n / 2.2, 0, 1)
        img = mix(img, teal, line)
    # a thin wave through the band: 12 periods around the cup (seamless)
    wave_c = (b0 + b1) / 2 + 0.035 * np.sin(U * 2 * np.pi * 12)
    img = mix(img, teal, np.clip(1 - abs(V - wave_c) * n / 2.0, 0, 1) * 0.9 * band)
    # small dots between the wave crests
    for k in range(12):
        cu = (k + 0.75) / 12; cv = (b0 + b1) / 2
        d = np.sqrt(((np.minimum(abs(U - cu), 1 - abs(U - cu))) * n) ** 2 + ((V - cv) * n) ** 2)
        img = mix(img, teal, np.clip(1 - d / 5.0, 0, 1) * 0.9)
    return img


OUT = {
    'opened_contents': ('contents.png', contents, 'KF_Pantry', 'r049_opened_contents_co.paa'),
    'paper_cup': ('band.png', paper_band, 'KF_Pantry', 'r049_paper_cup_band_co.paa'),
}


def main():
    for topic, (fname, fn, addon, paa) in OUT.items():
        png = TOOLS / 'textures' / topic / fname
        write_png(png, fn())
        print('png', png)
        if '--paa' in sys.argv:
            dst = REPO / 'source' / addon / 'data' / paa
            subprocess.run([IMAGETOPAA, str(png), str(dst)], check=True, stdout=subprocess.DEVNULL)
            print('paa', dst, dst.stat().st_size)


if __name__ == '__main__':
    main()
