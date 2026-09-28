"""0.4.9 fix group 4 ("packaging"): printed backs / ends / tops / bottoms for boxes, a wrap-around
label for the Binggrae milk bottles and a printed side sleeve for the Nongshim Yukgaejang bowl.

Runs inside Blender (image work uses bpy + numpy; blf renders text with the Windows Malgun Gothic font):

  "<Blender>\\blender.exe" -b --factory-startup --python tools/models/fixes/fix_packaging.py -- [--only a,b] [--no-p3d]

What it does, per model (always derived from tools/models/originals/KF_Pantry/models/<name>.p3d, which is
created from source on first run, so re-runs never accumulate):

* Boxes (the r043/r045 rounded-box generator, 6 LOD0 sides + tiny bevels): every visual-LOD face is
  classified by its dominant outward normal (front = file -Z, as the existing front art).  Faces of the
  sides listed in the model's `remap` set get a new texture r049_pack_<name>_co.paa and a planar UV
  inside that side's rectangle of a 1024x1024 atlas (back | left end | right end / top / bottom).
  Each rectangle has exactly the side's physical aspect, so nothing is stretched, and the art is drawn
  the right way up as seen from outside (orientation derived from the existing front mapping).
  The front (and existing printed backs of gosomi / curry / ghana / yanggaeng) keep their texture/UVs.
* Milk bottles: the whole conical label ring (one ring of faces, y 0.0842..0.1232) gets a cylindrical
  UV (u = angle, v = height) onto a new strip texture.  The strip is made by un-wrapping the existing
  front photo exactly as the old planar mapping showed it from the front, keeping only the printed ink
  (difference to the local photo background) on the bottle's own plastic colour, and repeating the print
  on the back.  Shoulder above the ring and the cap stay plain.
* Yukgaejang bowl (closed + open): outward faces of the bowl wall (y 0.004..0.063, r >= 0.0585) get a
  cylindrical UV onto a printed sleeve built from the lid art (food / purple title panel, Nongshim logo).

Textures: PNG sources in tools/models/textures/packaging/, PAA in source/KF_Pantry/data/r049_pack_*_co.paa
(converted with ImageToPAA).  Geometry, selections, memory points and materials are unchanged.
"""
import bpy, blf, imbuf
import sys, os, math, json, shutil, hashlib, subprocess, zlib
import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import modelfix as mf  # noqa: E402

ADDON = 'KF_Pantry'
SRC = REPO / 'source' / ADDON / 'models'
DATA = REPO / 'source' / ADDON / 'data'
ORIG = TOOLS / 'originals' / ADDON / 'models'
TEXOUT = TOOLS / 'textures' / 'packaging'
WORK = TOOLS / 'work' / 'packaging'
IMAGETOPAA = r"C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe"
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_R = r"C:\Windows\Fonts\malgun.ttf"
TEXPFX = 'KF_Pantry\\data\\'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
NO_P3D = '--no-p3d' in argv


# =============================================================== image helpers (top-down float RGBA, sRGB values)
def hexc(s):
    s = s.lstrip('#')
    return np.array([int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def load_png(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1].copy()


def save_png(arr, path):
    h, w = arr.shape[:2]
    a = np.ones((h, w, 4), np.float32)
    a[..., :arr.shape[2]] = np.clip(arr, 0, 1)
    img = bpy.data.images.new('out', w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    img.filepath_raw = str(path); img.file_format = 'PNG'; img.save()
    bpy.data.images.remove(img)


_paa_cache = {}
def texture_png(tex):
    """Current texture (source .paa) as float RGBA array (converted once into WORK)."""
    if tex in _paa_cache:
        return _paa_cache[tex]
    rel = tex.split('\\', 1)[1] if tex.lower().startswith('kf_pantry\\') else tex
    paa = REPO / 'source' / ADDON / rel
    png = WORK / 'src' / (Path(rel).stem + '.png')
    png.parent.mkdir(parents=True, exist_ok=True)
    if not png.exists():
        subprocess.run([IMAGETOPAA, str(paa), str(png)], check=True, stdout=subprocess.DEVNULL)
    _paa_cache[tex] = load_png(png)
    return _paa_cache[tex]


def box_blur(a, r, axis):
    if r < 1:
        return a
    k = 2 * r + 1
    pad = [(0, 0)] * a.ndim; pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode='edge'), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(k, k + n), axis=axis); lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / k).astype(np.float32)


def resize(a, w, h):
    """Area-prefiltered bilinear resize."""
    H, W = a.shape[:2]
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    if w < W:
        a = box_blur(a, int(W / w / 2), 1)
    if h < H:
        a = box_blur(a, int(H / h / 2), 0)
    xs = (np.arange(w) + 0.5) * W / w - 0.5; ys = (np.arange(h) + 0.5) * H / h - 0.5
    x0 = np.clip(np.floor(xs).astype(int), 0, W - 1); x1 = np.clip(x0 + 1, 0, W - 1); fx = np.clip(xs - x0, 0, 1)
    y0 = np.clip(np.floor(ys).astype(int), 0, H - 1); y1 = np.clip(y0 + 1, 0, H - 1); fy = np.clip(ys - y0, 0, 1)
    r0 = a[y0]; r1 = a[y1]
    r = r0 * (1 - fy)[:, None, None] + r1 * fy[:, None, None]
    return r[:, x0] * (1 - fx)[None, :, None] + r[:, x1] * fx[None, :, None]


def sample(a, u, v):
    """Bilinear sample of a at pixel coords (u=x, v=y) arrays."""
    H, W = a.shape[:2]
    u = np.clip(u, 0, W - 1.001); v = np.clip(v, 0, H - 1.001)
    x0 = np.floor(u).astype(int); y0 = np.floor(v).astype(int); fx = (u - x0)[..., None]; fy = (v - y0)[..., None]
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def canvas(w, h, col):
    c = np.ones((int(h), int(w), 4), np.float32); c[..., :3] = col
    return c


def paste(dst, src, x, y, opacity=1.0):
    """Alpha-composite src (RGBA) onto dst at integer x, y (clipped)."""
    x, y = int(round(x)), int(round(y))
    h, w = src.shape[:2]; H, W = dst.shape[:2]
    sx0, sy0 = max(0, -x), max(0, -y); dx0, dy0 = max(0, x), max(0, y)
    ww, hh = min(w - sx0, W - dx0), min(h - sy0, H - dy0)
    if ww <= 0 or hh <= 0:
        return
    s = src[sy0:sy0 + hh, sx0:sx0 + ww]; d = dst[dy0:dy0 + hh, dx0:dx0 + ww]
    _over(d, s[..., :3], s[..., 3:4] * opacity)


def _over(d, rgb, a):
    """Straight-alpha 'over' of colour rgb with alpha a (HxWx1) onto region d (in place)."""
    da = d[..., 3:4]
    oa = a + da * (1 - a)
    d[..., :3] = np.where(oa > 1e-6, (rgb * a + d[..., :3] * da * (1 - a)) / np.maximum(oa, 1e-6), d[..., :3])
    d[..., 3:4] = oa


def fit(img, bw, bh):
    h, w = img.shape[:2]
    s = min(bw / w, bh / h)
    return resize(img, w * s, h * s)


def paste_fit(dst, img, x, y, bw, bh, align='c', opacity=1.0):
    f = fit(img, bw, bh)
    h, w = f.shape[:2]
    ox = x + (bw - w) / 2 if align in ('c', 't', 'b') else (x if align == 'l' else x + bw - w)
    oy = y + (bh - h) / 2
    if align == 't': oy = y
    if align == 'b': oy = y + bh - h
    paste(dst, f, ox, oy, opacity)
    return ox, oy, w, h


def rect(dst, x, y, w, h, col, alpha=1.0, radius=0):
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = int(round(x)), int(round(y)), int(round(x + w)), int(round(y + h))
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    m = np.ones((y1 - y0, x1 - x0), np.float32)
    if radius > 0:
        yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
        cx = np.clip(xx, x + radius, x + w - radius); cy = np.clip(yy, y + radius, y + h - radius)
        m = np.clip(radius + 0.5 - np.hypot(xx - cx, yy - cy), 0, 1).astype(np.float32)
    a = (m * alpha)[..., None]
    _over(dst[y0:y1, x0:x1], np.asarray(col, np.float32), a)


