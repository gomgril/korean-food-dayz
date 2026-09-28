"""labelkit - shared helpers for the 0.4.9 label/texture fixes (fix_labels_*.py).

Runs INSIDE Blender (bpy + numpy), headless:
    blender.exe -b --factory-startup --python tools/models/fixes/fix_labels_xxx.py

Images are numpy float32 arrays, shape (H, W, 4), rows top-down, values = stored 8-bit
sRGB values / 255 (no colour management). p3d UVs: u -> column (u*W), v -> row from the
TOP (v*H); this is how render_review.py and the game read them.

Main pieces
- paths / backup of original models (tools/models/originals/<Addon>/models)
- texture IO: p3d texture path -> PNG (ImageToPAA), PNG -> PAA
- rebake(): re-projects existing label faces into a new unrolled texture layout
- seam_band(): replaces a band of columns with a per-row colour blend (clean seam)
- small 2D drawing helpers (resize, paste, polygons, text via blf with a Windows font)
"""
import os, sys, math, shutil, subprocess, hashlib, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import modelfix as mf  # noqa: E402

WORK = TOOLS / 'work' / 'labels'
TEXSRC = TOOLS / 'textures'
IMAGETOPAA = os.environ.get('KF_IMAGETOPAA',
                            r"C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe")
FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
OLD_PROJECT = os.environ.get('KF_OLD_PROJECT', str(REPO.parent / '2026-09-24' / 'lake-dayz-actionfishingnew-modded-x20'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ models
def model_paths(addon, name):
    target = REPO / 'source' / addon / 'models' / (name + '.p3d')
    orig = TOOLS / 'originals' / addon / 'models' / (name + '.p3d')
    if not orig.exists():
        orig.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, orig)
    return orig, target


def load_original(addon, name):
    orig, target = model_paths(addon, name)
    return mf.load(orig), target


def corners_xyz(lod, face):
    return [lod['vertices'][c[0]][:3] for c in face['corners']]


def face_normal(lod, face):
    P = corners_xyz(lod, face)
    n = np.zeros(3)
    for i in range(len(P)):  # Newell
        a, b = np.array(P[i]), np.array(P[(i + 1) % len(P)])
        n += np.cross(a, b)
    le = np.linalg.norm(n)
    return n / le if le else n


# ------------------------------------------------------------------ image IO (bpy)
def load_png(path):
    import bpy
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return np.ascontiguousarray(a.reshape(h, w, 4)[::-1])


def save_png(arr, path):
    import bpy
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.clip(arr, 0, 1).astype(np.float32)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones(arr.shape[:2] + (1,), np.float32)], 2)
    h, w = arr.shape[:2]
    img = bpy.data.images.new('kf_out', w, h, alpha=True)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel())
    img.filepath_raw = str(path); img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def tex_png(texture):
    """p3d texture path (e.g. KF_Pantry\\data\\x_co.paa) -> cached PNG of the source PAA."""
    rel = texture.strip().lstrip('\\/').replace('/', '\\')
    paa = REPO / 'source' / rel
    out = WORK / 'texcache' / (rel.replace('\\', '__').rsplit('.', 1)[0] + '.png')
    if not out.exists() or out.stat().st_mtime < paa.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([IMAGETOPAA, str(paa), str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert out.exists(), paa
    return out


def load_tex(texture):
    return load_png(tex_png(texture))


def old_ref(rel):
    """PNG from the old project (read-only), e.g. 'work/kf-product-review/references/Perilla/mild_side.png'."""
    return load_png(Path(OLD_PROJECT) / rel)


def publish(arr, topic, name, addon='KF_Pantry'):
    """Write PNG source + PAA. Returns the p3d texture path (Addon\\data\\r049_<topic>_<name>_co.paa)."""
    png = TEXSRC / topic / ('r049_%s_%s_co.png' % (topic, name))
    a = arr.copy(); a[..., 3] = 1.0          # labels are opaque -> DXT1
    save_png(a, png)
    paa = REPO / 'source' / addon / 'data' / ('r049_%s_%s_co.paa' % (topic, name))
    subprocess.run([IMAGETOPAA, str(png), str(paa)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert paa.exists() and paa.stat().st_mtime >= png.stat().st_mtime - 5, paa
    return '%s\\data\\%s' % (addon, paa.name)


# ------------------------------------------------------------------ 2D helpers
def sample(img, u, v, wrap=False):
    """Bilinear sample at normalized (u, v) (v from top). u, v: arrays. Returns (..., C)."""
    h, w = img.shape[:2]
    x = np.asarray(u) * w - 0.5; y = np.asarray(v) * h - 0.5
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[..., None]; fy = (y - y0)[..., None]
    def gx(i):
        return np.mod(i, w) if wrap else np.clip(i, 0, w - 1)
    x1 = gx(x0 + 1); x0 = gx(x0)
    y1 = np.clip(y0 + 1, 0, h - 1); y0 = np.clip(y0, 0, h - 1)
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy)
            + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def resize(img, w, h):
    """Area-aware resize (box pre-filter when shrinking, then bilinear)."""
    H, W = img.shape[:2]
    a = img
    fx, fy = max(1, int(W // w)), max(1, int(H // h))
    if fx > 1 or fy > 1:
        H2, W2 = (H // fy) * fy, (W // fx) * fx
        a = a[:H2, :W2].reshape(H2 // fy, fy, W2 // fx, fx, -1).mean(axis=(1, 3))
    u = (np.arange(w) + 0.5) / w; v = (np.arange(h) + 0.5) / h
    U, V = np.meshgrid(u, v)
    return sample(a, U, V).astype(np.float32)


def crop(img, u0, v0, u1, v1):
    h, w = img.shape[:2]
    return img[int(round(v0 * h)):int(round(v1 * h)), int(round(u0 * w)):int(round(u1 * w))].copy()


def paste(dst, src, x, y, alpha=None):
    """Alpha-composite src (H,W,4) onto dst at pixel (x, y) (top-left). alpha: extra mask (H,W)."""
    h, w = src.shape[:2]
    X0, Y0 = max(0, x), max(0, y); X1, Y1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if X1 <= X0 or Y1 <= Y0:
        return dst
    s = src[Y0 - y:Y1 - y, X0 - x:X1 - x]
    a = s[..., 3:4] if alpha is None else (s[..., 3] * alpha[Y0 - y:Y1 - y, X0 - x:X1 - x])[..., None]
    dst[Y0:Y1, X0:X1, :3] = dst[Y0:Y1, X0:X1, :3] * (1 - a) + s[..., :3] * a
    return dst


def fill(h, w, rgb):
    a = np.ones((h, w, 4), np.float32); a[..., :3] = rgb
    return a


def poly_mask(h, w, pts, ss=3):
    """Anti-aliased polygon mask. pts in pixel coords (x, y)."""
    pts = np.asarray(pts, float)
    ys, xs = (np.arange(h * ss) + 0.5) / ss, (np.arange(w * ss) + 0.5) / ss
    X, Y = np.meshgrid(xs, ys)
    inside = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        cond = ((y1 > Y) != (y2 > Y))
        xint = (x2 - x1) * (Y - y1) / ((y2 - y1) if y2 != y1 else 1e-12) + x1
        inside ^= cond & (X < xint)
    return inside.reshape(h, ss, w, ss).mean(axis=(1, 3)).astype(np.float32)


def star_points(cx, cy, r_out, r_in, rot_deg=-90, n=5):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot_deg + i * 180.0 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def rounded_rect_mask(h, w, x0, y0, x1, y1, r, ss=3):
    ys, xs = (np.arange(h * ss) + 0.5) / ss, (np.arange(w * ss) + 0.5) / ss
    X, Y = np.meshgrid(xs, ys)
    cx = np.clip(X, x0 + r, x1 - r); cy = np.clip(Y, y0 + r, y1 - r)
    m = ((X - cx) ** 2 + (Y - cy) ** 2 <= r * r) & (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    return m.reshape(h, ss, w, ss).mean(axis=(1, 3)).astype(np.float32)


def blur(img, r):
    """Separable box blur x3 (~gaussian), radius r pixels, edge clamp."""
    a = img.astype(np.float32)
    for _ in range(3):
        for ax in (0, 1):
            pad = [(0, 0)] * a.ndim; pad[ax] = (r, r)
            p = np.pad(a, pad, mode='edge')
            c = np.cumsum(p, axis=ax, dtype=np.float64)
            c = np.concatenate([np.zeros_like(np.take(c, [0], axis=ax)), c], axis=ax)
            n = a.shape[ax]
            a = ((np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax)
                  - np.take(c, np.arange(0, n), axis=ax)) / (2 * r + 1)).astype(np.float32)
    return a


_fonts = {}


def font(name='malgunbd.ttf'):
    import blf
    if name not in _fonts:
        _fonts[name] = blf.load(os.path.join(FONT_DIR, name))
        assert _fonts[name] != -1, name
    return _fonts[name]


def text_image(text, px, rgb=(1, 1, 1), fontname='malgunbd.ttf', pad=None):
    """Render one line of text -> RGBA image cropped to the ink (anti-aliased, premultiplied-free)."""
    import blf, imbuf
    fid = font(fontname)
    blf.size(fid, px)
    tw, th = blf.dimensions(fid, text)
    pad = int(px * 0.35) if pad is None else pad
    W, H = int(tw + 2 * pad) + 2, int(px * 1.6 + 2 * pad)
    ib = imbuf.new((W, H))
    with blf.bind_imbuf(fid, ib):
        blf.color(fid, 1, 1, 1, 1)
        blf.position(fid, pad, pad + px * 0.35, 0)
        blf.draw_buffer(fid, text)
    tmp = WORK / '_text.png'; tmp.parent.mkdir(parents=True, exist_ok=True)
    imbuf.write(ib, filepath=str(tmp))
    a = load_png(tmp)
    m = np.clip(a[..., :3].max(axis=2) * a[..., 3], 0, 1)
    ys, xs = np.nonzero(m > 0.02)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = np.zeros(m.shape + (4,), np.float32); out[..., :3] = rgb; out[..., 3] = m
    return out


def shear_x(img, k):
    """Italic-like shear: x' = x + k*(h-y)."""
    h, w = img.shape[:2]
    extra = int(abs(k) * h) + 1
    out = np.zeros((h, w + extra, img.shape[2]), np.float32)
    for y in range(h):
        off = k * (h - 1 - y) if k > 0 else -k * y
        xs = np.arange(w + extra) - off
        x0 = np.floor(xs).astype(int); f = (xs - x0)[:, None]
        valid0 = (x0 >= 0) & (x0 < w); valid1 = (x0 + 1 >= 0) & (x0 + 1 < w)
        a = np.where(valid0[:, None], img[y, np.clip(x0, 0, w - 1)], 0)
        b = np.where(valid1[:, None], img[y, np.clip(x0 + 1, 0, w - 1)], 0)
        out[y] = a * (1 - f) + b * f
    return out


def scale_to(img, w=None, h=None):
    H, W = img.shape[:2]
    if w is None:
        w = int(round(W * h / H))
    if h is None:
        h = int(round(H * w / W))
    return resize(img, max(1, int(w)), max(1, int(h)))


def outline(img, r, rgb):
    """Return an RGBA 'stroke' layer: alpha dilated by r px (for text outlines/shadows)."""
    a = img[..., 3]
    h, w = a.shape
    pa = np.pad(a, r)
    d = np.zeros_like(pa)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                d = np.maximum(d, np.roll(np.roll(pa, dy, 0), dx, 1))
    out = np.zeros(d.shape + (4,), np.float32); out[..., :3] = rgb; out[..., 3] = d
    return out


# ------------------------------------------------------------------ unrolled label rebake
def ring_param(x, z, mode='cyl', sx=1.0, sz=1.0):
    """Angle-like parameter in degrees, 0 = front centre (file -Z), +90 = +X side, 180 = back.
    'cyl': polar angle of (x/sx, -z/sz). 'bag': planar per half (linear in x), so a flat
    pouch keeps the photo's planar look and the seam lies exactly on the side edge."""
    if mode == 'cyl':
        return math.degrees(math.atan2(x / sx, -z / sz))
    t = max(-1.0, min(1.0, x / sx)) * 90.0
    return t if z <= 0 else (180.0 - t if t >= 0 else -180.0 - t)


def unrolled_uv(lod, face, seam_deg, y0, y1, mode='cyl', sx=1.0, sz=1.0, vpad=0.0):
    """New (u, v) for each face corner: u = (param - seam)/360 wrapped to [0, 1] consistently per face,
    v = (y1 - y)/(y1 - y0) mapped into [vpad, 1 - vpad]."""
    P = corners_xyz(lod, face)
    zc = sum(p[2] for p in P) / len(P)
    us = []
    for x, y, z in P:
        zz = z if abs(z) > 1e-7 else (zc if abs(zc) > 1e-9 else z)   # side-edge vertices: take the face's half
        t = ring_param(x, zz, mode, sx, sz)
        us.append(((t - seam_deg) % 360.0) / 360.0)
    if max(us) - min(us) > 0.5:
        us = [u + 1.0 if u < 0.5 else u for u in us]
    vs = [vpad + (1 - 2 * vpad) * (y1 - p[1]) / (y1 - y0) for p in P]
    return list(zip(us, vs))


def rebake(lod, faces, newuvs, W, H, src_images, flip_u=None):
    """Rasterise faces (indices) at their new UVs into a W x H image, sampling each face's current
    texture at its current UVs. src_images: {texture_path_lower: array}. Returns (img, coverage)."""
    out = np.zeros((H, W, 4), np.float32); cov = np.zeros((H, W), np.float32)
    for fi, nuv in zip(faces, newuvs):
        f = lod['faces'][fi]
        src = src_images[f['texture'].lower()]
        old = [(c[2], c[3]) for c in f['corners']]
        n = len(old)
        for k in range(1, n - 1):
            tri = [0, k, k + 1]
            P = np.array([[nuv[i][0] * W, nuv[i][1] * H] for i in tri])
            A = np.array([old[i] for i in tri])
            for shift in (0.0, -W):
                Q = P + [shift, 0]
                x0, x1 = int(max(0, math.floor(Q[:, 0].min()))), int(min(W, math.ceil(Q[:, 0].max()) + 1))
                y0, y1 = int(max(0, math.floor(Q[:, 1].min()))), int(min(H, math.ceil(Q[:, 1].max()) + 1))
                if x1 <= x0 or y1 <= y0:
                    continue
                X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
                (ax, ay), (bx, by), (cx, cy) = Q
                d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
                if abs(d) < 1e-12:
                    continue
                l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / d
                l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / d
                l3 = 1 - l1 - l2
                e = -1e-3
                m = (l1 >= e) & (l2 >= e) & (l3 >= e)
                if not m.any():
                    continue
                u = l1 * A[0, 0] + l2 * A[1, 0] + l3 * A[2, 0]
                v = l1 * A[0, 1] + l2 * A[1, 1] + l3 * A[2, 1]
                col = sample(src, u[m], v[m])
                sub = out[y0:y1, x0:x1]; sub[m] = col
                cs = cov[y0:y1, x0:x1]; cs[m] = 1
    return out, cov


def fill_uncovered(img, cov, iters=64):
    """Grow covered pixels into uncovered ones (padding for filtering/mips)."""
    a = img.copy(); c = cov.copy()
    for _ in range(iters):
        if c.min() > 0:
            break
        acc = np.zeros_like(a); n = np.zeros_like(c)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            acc += np.roll(np.roll(a * c[..., None], dy, 0), dx, 1)
            n += np.roll(np.roll(c, dy, 0), dx, 1)
        new = (c == 0) & (n > 0)
        a[new] = acc[new] / n[new][:, None]; c[new] = 1
    return a


def seam_band(img, c0, c1, k=12, vsmooth=None, feather=0.22, mid_flat=0.0):
    """Clean, continuous seam over columns c0..c1 (inclusive, may wrap past W).
    The band becomes a smooth colour gradient between the (median) colours just outside it on
    both sides, blurred vertically so text/detail does not smear into horizontal streaks. The
    outer `feather` fraction of the band cross-fades from the original art into that gradient."""
    H, W = img.shape[:2]
    vsmooth = max(3, H // 22) if vsmooth is None else vsmooth
    left = np.stack([img[:, (c0 - 1 - i) % W, :3] for i in range(k)], 1)
    right = np.stack([img[:, (c1 + 1 + i) % W, :3] for i in range(k)], 1)
    L = blur(np.median(left, axis=1)[:, None, :], vsmooth)[:, 0]
    R = blur(np.median(right, axis=1)[:, None, :], vsmooth)[:, 0]
    n = c1 - c0 + 1
    nf = max(2, int(n * feather))
    for i in range(n):
        t = (i + 0.5) / n
        if mid_flat:   # constant average colour over the middle `mid_flat` fraction (thin bag folds)
            a = (1 - mid_flat) / 2
            t = 0.5 * min(t / a, 1) if t < 0.5 else 1 - 0.5 * min((1 - t) / a, 1)
        t = t * t * (3 - 2 * t)
        grad = L * (1 - t) + R * t
        # keep some of the original art near both band borders
        e = min(i, n - 1 - i)
        keep = 0.0 if e >= nf else (1 - e / nf) ** 2
        col = (c0 + i) % W
        img[:, col, :3] = img[:, col, :3] * keep + grad * (1 - keep)
    return img


def deg_col(deg, seam_deg, W):
    return int(round(((deg - seam_deg) % 360.0) / 360.0 * W))


def write_report(name, data):
    out = TOOLS / 'reports'; out.mkdir(exist_ok=True)
    (out / (name + '.json')).write_text(json.dumps(data, indent=1, default=str), encoding='utf8')


# ------------------------------------------------------------------ added helpers (misc label fixes)
def paste_center(dst, src, cx, cy):
    h, w = src.shape[:2]
    return paste(dst, src, int(round(cx - w / 2)), int(round(cy - h / 2)))


def text_block(dst, text, px, rgb, cx, cy, fontname='malgunbd.ttf', stroke=0, stroke_rgb=(0, 0, 0), shear=0.0,
               max_w=None, align='center'):
    """Draw one line of text centred at (cx, cy) (align='left': cx is the left edge). Returns (w, h)."""
    t = text_image(text, px, rgb, fontname)
    if shear:
        t = shear_x(t, shear)
    if max_w and t.shape[1] > max_w:
        t = scale_to(t, w=max_w, h=t.shape[0])
    h, w = t.shape[:2]
    x = int(round(cx - w / 2)) if align == 'center' else int(round(cx))
    y = int(round(cy - h / 2))
    if stroke:
        paste(dst, outline(t, stroke, stroke_rgb), x - stroke, y - stroke)
    paste(dst, t, x, y)
    return w, h


def shape(dst, mask, rgb, alpha=1.0):
    dst[..., :3] = dst[..., :3] * (1 - mask[..., None] * alpha) + np.asarray(rgb, np.float32) * mask[..., None] * alpha
    return dst


def barcode(dst, x0, y0, w, h, seed=7, rgb=(0.05, 0.05, 0.05)):
    """Stylised (non-functional) barcode: white box with bars."""
    import random
    rnd = random.Random(seed)
    dst[y0:y0 + h, x0:x0 + w, :3] = 1.0
    x = x0 + max(2, w // 14)
    while x < x0 + w - max(2, w // 14):
        bw = rnd.choice((1, 1, 2, 3)); gap = rnd.choice((1, 2, 2, 3))
        dst[y0 + 2:y0 + h - 2, x:min(x + bw, x0 + w - 2), :3] = rgb
        x += bw + gap
    return dst


def white_bg_mask(img, thr=0.88, iters=4000):
    """Near-white background connected to the image border (flood fill by iterative dilation)."""
    white = img[..., :3].min(axis=2) > thr
    bg = np.zeros_like(white)
    bg[0, :] = white[0, :]; bg[-1, :] = white[-1, :]; bg[:, 0] = white[:, 0]; bg[:, -1] = white[:, -1]
    for _ in range(iters):
        grown = bg.copy()
        grown[1:] |= bg[:-1]; grown[:-1] |= bg[1:]; grown[:, 1:] |= bg[:, :-1]; grown[:, :-1] |= bg[:, 1:]
        grown &= white
        if (grown == bg).all():
            break
        bg = grown
    return bg


class Ring:
    """Arc-length parameter around a closed label ring (any convex outline in the x/z plane).
    u(x, z) in [0, 1): 0 at angle `seam_deg` (0 = front -Z, +90 = +X), increasing with the angle."""

    def __init__(self, pts, seam_deg=90.0):
        pts = sorted({(round(x, 6), round(z, 6)) for x, z in pts}, key=lambda p: math.atan2(p[0], -p[1]))
        ang = np.array([math.degrees(math.atan2(x, -z)) for x, z in pts])
        P = np.array(pts)
        seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
        self.perimeter = float(seg.sum())
        cum = np.concatenate([[0], np.cumsum(seg)[:-1]])
        self.ang = np.concatenate([ang - 360, ang, ang + 360])
        self.arc = np.concatenate([cum - self.perimeter, cum, cum + self.perimeter])
        self.seam = seam_deg
        self.s0 = float(np.interp(seam_deg, self.ang, self.arc))

    def arc_at(self, deg):
        deg = (deg + 180.0) % 360.0 - 180.0
        return float(np.interp(deg, self.ang, self.arc))

    def u(self, x, z):
        s = self.arc_at(math.degrees(math.atan2(x, -z)))
        return ((s - self.s0) / self.perimeter) % 1.0

    def u_deg(self, deg):
        return ((self.arc_at(deg) - self.s0) / self.perimeter) % 1.0


def ring_uv(lod, face, ring, y0, y1):
    P = corners_xyz(lod, face)
    us = [ring.u(x, z) for x, y, z in P]
    if max(us) - min(us) > 0.5:
        us = [u + 1.0 if u < 0.5 else u for u in us]
    return [(u, (y1 - p[1]) / (y1 - y0)) for u, p in zip(us, P)]
