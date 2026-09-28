"""0.4.9 fix group 2 ("labels"): individual label/texture layout fixes.

  chilsungcider          new wrap label: horizontal '칠성사이다' logo on the star, clean info back, seamless
  jangjorim(_open)       side band re-laid out by arc length (no squashed text); opened top food not stretched
  perilla                lid print re-made landscape from the landscape product photo (perspective-rectified)
  peardrink              crisp generated back half (logo, info block, barcode) joined to the existing front
  nutenergybar           wrapper re-laid out portrait so the print reads upright on the standing bar
  nutenergybar_open      nut surface box-mapped (no vertical streaks)
  kkokkalcorn*           bag print cropped to the bag, photo background removed, planar front/back mapping

Always derives from tools/models/originals (backed up on first run). New textures:
source/<Addon>/data/r049_labels_<name>_co.paa, PNG sources in tools/models/textures/labels/.

Run:  blender.exe -b --factory-startup --python tools/models/fixes/fix_labels_misc.py -- [--only a,b]
"""
import sys, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import labelkit as lk  # noqa: E402

REF = 'work/kf-product-review/references/'
REPORT = []


def faces_where(lod, pred):
    return [i for i, f in enumerate(lod['faces']) if pred(f)]


def outward(lod, f):
    """File winding convention: outward faces have (Newell normal . centroid) < 0 in the xz plane."""
    n = lk.face_normal(lod, f)
    P = lk.corners_xyz(lod, f)
    c = np.mean(np.array(P), axis=0)
    return float(n[0] * c[0] + n[1] * c[1] * 0 + n[2] * c[2]) < 0


def median_rgb(img, u0, v0, u1, v1):
    c = lk.crop(img, u0, v0, u1, v1)[..., :3].reshape(-1, 3)
    return np.median(c, axis=0)


def save(m, target, name, **info):
    digest = m.save(target)
    REPORT.append(dict(model=name, sha256=digest, **info))
    print('saved', name, info.get('texture', ''))