def frame(dst, x, y, w, h, col, t, alpha=1.0):
    rect(dst, x, y, w, t, col, alpha); rect(dst, x, y + h - t, w, t, col, alpha)
    rect(dst, x, y, t, h, col, alpha); rect(dst, x + w - t, y, t, h, col, alpha)


# --------------------------------------------------------------- text (blf into an ImBuf)
_fonts = {}
def font(bold=True):
    k = FONT_B if bold else FONT_R
    if k not in _fonts:
        _fonts[k] = blf.load(k)
    return _fonts[k]


def text_img(text, px, col, bold=True):
    """Tightly cropped RGBA image of `text` rendered at `px` pixel size (supersampled x2)."""
    f = font(bold)
    ss = 2
    blf.size(f, px * ss)
    tw, th = blf.dimensions(f, text)
    W, H = int(tw + 8 * ss + 4), int(px * ss * 1.6 + 8)
    ib = imbuf.new((W, H))
    with blf.bind_imbuf(f, ib):
        blf.color(f, 1, 1, 1, 1)
        blf.position(f, 4 * ss, int(px * ss * 0.45), 0)
        blf.draw_buffer(f, text)
    tmp = WORK / '_text.png'
    imbuf.write(ib, filepath=str(tmp))
    a = load_png(tmp)
    m = np.clip(a[..., :3].max(axis=2) * a[..., 3], 0, 1)
    ys, xs = np.nonzero(m > 0.02)
    if len(xs) == 0:
        return np.zeros((1, 1, 4), np.float32)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = np.zeros(m.shape + (4,), np.float32); out[..., :3] = col; out[..., 3] = m
    return resize(out, out.shape[1] / ss, out.shape[0] / ss)


def text_line(dst, text, x, y, px, col, bold=True, maxw=None, align='l'):
    """Draw text with its top at y. Shrinks to maxw. Returns (w, h)."""
    t = text_img(text, px, col, bold)
    if maxw and t.shape[1] > maxw:
        t = resize(t, maxw, t.shape[0] * maxw / t.shape[1])
    ox = x if align == 'l' else (x - t.shape[1] / 2 if align == 'c' else x - t.shape[1])
    paste(dst, t, ox, y)
    return t.shape[1], t.shape[0]


def ean13(dst, x, y, w, h, digits, col=(0.05, 0.05, 0.05), bg=(1, 1, 1)):
    """EAN-13 style barcode (white label with bars and digits) in box x, y, w, h."""
    L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011']
    G = [''.join('1' if c == '0' else '0' for c in reversed(p)) for p in L]
    R = [''.join('1' if c == '0' else '0' for c in p) for p in L]
    par = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL']
    d = [int(c) for c in digits[:12]]
    s = sum(v * (3 if i % 2 else 1) for i, v in enumerate(d)); d.append((10 - s % 10) % 10)
    bits = '101' + ''.join((L if par[d[0]][i] == 'L' else G)[d[i + 1]] for i in range(6)) + '01010' + \
           ''.join(R[d[i + 7]] for i in range(6)) + '101'
    rect(dst, x, y, w, h, bg)
    mw = (w * 0.86) / len(bits); bx = x + w * 0.07
    bh = h * 0.72
    for i, b in enumerate(bits):
        if b == '1':
            rect(dst, bx + i * mw, y + h * 0.08, mw, bh, col)
    if h >= 28:
        t = ''.join(str(v) for v in d)
        text_line(dst, t[0] + ' ' + t[1:7] + ' ' + t[7:], x + w / 2, y + h * 0.80, max(6, h * 0.14), col, False,
                  maxw=w * 0.9, align='c')


def rotate_cw(img):
    return np.ascontiguousarray(np.rot90(img, -1))


def rotate_ccw(img):
    return np.ascontiguousarray(np.rot90(img, 1))


# =============================================================== model analysis
def face_info(lod, f):
    V = lod['vertices']
    P = [V[c[0]][:3] for c in f['corners']]
    a, b, c = P[0], P[1], P[2]
    u = [b[i] - a[i] for i in range(3)]; w = [c[i] - a[i] for i in range(3)]
    n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    ln = math.sqrt(sum(x * x for x in n)) or 1.0
    n = tuple(x / ln for x in n)
    cen = tuple(sum(p[i] for p in P) / len(P) for i in range(3))
    return P, n, cen


def lod_bounds(lod):
    used = sorted({c[0] for f in lod['faces'] for c in f['corners']})
    V = lod['vertices']
    return [(min(V[i][a] for i in used), max(V[i][a] for i in used)) for a in range(3)]


def front_orientation(m):
    """sign of du/dx and dv/dy on the textured front (file -Z) faces of LOD 1."""
    l = m.lod(1)
    zmin = lod_bounds(l)[2][0]
    xs, us, ys, vs = [], [], [], []
    for f in l['faces']:
        if f['texture'].startswith('#'):
            continue
        P = [l['vertices'][c[0]] for c in f['corners']]
        if max(p[2] for p in P) < zmin + 0.0005:
            for c in f['corners']:
                p = l['vertices'][c[0]]; xs.append(p[0]); us.append(c[2]); ys.append(p[1]); vs.append(c[3])
    bu = np.polyfit(xs, us, 1)[0]; bv = np.polyfit(ys, vs, 1)[0]
    return (1 if bu > 0 else -1), (1 if bv > 0 else -1)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


SIDES = {  # outward normal, image-up direction as seen from outside
    'front': ((0, 0, -1), (0, 1, 0)), 'back': ((0, 0, 1), (0, 1, 0)),
    'left': ((-1, 0, 0), (0, 1, 0)), 'right': ((1, 0, 0), (0, 1, 0)),
    'top': ((0, 1, 0), (0, 0, 1)), 'bottom': ((0, -1, 0), (0, 0, 1)),
}


def side_axes(side, sR):
    n, up = SIDES[side]
    r = tuple(sR * x for x in cross(n, up))
    return r, up


def classify(lod, f, bnd):
    P, n, cen = face_info(lod, f)
    k = max(range(3), key=lambda i: abs(n[i]))
    mid = (bnd[k][0] + bnd[k][1]) / 2
    s = 1 if cen[k] > mid else -1
    return {(0, -1): 'left', (0, 1): 'right', (1, -1): 'bottom', (1, 1): 'top', (2, -1): 'front', (2, 1): 'back'}[(k, s)]


def box_dims(m):
    b = lod_bounds(m.lod(1))
    return b[0][1] - b[0][0], b[1][1] - b[1][0], b[2][1] - b[2][0]


# =============================================================== box atlas layout
ATLAS = 1024
PAD = 12


def box_layout(W, H, D, sides):
    """Pixel rects for the requested sides.  Row 1: back | left | right, rows 2/3: top, bottom."""
    row1 = [s for s in ('back', 'left', 'right') if s in sides]
    row2 = [s for s in ('top', 'bottom') if s in sides]
    phys = {'back': (W, H), 'left': (D, H), 'right': (D, H), 'top': (W, D), 'bottom': (W, D), 'front': (W, H)}
    # try: A) top+bottom stacked under row1;  B) top+bottom side by side under row1;  C) one column
    best = None
    for mode in ('A', 'B'):
        if mode == 'A':
            wmm = max(sum(phys[s][0] for s in row1), max([phys[s][0] for s in row2] or [0]))
            hmm = max([phys[s][1] for s in row1] or [0]) + sum(phys[s][1] for s in row2)
            npx_w = PAD * (len(row1) + 1); npx_h = PAD * (1 + (1 if row1 else 0) + len(row2))
        else:
            wmm = max(sum(phys[s][0] for s in row1), sum(phys[s][0] for s in row2))
            hmm = max([phys[s][1] for s in row1] or [0]) + max([phys[s][1] for s in row2] or [0])
            npx_w = PAD * (max(len(row1), len(row2)) + 1); npx_h = PAD * (1 + (1 if row1 else 0) + (1 if row2 else 0))
        s = min((ATLAS - npx_w) / wmm, (ATLAS - npx_h) / hmm) * 0.995
        if best is None or s > best[0]:
            best = (s, mode)
    s, mode = best
    rects = {}
    x = PAD; y = PAD
    for sd in row1:
        w, h = phys[sd][0] * s, phys[sd][1] * s
        rects[sd] = (int(x), int(y), int(round(w)), int(round(h))); x += round(w) + PAD
    y = PAD + (int(round(max([phys[sd][1] for sd in row1] or [0]) * s)) + PAD if row1 else 0)
    x = PAD
    for sd in row2:
        w, h = phys[sd][0] * s, phys[sd][1] * s
        rects[sd] = (int(x), int(y), int(round(w)), int(round(h)))
        if mode == 'A':
            y += round(h) + PAD
        else:
            x += round(w) + PAD
    return rects, s


# =============================================================== panel designers (boxes)
def crop_front(theme, frac):
    """Crop of the front art; frac = (x0, y0, x1, y1) as fractions of the model's front rectangle."""
    a = texture_png(theme['_front_tex'])
    H, W = a.shape[:2]
    u0, u1, v0, v1 = theme['_front_rect']
    x0 = (u0 + (u1 - u0) * frac[0]) * W; x1 = (u0 + (u1 - u0) * frac[2]) * W
    y0 = (v0 + (v1 - v0) * frac[1]) * H; y1 = (v0 + (v1 - v0) * frac[3]) * H
    c = a[int(y0):int(math.ceil(y1)), int(x0):int(math.ceil(x1))].copy()
    c[..., 3] = 1
    fe = theme.get('feather', 0.1)
    if fe > 0:
        # soft edges so a crop of the (gradient) front art blends into the flat panel colour
        h, w = c.shape[:2]
        e = max(2.0, min(h, w) * fe)
        yy = np.minimum(np.arange(h) + 0.5, h - np.arange(h) - 0.5)[:, None]
        xx = np.minimum(np.arange(w) + 0.5, w - np.arange(w) - 0.5)[None, :]
        c[..., 3] = np.clip(np.minimum(yy, xx) / e, 0, 1) ** 1.5
    return c


def crop_tex(tex, px_rect):
    a = texture_png(tex)
    x0, y0, x1, y1 = px_rect
    c = a[y0:y1, x0:x1].copy(); c[..., 3] = 1
    return c


def sample_front(theme, fx, fy, r=0.02):
    a = texture_png(theme['_front_tex'])
    H, W = a.shape[:2]
    u0, u1, v0, v1 = theme['_front_rect']
    cx = (u0 + (u1 - u0) * fx) * W; cy = (v0 + (v1 - v0) * fy) * H
    rw = max(2, (u1 - u0) * W * r); rh = max(2, (v1 - v0) * H * r)
    p = a[int(cy - rh):int(cy + rh) + 1, int(cx - rw):int(cx + rw) + 1, :3].reshape(-1, 3)
    return np.median(p, axis=0)


def info_block(dst, x, y, w, h, lines, theme, px=None):
    """White rounded info panel with label: value lines."""
    ink = theme['ink']; acc = theme['accent']
    rect(dst, x, y, w, h, theme.get('info_bg', (1, 1, 1)), theme.get('info_alpha', 0.93), radius=min(w, h) * 0.04)
    n = len(lines)
    px = px or min(h / (n * 1.55 + 0.8), w / 22)
    lh = px * 1.5
    cy = y + (h - lh * n) / 2 + px * 0.15
    lab_w = w * 0.28
    for lab, val in lines:
        rect(dst, x + w * 0.035, cy + lh - px * 0.25, w * 0.93, max(1, px * 0.06), ink, 0.25)
        if lab:
            text_line(dst, lab, x + w * 0.05, cy, px * 0.82, acc, True, maxw=lab_w - w * 0.03)
            text_line(dst, val, x + lab_w + w * 0.02, cy, px * 0.82, ink, False, maxw=w - lab_w - w * 0.08)
        else:
            text_line(dst, val, x + w * 0.05, cy, px * 0.82, ink, False, maxw=w * 0.9)
        cy += lh


def draw_back(theme, w, h):
    c = canvas(w, h, theme['bg'])
    if theme.get('back_band'):
        col, frac = theme['back_band']
        rect(c, 0, 0, w, h * frac, col)
    logo = theme['logo_img']
    lines = theme['info']
    if w / h > 1.25:   # landscape: logo left, info right
        paste_fit(c, logo, w * 0.04, h * 0.08, w * 0.40, h * 0.62)
        text_line(c, theme['name_line'], w * 0.24, h * 0.74, h * 0.07, theme['ink'], True, maxw=w * 0.42, align='c')
        text_line(c, theme['weight'], w * 0.24, h * 0.85, h * 0.055, theme['ink'], False, maxw=w * 0.42, align='c')
        info_block(c, w * 0.48, h * 0.07, w * 0.49, h * 0.64, lines, theme)
        ean13(c, w * 0.72, h * 0.75, w * 0.25, h * 0.19, theme['barcode'])
        text_line(c, theme['maker'], w * 0.48, h * 0.78, h * 0.045, theme['ink'], False, maxw=w * 0.23)
        if theme.get('note'):
            text_line(c, theme['note'], w * 0.48, h * 0.86, h * 0.038, theme['ink'], False, maxw=w * 0.23)
    else:              # portrait: logo top, info middle, barcode bottom
        _, _, _, lh = paste_fit(c, logo, w * 0.06, h * 0.03, w * 0.88, h * 0.30, align='t')
        yy = h * 0.03 + lh + h * 0.015
        text_line(c, theme['name_line'], w / 2, yy, w * 0.07, theme.get('head_ink', theme['ink']), True,
                  maxw=w * 0.86, align='c')
        info_block(c, w * 0.06, h * 0.43, w * 0.88, h * 0.37, lines, theme)
        ean13(c, w * 0.52, h * 0.83, w * 0.42, h * 0.13, theme['barcode'])
        text_line(c, theme['maker'], w * 0.06, h * 0.845, w * 0.045, theme.get('head_ink', theme['ink']), False,
                  maxw=w * 0.42)
        if theme.get('note'):
            text_line(c, theme['note'], w * 0.06, h * 0.90, w * 0.036, theme.get('head_ink', theme['ink']), False,
                      maxw=w * 0.42)
    return c


def end_content(theme, w, h, which):
    """Landscape/square end panel content (w >= h*0.6 expected)."""
    c = canvas(w, h, theme.get('end_bg', theme['bg']))
    hi = theme.get('head_ink', theme['ink'])
    if theme.get('end_band'):
        col, frac = theme['end_band']
        rect(c, 0, h * (1 - frac), w, h * frac, col)
    img = theme.get('end_img', theme['logo_img'])
    if w >= h * 1.6:   # long strip (rotated end of a tall box)
        _, _, lw, _ = paste_fit(c, img, w * 0.03, h * 0.1, w * 0.40, h * 0.8, align='l')
        text_line(c, theme['short_name'], w * 0.03 + lw + w * 0.04, h * 0.18, h * 0.36, hi, True,
                  maxw=w * 0.95 - lw - w * 0.07)
        text_line(c, theme['weight'] if which == 'left' else theme['maker'], w * 0.03 + lw + w * 0.04, h * 0.62,
                  h * 0.2, hi, False, maxw=w * 0.95 - lw - w * 0.07)
    else:              # portrait-ish end
        _, _, _, lh = paste_fit(c, img, w * 0.08, h * 0.05, w * 0.84, h * 0.45, align='t')
        y = h * 0.05 + lh + h * 0.04
        _, th = text_line(c, theme['short_name'], w / 2, y, min(w * 0.2, h * 0.09), hi, True, maxw=w * 0.86, align='c')
        y += th + h * 0.04
        text_line(c, theme['weight'], w / 2, y, min(w * 0.11, h * 0.05), hi, False, maxw=w * 0.86, align='c')
        text_line(c, theme['maker'], w / 2, h * 0.9, min(w * 0.09, h * 0.04), hi, False, maxw=w * 0.86, align='c')
    return c


def draw_end(theme, w, h, which):
    if 'draw_end' in theme:
        return theme['draw_end'](theme, w, h, which)
    if h > 1.8 * w:   # tall narrow end: design landscape, rotate so it reads bottom-to-top
        return rotate_ccw(end_content(theme, h, w, which))
    return end_content(theme, w, h, which)