# =================================================================== chilsungcider
def chilsungcider():
    name = 'chilsungcider'
    m, target = lk.load_original('KF_Pantry', name)
    lod1 = m.visual_lods()[0]
    is_label = lambda f: 'chilsungcider' in f['texture'].lower()
    L = faces_where(lod1, is_label)
    P = [lod1['vertices'][c[0]] for i in L for c in lod1['faces'][i]['corners']]
    y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
    r = max(max(abs(p[0]), abs(p[2])) for p in P)
    circ, hgt = 2 * math.pi * r, y1 - y0
    H = 512; Wp = int(round(H * circ / hgt))            # physical (square pixel) canvas
    photo = lk.load_tex(lod1['faces'][L[0]]['texture']) if 'pet_front' in lod1['faces'][L[0]]['texture'] else \
        lk.load_tex(next(lod1['faces'][i]['texture'] for i in L if 'pet_front' in lod1['faces'][i]['texture']))
    green = median_rgb(photo, 0.60, 0.40, 0.625, 0.44)     # label green from the product photo
    green = np.clip(green, 0, 1)
    dark = green * 0.62
    img = lk.fill(H, Wp, green)
    # soft vertical shading + thin white pinstripes near the label edges
    shade = (0.93 + 0.07 * np.sin(np.linspace(0, math.pi, H)))[:, None, None]
    img[..., :3] *= shade
    for yy in (14, H - 18):
        img[yy:yy + 4, :, :3] = img[yy:yy + 4, :, :3] * 0.3 + 0.7
    def xdeg(d):
        return ((d - 90.0) % 360.0) / 360.0 * Wp
    white = (0.97, 0.98, 0.97)
    # front: big star with white outline, logo across it
    cx, cy = xdeg(0), H * 0.52
    Ro = H * 0.50
    outer = lk.poly_mask(H, Wp, lk.star_points(cx, cy, Ro, Ro * 0.40))
    inner = lk.poly_mask(H, Wp, lk.star_points(cx, cy, Ro - 16, (Ro - 16) * 0.40))
    lk.shape(img, outer, white)
    lk.shape(img, inner, np.clip(green * 1.12 + 0.02, 0, 1))
    # small star cluster (upper left of the logo)
    for sx, sy, sr in ((-120, -150, 17), (-80, -175, 13), (-150, -110, 12), (-95, -120, 15), (-60, -140, 10)):
        lk.shape(img, lk.poly_mask(H, Wp, lk.star_points(cx + sx, cy + sy, sr, sr * 0.42)), white)
    lk.text_block(img, '칠성사이다', 118, white, cx + 6, cy + 18, stroke=7, stroke_rgb=tuple(dark), shear=0.22,
                  max_w=int(Wp * 0.36))
    lk.text_block(img, 'LOTTE', 30, white, cx - Ro * 0.95, H * 0.12, fontname='malgunbd.ttf')
    lk.text_block(img, 'Since 1950', 26, white, cx + Ro * 0.95, H * 0.12, fontname='malgun.ttf')
    # sides: smaller outline stars + name, so every view reads as the product
    for d in (95, -95):
        sx = xdeg(d)
        o = lk.poly_mask(H, Wp, lk.star_points(sx, H * 0.46, 110, 44)); i2 = lk.poly_mask(H, Wp, lk.star_points(sx, H * 0.46, 100, 40))
        lk.shape(img, o, white, 0.9); lk.shape(img, i2, np.clip(green * 1.08, 0, 1))
        lk.text_block(img, '칠성사이다', 52, white, sx, H * 0.80, stroke=4, stroke_rgb=tuple(dark), shear=0.2)
    # back: information panel
    bx = xdeg(180)
    pw, ph = int(Wp * 0.24), int(H * 0.72)
    x0, y0p = int(bx - pw / 2), int(H * 0.14)
    lk.shape(img, lk.rounded_rect_mask(H, Wp, x0, y0p, x0 + pw, y0p + ph, 22), white)
    ink = (0.12, 0.16, 0.13)
    lk.text_block(img, '칠성사이다', 50, tuple(np.clip(green * 0.9, 0, 1)), bx, y0p + 42)
    lines = ['식품유형 : 탄산음료', '원재료명 : 정제수, 액상과당, 설탕,', '탄산가스, 구연산, 천연향료',
             '보관방법 : 직사광선을 피해', '서늘한 곳에 보관하십시오.', '제조원 : 롯데칠성음료(주)']
    for k, t in enumerate(lines):
        lk.text_block(img, t, 22, ink, x0 + 22, y0p + 92 + k * 34, fontname='malgun.ttf', align='left', max_w=pw - 40)
    lk.barcode(img, int(bx - 70), y0p + ph - 78, 140, 60, seed=17)
    tex = lk.publish(lk.resize(img, 1024, 512), 'labels', 'chilsungcider_wrap')
    back = '#(argb,8,8,3)color(0.84,0.9,0.86,1,CO)'
    n = nb = 0
    for lod in m.visual_lods():
        for i in faces_where(lod, is_label):
            f = lod['faces'][i]
            if outward(lod, f):
                m.set_face_uv(lod, i, lk.unrolled_uv(lod, f, 90.0, y0, y1, 'cyl', 1, 1))
                f['texture'] = tex; n += 1
            else:
                f['texture'] = back; nb += 1
    save(m, target, name, texture=tex, label_faces=n, label_inside_faces=nb)