def draw_top(theme, w, h, which):
    if 'draw_top' in theme:
        return theme['draw_top'](theme, w, h, which)
    c = canvas(w, h, theme.get('top_bg', theme['bg']))
    hi = theme.get('head_ink', theme['ink'])
    if which == 'top':
        img = theme.get('top_img', theme['logo_img'])
        _, _, lw, _ = paste_fit(c, img, w * 0.03, h * 0.1, w * 0.45, h * 0.8, align='l')
        x = w * 0.03 + lw + w * 0.04
        text_line(c, theme['short_name'], x, h * 0.2, h * 0.34, hi, True, maxw=w * 0.95 - x)
        text_line(c, theme['maker'], x, h * 0.62, h * 0.18, hi, False, maxw=w * 0.95 - x)
    else:
        text_line(c, theme['short_name'] + '  ' + theme['weight'], w * 0.04, h * 0.14, h * 0.2, hi, True,
                  maxw=w * 0.55)
        text_line(c, theme.get('bottom_note', '제조일자 및 유통기한: 별도 표기일까지'), w * 0.04, h * 0.45, h * 0.15, hi,
                  False, maxw=w * 0.55)
        text_line(c, theme['maker'], w * 0.04, h * 0.7, h * 0.14, hi, False, maxw=w * 0.55)
        bw = min(w * 0.28, h * 1.5)
        ean13(c, w * 0.96 - bw, h * 0.2, bw, h * 0.6, theme['barcode'])
    return c


# =============================================================== box themes
STORE = '직사광선을 피하고 서늘하고 건조한 곳에 보관'


def tea(name, weight, ingr, accent, bgpt=(0.42, 0.06)):
    return dict(logo=(0.0, 0.02, 0.55, 0.62), bgpt=bgpt, ink=hexc('3f2616'), accent=hexc('c8242b'),
                head_ink=hexc('3f2616'), name_line='동서 ' + name, short_name=name, weight=weight,
                maker='동서식품(주)', note='소비자상담실 080-023-7111', barcode='880110700512',
                back_band=(accent, 0.035), end_band=(accent, 0.12),
                info=[('제품명', name), ('식품유형', '침출차'), ('내용량', weight), ('원재료명', ingr),
                      ('음용방법', '끓는 물에 티백 1개, 2~3분 우려 드세요'), ('보관방법', STORE)],
                remap={'back', 'left', 'right', 'top', 'bottom'})


def maxim(name, weight, logo, bgpt, accent):
    return dict(logo=logo, bgpt=bgpt, ink=hexc('3a1c0e'), accent=hexc('8a3b12'), head_ink=hexc('3a1c0e'),
                name_line='맥심 ' + name, short_name='맥심 ' + name, weight=weight, maker='동서식품(주)',
                note='소비자상담실 080-023-7111', barcode='880110704230', back_band=(accent, 0.035),
                end_band=(accent, 0.1),
                info=[('제품명', '맥심 ' + name + ' 커피믹스'), ('식품유형', '커피 (커피믹스)'), ('내용량', weight),
                      ('원재료명', '설탕, 식물성크림, 커피, 탈지분유'), ('섭취방법', '물 100 ml에 1개를 넣고 잘 저어 드세요'),
                      ('보관방법', STORE)],
                remap={'back', 'left', 'right', 'top', 'bottom'})


def pepero(kind, weight, kcal, bg_hex, logo, ink='ffffff', info_ink='3a1a10', acc='c8102e', **kw):
    t = dict(logo=logo, bg=hexc(bg_hex), ink=hexc(info_ink), accent=hexc(acc), head_ink=hexc(ink),
             name_line='빼빼로 ' + kind, short_name='빼빼로', weight='%s (%s)' % (weight, kcal),
             maker='롯데웰푸드(주)', note='고객상담실 080-024-4040', barcode='880106220041',
             info=[('제품명', '빼빼로 ' + kind), ('식품유형', '과자'), ('내용량', '%s (%s)' % (weight, kcal)),
                   ('원재료명', '밀가루, 설탕, 코코아매스, 식물성유지'), ('알레르기', '밀, 우유, 대두 함유'),
                   ('보관방법', STORE)],
             remap={'back', 'left', 'right', 'top', 'bottom'})
    t.update(kw)
    return t


THEMES = {
    'barleytea': tea('보리차', '300 g (10 g x 30티백)', '볶은보리 100%', hexc('e0a91c')),
    'corntea': tea('옥수수차', '300 g (10 g x 30티백)', '볶은옥수수 100%', hexc('f0be1a')),
    'solomonsealtea': tea('둥굴레차', '72 g (1.2 g x 60티백)', '볶은둥굴레 100%', hexc('e2831c'),
                          bgpt=(0.30, 0.9)),
    'cassiaseedtea': tea('결명자차', '144 g (4 g x 36티백)', '볶은결명자 100%', hexc('8fbf3a'),
                         bgpt=(0.30, 0.9)),
    'coffeemix': maxim('모카골드 마일드', '240 g (12 g x 20개)', (0.22, 0.04, 0.60, 0.56), (0.58, 0.05),
                       hexc('6b3413')),
    'whitegoldcoffee': maxim('화이트골드', '234 g (11.7 g x 20개)', (0.10, 0.08, 0.50, 0.86), (0.55, 0.9),
                             hexc('8a5a2b')),
    'pepero': pepero('오리지널', '54 g', '270 kcal', 'd9161f', (0.0, 0.0, 1.0, 0.5)),
    'peperoalmond': pepero('아몬드', '37 g', '205 kcal', '3f7b45', (0.0, 0.085, 1.0, 0.5), acc='3f7b45'),
    'peperochococookie': pepero('초코쿠키', '37 g', '180 kcal', '1f5eb4', (0.0, 0.0, 1.0, 0.47), acc='1f5eb4'),
    'peperochocofilled': pepero('초코필드', '53 g', '275 kcal', 'f5b100', (0.0, 0.0, 1.0, 0.46), acc='a0521d',
                                ink='3a1a10'),
    'peperocrunky': pepero('크런키', '39 g', '205 kcal', 'e5561d', (0.0, 0.0, 1.0, 0.58), acc='c63d12'),
    'peperowhitecookie': pepero('화이트쿠키', '37 g', '185 kcal', 'ebe8e1', (0.0, 0.1, 1.0, 0.45), ink='3b2a20',
                                acc='3b2a20', back_band=(hexc('3b2a20'), 0.03), end_band=(hexc('3b2a20'), 0.1)),
}


# ---- yanggaeng / chestnut / gosomi / ghana (keep front+back, new ends/top/bottom)
def _yang_end(theme, w, h, which):
    c = canvas(w, h, theme['end_bg'])
    frame(c, 0, 0, w, h, theme['frame'], max(2, w * 0.03))
    paste_fit(c, theme['end_img'], w * 0.12, h * 0.1, w * 0.76, h * 0.8)
    return c


def _yang_top(theme, w, h, which):
    c = canvas(w, h, theme['bg'])
    dark = theme['end_bg']
    rect(c, 0, 0, h * 1.1, h, dark)
    paste_fit(c, theme['end_img'], h * 0.1, h * 0.08, h * 0.9, h * 0.84)
    x = h * 1.1 + w * 0.03
    if which == 'top':
        text_line(c, theme['short_name'], x, h * 0.16, h * 0.5, theme['ink'], True, maxw=w * 0.45)
        text_line(c, theme['slogan'], w * 0.97, h * 0.3, h * 0.24, theme['accent'], True, maxw=w * 0.34, align='r')
    else:
        text_line(c, theme['short_name'] + ' ' + theme['weight'], x, h * 0.14, h * 0.28, theme['ink'], True,
                  maxw=w * 0.40)
        text_line(c, '제조: ' + theme['maker'], x, h * 0.56, h * 0.2, theme['ink'], False, maxw=w * 0.40)
        bw = min(w * 0.28, h * 2.4)
        ean13(c, w * 0.97 - bw, h * 0.1, bw, h * 0.8, theme['barcode'])
    return c


THEMES['yanggaeng'] = dict(
    bgpt=(0.55, 0.28), ink=hexc('1d1410'), accent=hexc('c8242b'), end_bg=hexc('3a2418'),
    end_img_frac=(0.08, 0.45, 0.26, 0.88), frame=hexc('c9a045'), short_name='연양갱', slogan='70년 전통의 맛 그대로!',
    weight='50 g', maker='해태제과식품(주)', barcode='880101902032',
    draw_end=_yang_end, draw_top=_yang_top, remap={'left', 'right', 'top', 'bottom'}, crop_key=None)
THEMES['chestnutyanggaeng'] = dict(
    bgpt=(0.5, 0.08), ink=hexc('3b1f12'), accent=hexc('7a3b17'), end_bg=hexc('f2c35a'),
    end_img_frac=(0.0, 0.1, 0.112, 0.92), frame=hexc('7a3b17'), short_name='밤양갱', slogan='CROWN 밤양갱',
    weight='50 g', maker='크라운제과(주)', barcode='880101210155',
    draw_end=_yang_end, draw_top=_yang_top, remap={'left', 'right', 'top', 'bottom'})


def _gosomi_end(theme, w, h, which):
    c = canvas(w, h, theme['bg'])
    ink = theme['ink']
    text_line(c, '한입한입 미소 가득', w / 2, h * 0.07, w * 0.09, ink, False, maxw=w * 0.8, align='c')
    text_line(c, '高笑美', w / 2, h * 0.11, w * 0.2, ink, True, maxw=w * 0.7, align='c')
    paste_fit(c, theme['end_img'], w * 0.12, h * 0.22, w * 0.76, h * 0.3)
    y = h * 0.56
    for t in ('얇고 바삭한 크래커 위에', '참깨를 솔솔 뿌려', '입 안에 고소함이 전해지는'):
        text_line(c, t, w / 2, y, w * 0.075, ink, False, maxw=w * 0.84, align='c'); y += h * 0.035
    rect(c, w * 0.3, y + h * 0.01, w * 0.4, max(1, h * 0.004), ink, 0.8)
    text_line(c, '고소한 크래커', w / 2, y + h * 0.03, w * 0.11, ink, True, maxw=w * 0.84, align='c')
    text_line(c, '고소미', w / 2, y + h * 0.075, w * 0.16, ink, True, maxw=w * 0.84, align='c')
    text_line(c, '(주)오리온', w / 2, h * 0.93, w * 0.08, ink, False, maxw=w * 0.84, align='c')
    return c


def _gosomi_top(theme, w, h, which):
    c = canvas(w, h, theme['bg'])
    ink = theme['ink']
    if which == 'top':
        text_line(c, '고소미', w / 2, h * 0.14, h * 0.34, ink, True, maxw=w * 0.8, align='c')
        text_line(c, '高笑美  고소한 크래커', w / 2, h * 0.6, h * 0.16, ink, False, maxw=w * 0.86, align='c')
    else:
        text_line(c, '고소미 70 g', w / 2, h * 0.08, h * 0.14, ink, True, maxw=w * 0.86, align='c')
        text_line(c, '유통기한: 별도 표기일까지', w / 2, h * 0.28, h * 0.11, ink, False, maxw=w * 0.86, align='c')
        ean13(c, w * 0.18, h * 0.46, w * 0.64, h * 0.46, theme['barcode'])
    return c


THEMES['gosomi'] = dict(bgpt=(0.9, 0.5), ink=hexc('3d2a12'), accent=hexc('3d2a12'), end_img_frac=(0.08, 0.02, 0.42, 0.2),
                        barcode='880111702011', draw_end=_gosomi_end, draw_top=_gosomi_top,
                        remap={'left', 'right', 'top', 'bottom'})


def _ghana_end(theme, w, h, which):
    # tall narrow (9 x 47 mm): design landscape, rotate
    L = canvas(h, w, theme['bg'])
    gold = theme['accent']
    rect(L, 0, w * 0.1, h, max(1, w * 0.05), gold); rect(L, 0, w * 0.85, h, max(1, w * 0.05), gold)
    text_line(L, 'Ghana', h / 2, w * 0.24, w * 0.5, gold, True, maxw=h * 0.8, align='c')
    return rotate_ccw(L)


def _ghana_top(theme, w, h, which):
    c = canvas(w, h, theme['bg'])
    gold = theme['accent']
    rect(c, 0, h * 0.08, w, max(1, h * 0.05), gold); rect(c, 0, h * 0.87, w, max(1, h * 0.05), gold)
    if which == 'top':
        text_line(c, 'LOTTE   Ghana   MILD CHOCOLATE', w / 2, h * 0.25, h * 0.5, gold, True, maxw=w * 0.9,
                  align='c')
    else:
        text_line(c, '가나마일드  70 g (360 kcal)   롯데웰푸드(주)   유통기한: 별도 표기일까지', w / 2, h * 0.3,
                  h * 0.4, gold, False, maxw=w * 0.92, align='c')
    return c


THEMES['ghanachocolate'] = dict(bgpt=(0.5, 0.95), ink=hexc('c9a24a'), accent=hexc('c9a24a'),
                                draw_end=_ghana_end, draw_top=_ghana_top, remap={'left', 'right', 'top', 'bottom'})


# ---- curry (Ottogi 3-minute curry, hot)
def _curry_end(theme, w, h, which):
    L = canvas(h, w, theme['bg'])       # landscape 173 x 22 mm
    W, H = h, w
    red = theme['accent']
    rect(L, 0, H * 0.82, W, H * 0.18, red)
    _, _, lw, _ = paste_fit(L, theme['end_img'], W * 0.02, H * 0.06, W * 0.2, H * 0.72, align='l')
    x = W * 0.02 + lw + W * 0.03
    tw, _ = text_line(L, '3분 카레', x, H * 0.12, H * 0.5, red, True, maxw=W * 0.35)
    text_line(L, '매운맛' if which == 'left' else 'OTTOGI CURRY (HOT)', x + tw + W * 0.03, H * 0.26, H * 0.3,
              theme['ink'], True, maxw=W * 0.95 - x - tw - W * 0.03)
    return rotate_ccw(L)


def _curry_top(theme, w, h, which):
    c = canvas(w, h, theme['bg'])
    red = theme['accent']
    rect(c, 0, h * 0.82, w, h * 0.18, red)
    if which == 'top':
        _, _, lw, _ = paste_fit(c, theme['end_img'], w * 0.03, h * 0.05, w * 0.25, h * 0.72, align='l')
        x = w * 0.03 + lw + w * 0.04
        text_line(c, '3분 카레 매운맛', x, h * 0.16, h * 0.44, red, True, maxw=w * 0.95 - x)
    else:
        text_line(c, '3분 카레 매운맛 200 g', w * 0.04, h * 0.1, h * 0.26, theme['ink'], True, maxw=w * 0.55)
        text_line(c, '(주)오뚜기   유통기한: 별도 표기일까지', w * 0.04, h * 0.46, h * 0.2, theme['ink'], False,
                  maxw=w * 0.55)
        bw = min(w * 0.3, h * 2.4)
        ean13(c, w * 0.96 - bw, h * 0.06, bw, h * 0.72, theme['barcode'])
    return c


THEMES['curry'] = dict(bgpt=(0.5, 0.45), bg=hexc('ffd92a'), ink=hexc('2a1a10'), accent=hexc('e3151f'),
                       end_img_frac=(0.04, 0.06, 0.36, 0.34), barcode='880102004131',
                       draw_end=_curry_end, draw_top=_curry_top, remap={'left', 'right', 'top', 'bottom'})