# =================================================================== jangjorim
def jangjorim_band_texture(lod1, band, ring, y0, y1):
    atlas = lk.load_tex(lod1['faces'][band[0]]['texture'])
    W = 2048; Hp = max(64, int(round(W * (y1 - y0) / ring.perimeter)))
    orange = median_rgb(atlas, 0.70, 0.02, 0.80, 0.08)
    img = lk.fill(Hp, W, orange)
    img[int(Hp * 0.86):, :, :3] = np.clip(orange * 0.8, 0, 1)
    img[:int(Hp * 0.07), :, :3] = np.clip(orange * 0.85, 0, 1)
    logo = lk.crop(atlas, 0.575, 0.16, 0.925, 0.40)            # 샘표 / 우리엄마 / 쇠고기장조림
    bgmask = np.linalg.norm(logo[..., :3] - orange, axis=2) < 0.10
    logo[..., 3] = np.where(bgmask, 0.0, 1.0)
    logo[..., 3] = lk.blur(logo[..., 3:4], 1)[..., 0]
    leaf_l = lk.crop(atlas, 0.50, 0.00, 0.62, 0.16)
    leaf_r = np.ascontiguousarray(leaf_l[:, ::-1])       # mirrored leaf spray
    lh = int(Hp * 0.74)
    logo_s = lk.scale_to(logo, h=lh)
    for deg in (0, 90, 180, -90):
        cx = ring.u_deg(deg) * W
        for dx in (0, -W, W):
            lk.paste_center(img, logo_s, cx + dx, Hp * 0.47)
        if deg in (90, -90):         # long sides: leaf decoration left and right of the logo
            for crop_, off in ((leaf_l, -1), (leaf_r, 1)):
                s = lk.scale_to(crop_, h=int(Hp * 0.8))
                a = np.clip(np.linalg.norm(s[..., :3] - orange, axis=2) / 0.25, 0, 1)
                s[..., 3] = a
                x = cx + off * (logo_s.shape[1] * 0.5 + s.shape[1] * 0.9)
                for dx in (0, -W, W):
                    lk.paste_center(img, s, x + dx, Hp * 0.45)
    return lk.publish(lk.resize(img, W, 256), 'labels', 'jangjorim_band')


def jangjorim():
    tex = None
    for name in ('jangjorim', 'jangjorim_open'):
        m, target = lk.load_original('KF_Pantry', name)
        lod1 = m.visual_lods()[0]
        is_band = lambda f: 'atlases_jangjorim' in f['texture'].lower() and 'metal' in f['material'].lower()
        band = faces_where(lod1, is_band)
        P = [lod1['vertices'][c[0]] for i in band for c in lod1['faces'][i]['corners']]
        y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
        ring = lk.Ring([(p[0], p[2]) for p in P], seam_deg=45.0)
        if tex is None:
            tex = jangjorim_band_texture(lod1, band, ring, y0, y1)
        n = 0
        for lod in m.visual_lods():
            for i in faces_where(lod, is_band):
                m.set_face_uv(lod, i, lk.ring_uv(lod, lod['faces'][i], ring, y0, y1))
                lod['faces'][i]['texture'] = tex; n += 1
        info = dict(texture=tex, band_faces=n, perimeter_m=ring.perimeter)
        if name.endswith('_open'):
            # opened top: food photo region (atlas u .05-.95, v .555-.88, 2.77:1) was squeezed onto a
            # 60x80 mm top. Map it rotated (long image axis along the long z axis) with the true aspect.
            is_food = lambda f: 'atlases_jangjorim' in f['texture'].lower() and 'food' in f['material'].lower()
            F = faces_where(lod1, is_food)
            Q = [lod1['vertices'][c[0]] for i in F for c in lod1['faces'][i]['corners']]
            hx = max(abs(p[0]) for p in Q); hz = max(abs(p[2]) for p in Q)
            vc, vh = 0.7175, 0.1575               # image rows used (atlas px are square: 1024x1024)
            uh = vh * hz / hx                      # half-range of u along z keeps the aspect
            nf = 0
            for lod in m.visual_lods():
                for i in faces_where(lod, is_food):
                    f = lod['faces'][i]
                    m.set_face_uv(lod, i, [(0.5 + uh * p[2] / hz, vc + vh * p[0] / hx) for p in lk.corners_xyz(lod, f)])
                    nf += 1
            info.update(food_faces=nf, food_uv=dict(u=(0.5 - uh, 0.5 + uh), v=(vc - vh, vc + vh)))
        save(m, target, name, **info)


# =================================================================== perilla
def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, Vt = np.linalg.svd(np.array(A, float))
    return Vt[-1].reshape(3, 3) / Vt[-1][-1]


def perilla():
    name = 'perilla'
    m, target = lk.load_original('KF_Pantry', name)
    lod1 = m.visual_lods()[0]
    is_lid = lambda f: 'perilla_mild_top' in f['texture'].lower()
    L = faces_where(lod1, is_lid)
    P = [lod1['vertices'][c[0]] for i in L for c in lod1['faces'][i]['corners']]
    hx = max(abs(p[0]) for p in P); hz = max(abs(p[2]) for p in P)
    # sign of the old mapping (keeps the print the same way up / not mirrored)
    su = np.sign(np.corrcoef([p[0] for p in P], [c[2] for i in L for c in lod1['faces'][i]['corners']])[0, 1])
    sv = np.sign(np.corrcoef([p[2] for p in P], [c[3] for i in L for c in lod1['faces'][i]['corners']])[0, 1])
    photo = lk.old_ref(REF + 'Perilla/mild_side.png')     # landscape lid, seen from the front-top
    # printed lid area corners in the photo (normalized x, y): TL, TR, BR, BL (measured on the reference)
    quad = [(0.263, 0.192), (0.742, 0.192), (0.768, 0.660), (0.238, 0.660)]
    W, H = 1024, int(round(1024 * hz / hx / 2)) * 2
    Hm = homography([(0, 0), (1, 0), (1, 1), (0, 1)], quad)
    U, V = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
    q = Hm @ np.stack([U.ravel(), V.ravel(), np.ones(U.size)])
    img = lk.sample(photo, (q[0] / q[2]).reshape(H, W), (q[1] / q[2]).reshape(H, W)).astype(np.float32)
    img[..., 3] = 1
    # printed green frame like the real lid (photo rim colour), rounded corners
    rim = median_rgb(photo, 0.20, 0.64, 0.30, 0.66)
    inner = lk.rounded_rect_mask(H, W, 14, 14, W - 14, H - 14, 40)
    lk.shape(img, 1 - inner, rim)
    tex = lk.publish(lk.resize(img, 1024, 1024), 'labels', 'perilla_lid')   # stored square; UVs span it fully
    n = 0
    for lod in m.visual_lods():
        for i in faces_where(lod, is_lid):
            f = lod['faces'][i]
            m.set_face_uv(lod, i, [(0.5 + su * 0.5 * p[0] / hx, 0.5 + sv * 0.5 * p[2] / hz) for p in lk.corners_xyz(lod, f)])
            f['texture'] = tex; n += 1
    save(m, target, name, texture=tex, lid_faces=n, lid_mm=(2000 * hx, 2000 * hz), source=REF + 'Perilla/mild_side.png')