# ---- combat ration (kraft carton, military stencil-style print)
def kraft(w, h, base, seed):
    rng = np.random.default_rng(seed)
    c = canvas(w, h, base)
    n1 = resize(rng.normal(0, 1, (max(2, h // 90), max(2, w // 90), 1)).astype(np.float32), w, h)
    n2 = rng.normal(0, 1, (h, w, 1)).astype(np.float32)
    fib = box_blur(rng.normal(0, 1, (h, w, 1)).astype(np.float32), 5, 1)
    c[..., :3] *= 1 + 0.015 * n1 + 0.015 * n2 + 0.035 * fib
    return c


def _ration_back(theme, w, h):
    c = kraft(w, h, theme['bg'], 1)
    ink = theme['ink']
    ov = np.zeros((h, w, 4), np.float32)       # print layer (applied with slight transparency)
    paste_fit(ov, theme['emblem'], w * 0.3, h * 0.03, w * 0.4, h * 0.12)
    paste_fit(ov, theme['title'], w * 0.08, h * 0.16, w * 0.84, h * 0.08)
    y = h * 0.28
    text_line(ov, '조리 및 섭취 방법', w * 0.08, y, h * 0.03, ink, True); y += h * 0.05
    for t in ('1. 봉지 윗부분을 뜯어 발열제에 물을 붓는다.', '2. 주식 파우치를 넣고 10분간 데운다.',
              '3. 반찬 파우치는 그대로 또는 데워서 먹는다.', '4. 발열 중에는 봉지를 밀폐하지 말 것.'):
        text_line(ov, t, w * 0.08, y, h * 0.024, ink, False, maxw=w * 0.84); y += h * 0.04
    y += h * 0.02
    frame(ov, w * 0.08, y, w * 0.84, h * 0.22, ink, max(2, h * 0.003))
    yy = y + h * 0.02
    for t in ('보관방법: 직사광선을 피하고 서늘한 곳에 보관', '취급주의: 던지거나 떨어뜨리지 마십시오',
              '유통기한: 제조일로부터 36개월', '사용부대: 대한민국 국군'):
        text_line(ov, t, w * 0.11, yy, h * 0.024, ink, False, maxw=w * 0.78); yy += h * 0.05
    text_line(ov, '제조연월일 :', w * 0.08, h * 0.80, h * 0.028, ink, True, maxw=w * 0.3)
    rect(ov, w * 0.44, h * 0.795, w * 0.34, h * 0.045, ink)
    paste_fit(ov, theme['maker_img'], w * 0.15, h * 0.88, w * 0.7, h * 0.08)
    paste(c, ov, 0, 0, 0.88)
    return c


def _ration_end(theme, w, h, which):
    c = kraft(w, h, theme['bg'], 2 if which == 'left' else 3)
    ink = theme['ink']
    ov = np.zeros((h, w, 4), np.float32)
    paste_fit(ov, theme['emblem'], w * 0.2, h * 0.05, w * 0.6, h * 0.16)
    paste_fit(ov, theme['title'], w * 0.06, h * 0.26, w * 0.88, h * 0.12)
    frame(ov, w * 0.1, h * 0.46, w * 0.8, h * 0.22, ink, max(2, w * 0.012))
    text_line(ov, '1 식분', w / 2, h * 0.5, w * 0.1, ink, True, align='c')
    text_line(ov, '1 MEAL / 1 인분', w / 2, h * 0.6, w * 0.055, ink, False, maxw=w * 0.7, align='c')
    text_line(ov, '↑ 이 면을 위로', w / 2, h * 0.76, w * 0.07, ink, True, maxw=w * 0.8, align='c')
    paste_fit(ov, theme['maker_img'], w * 0.1, h * 0.87, w * 0.8, h * 0.08)
    paste(c, ov, 0, 0, 0.88)
    return c


def _ration_top(theme, w, h, which):
    c = kraft(w, h, theme['bg'], 4 if which == 'top' else 5)
    ink = theme['ink']
    ov = np.zeros((h, w, 4), np.float32)
    if which == 'top':
        paste_fit(ov, theme['emblem'], w * 0.04, h * 0.1, w * 0.22, h * 0.8)
        paste_fit(ov, theme['title'], w * 0.3, h * 0.14, w * 0.66, h * 0.3)
        text_line(ov, '취급주의  ·  습기주의', w * 0.63, h * 0.6, h * 0.12, ink, True, maxw=w * 0.64, align='c')
    else:
        text_line(ov, '식량, 전투용 I 형  1 식분', w * 0.06, h * 0.12, h * 0.12, ink, True, maxw=w * 0.88)
        text_line(ov, '제조연월일 :', w * 0.06, h * 0.42, h * 0.1, ink, False, maxw=w * 0.24)
        rect(ov, w * 0.32, h * 0.4, w * 0.28, h * 0.14, ink)
        text_line(ov, '유 통 기 한 :', w * 0.06, h * 0.62, h * 0.1, ink, False, maxw=w * 0.24)
        rect(ov, w * 0.32, h * 0.6, w * 0.28, h * 0.14, ink)
        paste_fit(ov, theme['maker_img'], w * 0.62, h * 0.4, w * 0.34, h * 0.34)
    paste(c, ov, 0, 0, 0.88)
    return c


def _ration_setup(theme):
    tex = theme['_front_tex']
    # the front panel of the ration-label atlas; print elements as ink-keyed crops
    def ink_crop(frac):
        c = crop_front(dict(theme, feather=0), frac)
        lum = c[..., :3].mean(axis=2)
        c[..., 3] = np.clip((0.5 - lum) / 0.2, 0, 1)
        c[..., :3] = theme['ink']
        return c
    theme['emblem'] = ink_crop((0.28, 0.02, 0.72, 0.27))
    theme['title'] = text_img('식량, 전투용 Ⅰ형', 96, theme['ink'], True)
    theme['maker_img'] = ink_crop((0.20, 0.86, 0.85, 0.99))


THEMES['combatration'] = dict(bgpt=(0.06, 0.5), ink=hexc('241a12'), accent=hexc('241a12'), setup=_ration_setup,
                              draw_back=_ration_back, draw_end=_ration_end, draw_top=_ration_top,
                              remap={'back', 'left', 'right', 'top', 'bottom'})

BOXES = list(THEMES)


# =============================================================== box fix
def front_rect(m):
    l = m.lod(1)
    zmin = lod_bounds(l)[2][0]
    r = {}
    for f in l['faces']:
        P = [l['vertices'][c[0]] for c in f['corners']]
        if f['texture'].startswith('#') or max(p[2] for p in P) >= zmin + 0.0005:
            continue
        q = r.setdefault(f['texture'], [9, -9, 9, -9])
        for c in f['corners']:
            q[0] = min(q[0], c[2]); q[1] = max(q[1], c[2]); q[2] = min(q[2], c[3]); q[3] = max(q[3], c[3])
    (tex, q), = r.items()
    return tex, q


def build_box_texture(name, m, theme):
    W, H, D = box_dims(m)
    tex, q = front_rect(m)
    theme['_front_tex'] = tex; theme['_front_rect'] = q
    theme['_bg_sampled'] = sample_front(theme, *theme.get('bgpt', (0.5, 0.5)))
    theme.setdefault('bg', theme['_bg_sampled'])
    if 'setup' in theme:
        theme['setup'](theme)
    if 'logo' in theme:
        theme['logo_img'] = crop_front(theme, theme['logo'])
    if 'end_img_frac' in theme:
        theme['end_img'] = crop_front(theme, theme['end_img_frac'])
    remap = theme['remap']
    rects, scale = box_layout(W * 1000, H * 1000, D * 1000, remap)
    atlas = canvas(ATLAS, ATLAS, theme['bg'])
    for side, (x, y, w, h) in rects.items():
        if side == 'back':
            art = theme['draw_back'](theme, w, h) if 'draw_back' in theme else draw_back(theme, w, h)
        elif side in ('left', 'right'):
            art = draw_end(theme, w, h, side)
        else:
            art = draw_top(theme, w, h, side)
        art = art[:h, :w]
        # bleed: replicate edge pixels into the padding
        b = PAD // 2
        big = np.pad(art, ((b, b), (b, b), (0, 0)), mode='edge')
        atlas[y - b:y + h + b, x - b:x + w + b] = big
    return atlas, rects


def remap_box(m, rects, newtex, sR, sV):
    counts = {}
    for lod in m.visual_lods():
        bnd = lod_bounds(lod)
        for side in rects:
            r, up = side_axes(side, sR)
            faces = [f for f in lod['faces'] if classify(lod, f, bnd) == side]
            if not faces:
                continue
            pts = [lod['vertices'][c[0]][:3] for f in faces for c in f['corners']]
            rs = [dot(p, r) for p in pts]; us = [dot(p, up) for p in pts]
            r0, r1, u0, u1 = min(rs), max(rs), min(us), max(us)
            x, y, w, h = rects[side]
            for f in faces:
                nc = []
                for vi, ni, _, _ in f['corners']:
                    p = lod['vertices'][vi][:3]
                    px = x + (dot(p, r) - r0) / (r1 - r0) * w
                    py = y + (u1 - dot(p, up)) / (u1 - u0) * h        # image row (top-down)
                    v = py / ATLAS if sV < 0 else 1 - py / ATLAS
                    nc.append((vi, ni, px / ATLAS, v))
                f['corners'] = nc
                f['texture'] = newtex
            counts[(lod['resolution'], side)] = len(faces)
    return counts


# =============================================================== milk bottles
MILK = {
    'bananamilk': dict(ink_lo=0.08, ink_hi=0.20, k=1.2),
    'strawberrymilk': dict(ink_lo=0.08, ink_hi=0.20, k=1.2),
    'melonamilk': dict(ink_lo=0.08, ink_hi=0.20, k=1.2),
}
BAND = (0.0842, 0.1232)
STRIP_W, STRIP_H = 1024, 256
SEAM = -math.pi / 2          # strip u=0 at this angle (a blank side of the bottle)


def milk_band_faces(lod):
    out = []
    for f in lod['faces']:
        P, n, cen = face_info(lod, f)
        ys = [p[1] for p in P]
        if min(ys) >= BAND[0] - 1e-4 and max(ys) <= BAND[1] + 1e-4 and max(ys) - min(ys) > 0.02 \
                and math.hypot(cen[0], cen[2]) > 0.02 and abs(n[1]) < 0.7:
            out.append(f)
    return out


def milk_geometry(m):
    l = m.lod(1)
    faces = milk_band_faces(l)
    label = [f for f in faces if not f['texture'].startswith('#')]
    plastic = [f for f in faces if f['texture'].startswith('#')]
    xs, us, ys, vs = [], [], [], []
    for f in label:
        for vi, ni, u, v in f['corners']:
            p = l['vertices'][vi]; xs.append(p[0]); us.append(u); ys.append(p[1]); vs.append(v)
    a_u = np.polyfit(xs, us, 1); a_v = np.polyfit(ys, vs, 1)
    rb = [math.hypot(l['vertices'][c[0]][0], l['vertices'][c[0]][2]) for f in faces for c in f['corners']
          if abs(l['vertices'][c[0]][1] - BAND[0]) < 1e-4]
    rt = [math.hypot(l['vertices'][c[0]][0], l['vertices'][c[0]][2]) for f in faces for c in f['corners']
          if abs(l['vertices'][c[0]][1] - BAND[1]) < 1e-4]
    return dict(label_tex=label[0]['texture'], material=label[0]['material'], plastic=plastic[0]['texture'],
                a_u=a_u, a_v=a_v, r_bot=float(np.mean(rb)), r_top=float(np.mean(rt)), n_faces=len(faces))


def plastic_rgb(tex):
    import re
    v = [float(x) for x in re.search(r'color\(([^)]*)\)', tex).group(1).split(',')[:3]]
    return np.array(v, np.float32)


def build_milk_texture(name, g, cfg):
    photo = texture_png(g['label_tex'])
    PH, PW = photo.shape[:2]
    body = plastic_rgb(g['plastic'])
    sR = 1 if g['a_u'][0] > 0 else -1
    # strip coords
    us = (np.arange(STRIP_W) + 0.5) / STRIP_W
    vs = (np.arange(STRIP_H) + 0.5) / STRIP_H
    theta = SEAM + us * 2 * math.pi                         # angle from the front (-Z), + toward viewer's right
    y = BAND[1] - vs * (BAND[1] - BAND[0])                  # strip row 0 = top of band
    r = g['r_bot'] + (y - BAND[0]) / (BAND[1] - BAND[0]) * (g['r_top'] - g['r_bot'])
    TH, RR = np.meshgrid(theta, r)
    _, YY = np.meshgrid(theta, y)

    def unwrap(center):
        t = (TH - center + math.pi) % (2 * math.pi) - math.pi
        # file x of the surface point seen from the front.  The photographed bottle is a little wider
        # (relative to its print) than the model's cone, so the photo silhouette radius is k * r.
        x = sR * RR * cfg['k'] * np.sin(t)
        pu = (g['a_u'][0] * x + g['a_u'][1]) * PW - 0.5
        pv = (g['a_v'][0] * YY + g['a_v'][1]) * PH - 0.5
        img = sample(photo, pu, pv)
        valid = np.clip((math.radians(84) - np.abs(t)) / math.radians(6), 0, 1)
        return img, valid

    img, valid = unwrap(0.0)
    # local photo background: blockwise median of the label region, smoothed
    bgimg = img[..., :3].copy()
    bs = 24
    bgest = np.zeros_like(bgimg)
    for yb in range(0, STRIP_H, bs):
        for xb in range(0, STRIP_W, bs):
            blk = bgimg[max(0, yb - bs):yb + 2 * bs, max(0, xb - bs):xb + 2 * bs].reshape(-1, 3)
            bgest[yb:yb + bs, xb:xb + bs] = np.median(blk, axis=0)
    bgest = box_blur(box_blur(bgest, bs, 0), bs, 1)
    # printed ink = pixels darker than the local background in some channel (white highlights /
    # the photo's pale label background are dropped, so the print sits on the bottle's own colour)
    d = np.sqrt((np.maximum(bgest - bgimg, 0) ** 2).sum(axis=2))
    alpha = np.clip((d - cfg['ink_lo']) / (cfg['ink_hi'] - cfg['ink_lo']), 0, 1) * valid
    ink = np.zeros((STRIP_H, STRIP_W, 4), np.float32); ink[..., :3] = bgimg; ink[..., 3] = alpha
    strip = canvas(STRIP_W, STRIP_H, body)
    paste(strip, ink, 0, 0)
    # the same print on the back
    shift = STRIP_W // 2
    paste(strip, np.roll(ink, shift, axis=1), 0, 0)
    return strip


def remap_milk(m, g, newtex):
    sR = 1 if g['a_u'][0] > 0 else -1
    n = 0
    for lod in m.visual_lods():
        for f in milk_band_faces(lod):
            P, _, cen = face_info(lod, f)
            tc = math.atan2(sR * cen[0], -cen[2])
            nc = []
            for (vi, ni, _, _), p in zip(f['corners'], P):
                t = math.atan2(sR * p[0], -p[2])
                t = tc + ((t - tc + math.pi) % (2 * math.pi) - math.pi)   # unwrap near the face centre
                tcen = (tc - SEAM) % (2 * math.pi)
                u = (tcen + (t - tc)) / (2 * math.pi)
                v = (BAND[1] - p[1]) / (BAND[1] - BAND[0])
                nc.append((vi, ni, u, min(max(v, 0.002), 0.998)))
            f['corners'] = nc
            f['texture'] = newtex
            f['material'] = g['material']
            n += 1
    return n


# =============================================================== yukgaejang bowl sleeve
BOWL = ['yukgaejangbowl', 'yukgaejangbowl_open']
SLEEVE = (0.004, 0.063)
LID_TEX = TEXPFX + 'r043_yukgaejangbowl_lid_bowl_b2f2874_co.paa'


def bowl_faces(lod):
    out = []
    for f in lod['faces']:
        P, n, cen = face_info(lod, f)
        r = math.hypot(cen[0], cen[2])
        radial = (n[0] * cen[0] + n[2] * cen[2]) / (r or 1)
        if SLEEVE[0] - 1e-4 <= min(p[1] for p in P) and max(p[1] for p in P) <= SLEEVE[1] + 1e-4 \
                and r >= 0.0585 and abs(n[1]) < 0.45 and radial < 0.5 and f['texture'].startswith('#'):
            out.append(f)
    return out


def build_sleeve():
    """Design in physical proportion (377 x 59 mm around r=0.06), store 2048 x 512."""
    Wd, Hd = 2048, 320
    mmy = Hd / ((SLEEVE[1] - SLEEVE[0]) * 1000)            # px per mm vertically
    c = canvas(Wd, Hd, (0.97, 0.97, 0.96))
    y_split = int(round((SLEEVE[1] - 0.0472) * 1000 * mmy))  # upper smooth band / lower ribbed wall
    lower_h = Hd - y_split
    panel = crop_tex(LID_TEX, (150, 296, 800, 500))
    # the lid's Nongshim logo pokes into the top-left corner of this crop: cover it with the food
    # photo just below it (mirrored), so the panel is food | diagonal | purple title only
    cov = 26
    panel[:cov, :185] = panel[cov:2 * cov, :185][::-1]
    panel = panel[:, :]
    # Nongshim-style mark: red disc with a white wave + wordmark
    logo = np.zeros((120, 330, 4), np.float32)
    yy, xx = np.mgrid[0:120, 0:120] + 0.5
    disc = np.clip(52 - np.hypot(xx - 60, yy - 60), 0, 1)
    wave = np.clip(9 - np.abs(yy - 60 - 10 * np.sin((xx - 60) / 16)), 0, 1) * (np.abs(xx - 60) < 44)
    logo[:, :120, :3] = np.where(wave[..., None] > 0.5, 1.0, hexc('e1261c'))
    logo[:, :120, 3] = disc
    wm = text_img('농심', 80, hexc('e1261c'), True)
    paste(logo, fit(wm, 200, 96), 128, 60 - fit(wm, 200, 96).shape[0] / 2)
    red = hexc('d7261e'); purple = hexc('3b2a78'); green = hexc('1f8a3c'); dark = hexc('2a2a2a')
    half = Wd // 2
    for k in range(2):
        x0 = k * half
        # main panel: food photo | diagonal | purple title (from the lid)
        ph = lower_h - 8
        f = fit(panel, 10000, ph)
        paste(c, f, x0 + 40, y_split + 4)
        # logo / info block on white
        bx = x0 + 40 + f.shape[1] + 30
        bw = half - (bx - x0) - 30
        paste_fit(c, logo, bx, y_split + 14, bw, lower_h * 0.36)
        text_line(c, '육개장 사발면', bx + bw / 2, y_split + lower_h * 0.47, lower_h * 0.13, red, True, maxw=bw,
                  align='c')
        text_line(c, '86 g (375 kcal)', bx + bw / 2, y_split + lower_h * 0.66, lower_h * 0.08, dark, False,
                  maxw=bw, align='c')
        rect(c, bx, y_split + lower_h * 0.80, bw, lower_h * 0.12, green, radius=6)
        text_line(c, '뜨거운 물 붓고 3분', bx + bw / 2, y_split + lower_h * 0.815, lower_h * 0.075,
                  (1, 1, 1), True, maxw=bw * 0.9, align='c')
        # upper band: red rule + repeated line of small print (compressed 1/1.12: larger radius there)
        rect(c, x0, y_split - 5, half, 4, red)
        t = text_img('농심  육개장 사발면  ·  한국인의 맛  ·  뜨거운 물을 표시선까지 붓고 3분 후 드세요', y_split * 0.36, dark,
                     False)
        t = resize(t, t.shape[1] / 1.12, t.shape[0])
        t = fit(t, half - 60, y_split * 0.5)
        paste(c, t, x0 + (half - t.shape[1]) / 2, (y_split - t.shape[0]) / 2 - 2)
    rect(c, 0, Hd - 3, Wd, 3, purple)
    return resize(c, 2048, 512)


def remap_bowl(m, newtex, material):
    n = 0
    for lod in m.visual_lods():
        for f in bowl_faces(lod):
            P, _, cen = face_info(lod, f)
            tc = math.atan2(cen[0], -cen[2])
            nc = []
            for (vi, ni, _, _), p in zip(f['corners'], P):
                t = math.atan2(p[0], -p[2])
                t = tc + ((t - tc + math.pi) % (2 * math.pi) - math.pi)
                u = ((tc + math.pi / 2) % (2 * math.pi) + (t - tc)) / (2 * math.pi)
                v = (SLEEVE[1] - p[1]) / (SLEEVE[1] - SLEEVE[0])
                nc.append((vi, ni, u, min(max(v, 0.002), 0.998)))
            f['corners'] = nc
            f['texture'] = newtex
            if material:
                f['material'] = material
            n += 1
    return n


# =============================================================== driver
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_texture(arr, stem):
    TEXOUT.mkdir(parents=True, exist_ok=True)
    png = TEXOUT / (stem + '.png')
    save_png(arr, png)
    paa = DATA / (stem + '.paa')
    subprocess.run([IMAGETOPAA, str(png), str(paa)], check=True, stdout=subprocess.DEVNULL)
    assert paa.exists() and paa.stat().st_size > 0
    return png, paa


def backup(name):
    ORIG.mkdir(parents=True, exist_ok=True)
    b = ORIG / (name + '.p3d')
    if not b.exists():
        shutil.copy2(SRC / (name + '.p3d'), b)
    return b


def verify(orig, new_path, changed_tex):
    a, b = mf.load(orig), mf.load(new_path)
    for la, lb in zip(a.lods, b.lods):
        assert la['vertices'] == lb['vertices'] and la['normals'] == lb['normals']
        assert len(la['faces']) == len(lb['faces'])
        for fa, fb in zip(la['faces'], lb['faces']):
            assert [c[:2] for c in fa['corners']] == [c[:2] for c in fb['corners']]
            if fb['texture'] != changed_tex:
                assert fa['corners'] == fb['corners'] and fa['texture'] == fb['texture'] and fa['material'] == fb['material']
            else:
                assert all(-0.001 <= c[3] <= 1.001 for c in fb['corners'])
        assert [(t['name'], t['data']) for t in la['tags'] if not t['name'].startswith('#UVSet')] == \
               [(t['name'], t['data']) for t in lb['tags'] if not t['name'].startswith('#UVSet')]
    assert a.memory_points() == b.memory_points()


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    report = []
    todo = BOXES + list(MILK) + BOWL
    if ONLY:
        todo = [n for n in todo if n in ONLY]
    sleeve_tex = None
    for name in todo:
        orig = backup(name)
        m = mf.load(orig)
        stem = 'r049_pack_' + name + '_co'
        newtex = TEXPFX + stem + '.paa'
        entry = dict(model=name, original_sha256=sha(orig))
        if name in THEMES:
            theme = dict(THEMES[name])
            sR, sV = front_orientation(m)
            atlas, rects = build_box_texture(name, m, theme)
            png, paa = write_texture(atlas, stem)
            counts = remap_box(m, rects, newtex, sR, sV)
            entry.update(kind='box', sides=sorted(rects), rects=rects, faces=sum(counts.values()),
                         dims_mm=[round(x * 1000, 1) for x in box_dims(m)])
        elif name in MILK:
            g = milk_geometry(m)
            strip = build_milk_texture(name, g, MILK[name])
            png, paa = write_texture(strip, stem)
            n = remap_milk(m, g, newtex)
            entry.update(kind='bottle', faces=n, r_bot=g['r_bot'], r_top=g['r_top'])
        else:
            stem = 'r049_pack_yukgaejangbowl_sleeve_co'
            newtex = TEXPFX + stem + '.paa'
            if sleeve_tex is None:
                sleeve_tex = write_texture(build_sleeve(), stem)
            png, paa = sleeve_tex
            n = remap_bowl(m, newtex, None)
            entry.update(kind='bowl', faces=n)
        entry.update(texture=newtex, png=str(png.relative_to(REPO)), paa=str(paa.relative_to(REPO)))
        if not NO_P3D:
            target = SRC / (name + '.p3d')
            entry['fixed_sha256'] = m.save(target)
            verify(orig, target, newtex)
            entry['bounds_unchanged'] = mf.Model.bounds(mf.load(target).lod(1)) == mf.Model.bounds(mf.load(orig).lod(1))
        print('%-20s %-6s faces=%s  %s' % (name, entry['kind'], entry['faces'], newtex))
        report.append(entry)
    out = TOOLS / 'reports'; out.mkdir(exist_ok=True)
    rp = out / ('fix_packaging.json' if not ONLY else 'fix_packaging_partial.json')
    rp.write_text(json.dumps(report, indent=1, default=str), encoding='utf8')
    print('OK', len(report), 'models; report', rp)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