# =================================================================== peardrink
def peardrink():
    name = 'peardrink'
    m, target = lk.load_original('KF_Pantry', name)
    lod1 = m.visual_lods()[0]
    is_label = lambda f: 'peardrink' in f['texture'].lower()
    L = faces_where(lod1, is_label)
    P = [lod1['vertices'][c[0]] for i in L for c in lod1['faces'][i]['corners']]
    y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
    r = max(max(abs(p[0]), abs(p[2])) for p in P)
    W, H = 1024, 512
    srcs = {}
    for i in L:
        t = lod1['faces'][i]['texture']
        srcs.setdefault(t.lower(), lk.load_tex(t))
    side = [i for i in L if abs(lk.face_normal(lod1, lod1['faces'][i])[1]) < 0.6]
    uvs = [lk.unrolled_uv(lod1, lod1['faces'][i], 90.0, y0, y1) for i in side]
    img, cov = lk.rebake(lod1, side, uvs, W, H, srcs)
    img = lk.fill_uncovered(img, cov)
    # ---- new crisp back half (u 0..0.5 = +X side .. back .. -X side), drawn on a square-pixel canvas
    Hp = 512; Wp = int(round(Hp * (math.pi * r) / (y1 - y0)))
    front = img[:, W // 2:, :3].reshape(-1, 3)
    cream = np.median(front[front.min(axis=1) > 0.72], axis=0)     # light background of the front art
    brown = np.array((0.36, 0.2, 0.1)); red = np.array((0.80, 0.12, 0.12)); yellow = np.array((0.99, 0.84, 0.15))
    b = lk.fill(Hp, Wp, cream)
    b[..., :3] *= (0.97 + 0.03 * np.linspace(1, 0, Hp))[:, None, None]
    cx = Wp / 2
    # logo: red serrated disc, white '갈아만든', yellow '배'
    ly = Hp * 0.22
    pts = []
    for k in range(64):
        a = 2 * math.pi * k / 64; rr = 78 if k % 2 == 0 else 70
        pts.append((cx + rr * math.cos(a), ly + rr * math.sin(a)))
    lk.shape(b, lk.poly_mask(Hp, Wp, pts), red)
    lk.text_block(b, 'SINCE 1996', 11, (1, 1, 1), cx, ly - 52, fontname='malgunbd.ttf')
    lk.text_block(b, '갈아만든', 22, (1, 1, 1), cx, ly - 30)
    lk.text_block(b, '배', 70, tuple(yellow), cx, ly + 18, stroke=3, stroke_rgb=(0.55, 0.05, 0.05))
    lk.text_block(b, '배퓨레 함유 · PEAR PUREE 12%', 17, tuple(brown), cx, Hp * 0.405, max_w=int(Wp * 0.6))
    # info block
    bx0, bx1 = int(cx - Wp * 0.21), int(cx + Wp * 0.21); by0, by1 = int(Hp * 0.45), int(Hp * 0.83)
    lk.shape(b, lk.rounded_rect_mask(Hp, Wp, bx0, by0, bx1, by1, 12), (1, 1, 1))
    b[by0:by0 + 30, bx0 + 8:bx1 - 8, :3] = brown
    lk.text_block(b, '제품정보', 19, (1, 1, 1), bx0 + 16, by0 + 15, align='left')
    lines = ['제품명 : 갈아만든 배', '식품유형 : 과·채음료', '제조원 : 해태htb', '개봉 후 바로 드십시오.',
             '직사광선을 피해 보관하십시오.']
    for k, t in enumerate(lines):
        lk.text_block(b, t, 15, (0.15, 0.12, 0.1), bx0 + 14, by0 + 50 + k * 25, fontname='malgun.ttf', align='left',
                      max_w=bx1 - bx0 - 26)
    lk.barcode(b, int(cx - 45), int(Hp * 0.86), 90, 44, seed=23)
    lk.text_block(b, '해태htb', 20, tuple(brown), cx - Wp * 0.17, Hp * 0.905)
    lk.text_block(b, '캔류', 13, (0.2, 0.2, 0.2), cx + Wp * 0.17, Hp * 0.905)
    # place: back half of the wrap = columns 0..W/2
    img[:, :W // 2] = lk.resize(b, W // 2, H)
    for d0, d1 in ((64, 116), (-116, -64)):
        c0 = lk.deg_col(d0, 90.0, W)
        lk.seam_band(img, c0, c0 + int(round((d1 - d0) / 360.0 * W)) - 1)
    tex = lk.publish(img, 'labels', 'peardrink_wrap')
    n = 0
    for lod in m.visual_lods():
        for i in faces_where(lod, is_label):
            f = lod['faces'][i]
            m.set_face_uv(lod, i, lk.unrolled_uv(lod, f, 90.0, y0, y1)); f['texture'] = tex; n += 1
    save(m, target, name, texture=tex, label_faces=n)


# =================================================================== nut energy bar
def energybar_wrapper(atlas):
    """Portrait (40 x 126 mm) wrapper layout from the landscape wrapper art, all text upright."""
    W, H = 512, 1536
    blue = median_rgb(atlas, 0.40, 0.03, 0.50, 0.07)
    orange = median_rgb(atlas, 0.06, 0.32, 0.09, 0.37)
    img = lk.fill(H, W, blue)
    # crimped striped ends: the atlas' vertical stripe strip, turned 90 degrees
    stripe = lk.crop(atlas, 0.0, 0.05, 0.05, 0.45)
    stripe = np.ascontiguousarray(np.rot90(stripe, -1))
    s = lk.resize(stripe, W, 90)
    img[:90] = s; img[H - 90:] = s[::-1]
    def put(crop_box, cx, cy, w=None, h=None, key=blue, tol=0.12):
        c = lk.crop(atlas, *crop_box)
        c = lk.scale_to(c, w=w, h=h)
        d = np.linalg.norm(c[..., :3] - key, axis=2)
        c[..., 3] = np.clip((d - tol) / 0.08, 0, 1)
        lk.paste_center(img, c, cx, cy)
    put((0.12, 0.02, 0.405, 0.305), W / 2, 285, w=360)                       # Dr.You circle logo
    put((0.43, 0.12, 0.60, 0.23), W / 2, 560, w=260)                         # 맛있는 에너지 충전!
    img[670:830, :, :3] = orange                                             # orange band
    put((0.11, 0.305, 0.53, 0.40), W / 2, 750, w=460, key=orange, tol=0.15)  # 에너지바
    put((0.55, 0.19, 0.80, 0.455), W / 2, 1045, w=360)                       # bar photo
    put((0.785, 0.295, 0.94, 0.435), W * 0.80, 1245, w=150)                  # protein badge
    put((0.03, 0.43, 0.33, 0.48), W / 2, 1335, w=440, tol=0.15)              # 견과류와 곡물로 채운 ...
    put((0.33, 0.43, 0.62, 0.475), W / 2, 1395, w=400, tol=0.15)             # 땅콩 29.5%, 아몬드 11.8%
    return img


def nutenergybar():
    # closed
    name = 'nutenergybar'
    m, target = lk.load_original('KF_Pantry', name)
    lod1 = m.visual_lods()[0]
    is_wrap = lambda f: 'atlases_energybar' in f['texture'].lower()
    L = faces_where(lod1, is_wrap)
    atlas = lk.load_tex(lod1['faces'][L[0]]['texture'])
    P = [lod1['vertices'][c[0]] for i in L for c in lod1['faces'][i]['corners']]
    x0, x1 = min(p[0] for p in P), max(p[0] for p in P)
    y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
    tex = lk.publish(lk.resize(energybar_wrapper(atlas), 512, 2048), 'labels', 'nutenergybar_wrapper')
    n = 0
    for lod in m.visual_lods():
        for i in faces_where(lod, is_wrap):
            f = lod['faces'][i]
            C = lk.corners_xyz(lod, f)
            back = sum(p[2] for p in C) / len(C) > 0
            uv = [(((x1 - p[0]) if back else (p[0] - x0)) / (x1 - x0), (y1 - p[1]) / (y1 - y0)) for p in C]
            m.set_face_uv(lod, i, uv); f['texture'] = tex; n += 1
    save(m, target, name, texture=tex, wrapper_faces=n)
    # opened: box-map the nut surface (image long axis along the bar's long y axis)
    name = 'nutenergybar_open'
    m, target = lk.load_original('KF_Pantry', name)
    lod1 = m.visual_lods()[0]
    L = faces_where(lod1, is_wrap)
    P = [lod1['vertices'][c[0]] for i in L for c in lod1['faces'][i]['corners']]
    lo = [min(p[a] for p in P) for a in range(3)]; hi = [max(p[a] for p in P) for a in range(3)]
    k = 0.92 / (hi[1] - lo[1])            # u per metre: bar length spans u .04-.96
    vc = 0.7525                           # food rows v .53-.975 (atlas pixels square)
    n = 0
    for lod in m.visual_lods():
        for i in faces_where(lod, is_wrap):
            f = lod['faces'][i]
            nn = np.abs(lk.face_normal(lod, f)); ax = int(np.argmax(nn))
            uv = []
            for p in lk.corners_xyz(lod, f):
                if ax == 1:     # end caps: x across, z along
                    u = 0.5 + k * p[2]; v = vc + k * p[0]
                else:           # long faces: y along the image, the other axis across
                    u = 0.04 + k * (p[1] - lo[1])
                    v = vc + k * (p[0] if ax == 2 else p[2])
                uv.append((u, v))
            m.set_face_uv(lod, i, uv); n += 1
    save(m, target, name, texture=lod1['faces'][L[0]]['texture'], food_faces=n)


# =================================================================== kkokkalcorn bags
def kkokkalcorn():
    ref = lk.old_ref(REF + 'Kkokkalcorn/four_flavors.png')
    for name, (ua, ub) in (('kkokkalcornsweetspicy', (0.49, 0.72)), ('kkokkalcornwaxycorn', (0.70, 0.935))):
        m, target = lk.load_original('KF_Pantry', name)
        lod1 = m.visual_lods()[0]
        is_bag = lambda f: 'kkokkalcorn_four_flavors' in f['texture'].lower()
        L = faces_where(lod1, is_bag)
        region = lk.crop(ref, ua, 0.22, ub, 0.86)
        bg = lk.white_bg_mask(region)
        ys, xs = np.nonzero(~bg)
        # the bag body: rows/cols where most pixels are not background (drops the crimp corner tips)
        colfrac = (~bg).mean(axis=0); rowfrac = (~bg).mean(axis=1)
        cols = np.nonzero(colfrac > 0.55)[0]; rows = np.nonzero(rowfrac > 0.55)[0]
        cx0, cx1, ry0, ry1 = cols.min(), cols.max() + 1, rows.min(), rows.max() + 1
        bag = region[ry0:ry1, cx0:cx1].copy()
        cov = (~bg[ry0:ry1, cx0:cx1]).astype(np.float32)
        bag = lk.fill_uncovered(bag, cov, iters=200)
        bag[..., 3] = 1
        tex = lk.publish(lk.resize(bag, 512, 1024), 'labels', name + '_bag')
        P = [lod1['vertices'][c[0]] for i in L for c in lod1['faces'][i]['corners']]
        x0, x1 = min(p[0] for p in P), max(p[0] for p in P)
        y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
        n = 0
        for lod in m.visual_lods():
            for i in faces_where(lod, is_bag):
                f = lod['faces'][i]
                C = lk.corners_xyz(lod, f)
                back = sum(p[2] for p in C) / len(C) > 0
                uv = [(((x1 - p[0]) if back else (p[0] - x0)) / (x1 - x0), (y1 - p[1]) / (y1 - y0)) for p in C]
                m.set_face_uv(lod, i, uv); f['texture'] = tex; n += 1
        save(m, target, name, texture=tex, bag_faces=n, crop_px=(int(cx0), int(ry0), int(cx1), int(ry1)),
             source=REF + 'Kkokkalcorn/four_flavors.png')


ALL = dict(chilsungcider=chilsungcider, jangjorim=jangjorim, perilla=perilla, peardrink=peardrink,
           nutenergybar=nutenergybar, kkokkalcorn=kkokkalcorn)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else list(ALL)
    for k in only:
        ALL[k]()
    lk.write_report('fix_labels_misc' + ('' if len(only) == len(ALL) else '_partial'), REPORT)


main()
