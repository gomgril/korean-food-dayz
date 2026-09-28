"""0.4.9 fix group 5 ("photos"): replace baked photo textures (hands, backgrounds, crumpled backs).

Steps (all re-runnable, always derived from tools/models/originals/<Addon>/models/*.p3d):
  1. analyze : for every retextured surface, measure the UV rectangle + physical size of the faces that use the
               old photo texture (union over the models that share it) -> reports/r049_photos_layout.json
  2. textures: Blender (headless) runs r049_photos_textures.py, which composes clean label art and writes
               tools/models/textures/photos/*.png + source/<Addon>/data/r049_photos_*_co.paa
               (placed into the SAME uv rectangle the old photo occupied, so faces keep their UVs)
  3. models  : re-point only this group's faces to the new textures; rebuild misutgaru / misutgaru_open visual LODs
               (gusseted pillow bag, crimped seals, powder contents) and clean the combat-ration pouch sides.

Run:  <blender python> tools/models/fixes/fix_r049_photos.py [--blender <blender.exe>] [--skip-textures] [--only a,b]
"""
import sys, os, json, math, shutil, subprocess, argparse, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
import modelfix as mf  # noqa: E402

SRC = REPO / 'source'
ORIG = TOOLS / 'originals'
LAYOUT = TOOLS / 'reports' / 'r049_photos_layout.json'
DEFAULT_BLENDER = r"E:\SteamLibrary\steamapps\common\Blender\blender.exe"


def T(addon, name):
    return '%s\\data\\%s.paa' % (addon, name)


# ------------------------------------------------------------------ what gets retextured
# key -> dict(old=texture, new=texture, models=[(addon, model, side)], siblings=[models sharing the old texture
#        that are NOT changed here but whose UV rect is included so they can be re-pointed later without UV edits])
# side: 'all' = every face with the old texture, 'front' = faces with centre z < 0, 'back' = centre z > 0
SURFACES = {
    'ansung_back': dict(old=T('KF_Food', 'r044_ref_06_co'), new=T('KF_Food', 'r049_photos_ansung_back_co'),
                        models=[('KF_Food', 'ansung_packet_dry', 'all')], siblings=[('KF_Food', 'ansung_packet_ready')]),
    'chapagetti_back': dict(old=T('KF_Food', 'r044_ref_08_co'), new=T('KF_Food', 'r049_photos_chapagetti_back_co'),
                            models=[('KF_Food', 'chapagetti_packet_dry', 'all')], siblings=[('KF_Food', 'chapagetti_packet_ready')]),
    'jin_mild_back': dict(old=T('KF_Food', 'r044_ref_03_co'), new=T('KF_Food', 'r049_photos_jin_mild_back_co'),
                          models=[('KF_Food', 'jin_mild_packet_dry', 'all')], siblings=[('KF_Food', 'jin_mild_packet_ready')]),
    'neoguri_back': dict(old=T('KF_Pantry', 'r043_neoguri_back_4bb7027_co'), new=T('KF_Pantry', 'r049_photos_neoguri_back_co'),
                         models=[('KF_Pantry', 'neoguri', 'all')], siblings=[('KF_Pantry', 'neoguri_open')]),
    'odongtong_back': dict(old=T('KF_Pantry', 'r043_odongtong_back_53d58ef_co'), new=T('KF_Pantry', 'r049_photos_odongtong_back_co'),
                           models=[('KF_Pantry', 'odongtong', 'all')], siblings=[('KF_Pantry', 'odongtong_open')]),
    'paldobibim_back': dict(old=T('KF_Pantry', 'r043_paldobibim_back_be2348e_co'), new=T('KF_Pantry', 'r049_photos_paldobibim_back_co'),
                            models=[('KF_Pantry', 'paldobibim', 'all')], siblings=[('KF_Pantry', 'paldobibim_open')]),
    'homerunball_back': dict(old=T('KF_Pantry', 'r043_homerunball_back_dd7122b_co'), new=T('KF_Pantry', 'r049_photos_homerunball_back_co'),
                             models=[('KF_Pantry', 'homerunball', 'all'), ('KF_Pantry', 'homerunballclassic', 'all')], siblings=[]),
    'homerunballsaltmilk_back': dict(old=T('KF_Pantry', 'r043_homerunballsaltmilk_back_84a2527_co'),
                                     new=T('KF_Pantry', 'r049_photos_homerunballsaltmilk_back_co'),
                                     models=[('KF_Pantry', 'homerunballsaltmilk', 'all')], siblings=[]),
    'kkokkalcornroasted_back': dict(old=T('KF_Pantry', 'r043_kkokkalcorn_roasted_back_black_91a45c7_co'),
                                    new=T('KF_Pantry', 'r049_photos_kkokkalcornroasted_back_co'),
                                    models=[('KF_Pantry', 'kkokkalcornroasted', 'all')], siblings=[('KF_Pantry', 'kkokkalcornroasted_open')]),
    'ojingeopeanut_back': dict(old=T('KF_Pantry', 'r043_ojingeopeanut_back_8221d6d_co'), new=T('KF_Pantry', 'r049_photos_ojingeopeanut_back_co'),
                               models=[('KF_Pantry', 'ojingeopeanut', 'all')], siblings=[('KF_Pantry', 'ojingeopeanut_open')]),
    'samgyetang_back': dict(old=T('KF_Pantry', 'r043_samgyetang_back_66c8282_co'), new=T('KF_Pantry', 'r049_photos_samgyetang_back_co'),
                            models=[('KF_Pantry', 'samgyetang', 'all')], siblings=[('KF_Pantry', 'samgyetang_open')]),
    'yukgaejangsoup_back': dict(old=T('KF_Pantry', 'r043_yukgaejangsoup_back_3746ad7_co'), new=T('KF_Pantry', 'r049_photos_yukgaejangsoup_back_co'),
                                models=[('KF_Pantry', 'yukgaejangsoup', 'all')], siblings=[('KF_Pantry', 'yukgaejangsoup_open')]),
    'curry_front': dict(old=T('KF_Pantry', 'r043_curry_pouch_71c31e0_co'), new=T('KF_Pantry', 'r049_photos_curry_pouch_front_co'),
                        models=[('KF_Pantry', 'curry_pouch', 'front'), ('KF_Pantry', 'curry_open', 'front')], siblings=[]),
    'curry_back': dict(old=T('KF_Pantry', 'r043_curry_pouch_71c31e0_co'), new=T('KF_Pantry', 'r049_photos_curry_pouch_back_co'),
                       models=[('KF_Pantry', 'curry_pouch', 'back'), ('KF_Pantry', 'curry_open', 'back')], siblings=[]),
    # fronts whose photo still shows white studio background inside the mapped rectangle
    'homerunball_front': dict(old=T('KF_Pantry', 'r043_homerunball_front_design_1_95c2037_co'),
                              new=T('KF_Pantry', 'r049_photos_homerunball_front_co'),
                              models=[('KF_Pantry', 'homerunball', 'all')], siblings=[], front=True),
    'homerunballclassic_front': dict(old=T('KF_Pantry', 'r043_homerunball_front_design_2_657fab1_co'),
                                     new=T('KF_Pantry', 'r049_photos_homerunballclassic_front_co'),
                                     models=[('KF_Pantry', 'homerunballclassic', 'all')], siblings=[], front=True),
    'kkokkalcornroasted_front': dict(old=T('KF_Pantry', 'r043_kkokkalcorn_four_flavors_beff63d_co'),
                                     new=T('KF_Pantry', 'r049_photos_kkokkalcornroasted_front_co'),
                                     models=[('KF_Pantry', 'kkokkalcornroasted', 'all')], siblings=[], front=True),
    'ojingeopeanut_front': dict(old=T('KF_Pantry', 'r043_ojingeopeanut_front_0f32656_co'),
                                new=T('KF_Pantry', 'r049_photos_ojingeopeanut_front_co'),
                                models=[('KF_Pantry', 'ojingeopeanut', 'all')], siblings=[], front=True),
    'ansung_front': dict(old=T('KF_Food', 'r044_ref_05_co'), new=T('KF_Food', 'r049_photos_ansung_front_co'),
                         models=[('KF_Food', 'ansung_packet_dry', 'all')], siblings=[], front=True),
    'chapagetti_front': dict(old=T('KF_Food', 'r044_ref_07_co'), new=T('KF_Food', 'r049_photos_chapagetti_front_co'),
                             models=[('KF_Food', 'chapagetti_packet_dry', 'all')], siblings=[], front=True),
    # combat ration pouch: front and back share one clean print
    'combatbibimbap': dict(old=T('KF_Pantry', 'batch02_13_CombatBibimbap_front_co'), new=T('KF_Pantry', 'r049_photos_combatbibimbap_co'),
                           models=[('KF_Pantry', 'combatbibimbap', 'all'), ('KF_Pantry', 'combatbibimbap_open', 'all')], siblings=[]),
}
# rebuilt models (new geometry + new textures)
MISUT = dict(front=T('KF_Pantry', 'r049_photos_misutgaru_front_co'), back=T('KF_Pantry', 'r049_photos_misutgaru_back_co'),
             parts=T('KF_Pantry', 'r049_photos_misutgaru_parts_co'))
MISUT_MODELS = ['misutgaru', 'misutgaru_open']


def model_path(addon, name):
    return SRC / addon / 'models' / (name + '.p3d')


def original(addon, name):
    """Back up once, always return the untouched original."""
    o = ORIG / addon / 'models' / (name + '.p3d')
    if not o.exists():
        o.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model_path(addon, name), o)
    return o


def source_for_analysis(addon, name):
    o = ORIG / addon / 'models' / (name + '.p3d')
    return o if o.exists() else model_path(addon, name)


def face_center(lod, f):
    P = [lod['vertices'][c[0]] for c in f['corners']]
    return [sum(p[k] for p in P) / len(P) for k in range(3)]


def side_ok(side, cen):
    return side == 'all' or (side == 'front' and cen[2] < 0) or (side == 'back' and cen[2] > 0)


# ------------------------------------------------------------------ 1. analyze
def analyze():
    out = {}
    for key, s in SURFACES.items():
        u = [9, -9]; v = [9, -9]; x = [9, -9]; y = [9, -9]; n = 0
        members = [(a, m, side) for a, m, side in s['models']] + [(a, m, 'all') for a, m in s['siblings']]
        for addon, name, side in members:
            mm = mf.load(source_for_analysis(addon, name))
            for l in mm.visual_lods():
                for f in l['faces']:
                    if f['texture'].lower() != s['old'].lower():
                        continue
                    cen = face_center(l, f)
                    if not side_ok(side, cen):
                        continue
                    n += 1
                    for vi, ni, uu, vv in f['corners']:
                        u = [min(u[0], uu), max(u[1], uu)]; v = [min(v[0], vv), max(v[1], vv)]
                        p = l['vertices'][vi]
                        x = [min(x[0], p[0]), max(x[1], p[0])]; y = [min(y[0], p[1]), max(y[1], p[1])]
        assert n, key
        out[key] = dict(old=s['old'], new=s['new'], rect=[u[0], v[0], u[1], v[1]], size_m=[x[1] - x[0], y[1] - y[0]], faces=n,
                        front=bool(s.get('front')))
        print('%-26s rect u %.3f..%.3f v %.3f..%.3f  size %.3f x %.3f m  faces %d' % (key, u[0], u[1], v[0], v[1], x[1] - x[0], y[1] - y[0], n))
    LAYOUT.parent.mkdir(exist_ok=True)
    LAYOUT.write_text(json.dumps(out, indent=1), encoding='utf8')
    return out


# ------------------------------------------------------------------ 3a. retexture (UVs untouched)
def retexture_models(layout):
    per_model = {}
    for key, s in SURFACES.items():
        for addon, name, side in s['models']:
            per_model.setdefault((addon, name), []).append((s['old'], s['new'], side))
    report = []
    for (addon, name), subs in sorted(per_model.items()):
        m = mf.load(original(addon, name))
        counts = {}
        for l in m.visual_lods():
            for f in l['faces']:
                cen = face_center(l, f)
                for old, new, side in subs:
                    if f['texture'].lower() == old.lower() and side_ok(side, cen):
                        f['texture'] = new
                        counts[new] = counts.get(new, 0) + 1
                        break
        digest = m.save(model_path(addon, name))
        report.append(dict(model='%s/%s' % (addon, name), faces=counts, sha256=digest))
        print('%-34s %s' % (addon + '/' + name, ', '.join('%s x%d' % (k.split('\\')[-1], v) for k, v in counts.items())))
    return report


def retexture_shared_in_place():
    """jin_mild_packet_ready is owned by another fix group (its bottom); only its back-face texture reference is
    switched here, applied to the CURRENT file (no geometry/UV change, idempotent)."""
    s = SURFACES['jin_mild_back']
    p = model_path('KF_Food', 'jin_mild_packet_ready')
    m = mf.load(p)
    n = m.retexture(s['old'], s['new'], lods='visual')
    if n:
        m.save(p)
    print('KF_Food/jin_mild_packet_ready (in place) back faces re-pointed: %d' % n)
    return dict(model='KF_Food/jin_mild_packet_ready', faces_repointed=n, note='in place, texture reference only')


# ------------------------------------------------------------------ 3b. misutgaru stand-up bag geometry
PLASTIC = 'KF_Pantry\\data\\r043_plastic.rvmat'
FOOD = 'KF_Pantry\\data\\r043_food.rvmat'
GREEN_TEX = '#(argb,8,8,3)color(0.24,0.62,0.21,1,CO)'
INNER_TEX = '#(argb,8,8,3)color(0.80,0.72,0.61,1,CO)'
LABEL_H = 0.225   # printed label height (closed bag, below the crimp seal)


class MeshBuilder:
    """Collects faces in FILE coords. Points are given in any order + an outward hint; the builder stores
    them in the MLOD convention (cross(b-a, c-a) and the stored normal point INTO the surface)."""

    def __init__(self):
        self.faces = []  # (points, uvs, texture, material)

    def face(self, pts, uvs, tex, mat, out):
        a, b, c = pts[0], pts[1], pts[2]
        u = [b[k] - a[k] for k in range(3)]; w = [c[k] - a[k] for k in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        if sum(n[k] * out[k] for k in range(3)) > 0:   # currently outward -> reverse to inward
            pts = pts[::-1]; uvs = uvs[::-1]
        self.faces.append((pts, uvs, tex, mat))

    def write(self, lod):
        """replace a visual LOD's geometry; smooth normals per welded position and per texture group."""
        acc = {}
        fn = []
        for pts, uvs, tex, mat in self.faces:
            a, b, c = pts[0], pts[1], pts[2]
            u = [b[k] - a[k] for k in range(3)]; w = [c[k] - a[k] for k in range(3)]
            n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
            fn.append(n)
            for p in pts:
                k = (round(p[0], 6), round(p[1], 6), round(p[2], 6), tex)
                s = acc.setdefault(k, [0.0, 0.0, 0.0])
                for i in range(3):
                    s[i] += n[i]
        V, N, F, vidx, nidx = [], [], [], {}, {}
        for (pts, uvs, tex, mat), n in zip(self.faces, fn):
            corners = []
            for p, (uu, vv) in zip(pts, uvs):
                kp = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
                if kp not in vidx:
                    vidx[kp] = len(V); V.append((float(p[0]), float(p[1]), float(p[2]), 0))
                sn = acc[kp + (tex,)]
                ln = math.sqrt(sum(x * x for x in sn)) or 1.0
                sn = tuple(round(x / ln, 6) for x in sn)
                if sn not in nidx:
                    nidx[sn] = len(N); N.append(sn)
                corners.append((vidx[kp], nidx[sn], float(uu), float(vv)))
            F.append(dict(corners=corners, flags=0, texture=tex, material=mat))
        lod['vertices'], lod['normals'], lod['faces'] = V, N, F
        for t in lod['tags']:
            assert t['name'].startswith('#') and t['name'] not in ('#Mass#', '#UVSet#', '#SharpEdges#'), t['name']
        return len(F)


def interp(y, ys, vals):
    if y <= ys[0]:
        return vals[0]
    for i in range(1, len(ys)):
        if y <= ys[i]:
            t = (y - ys[i - 1]) / (ys[i] - ys[i - 1])
            t = t * t * (3 - 2 * t)
            return vals[i - 1] + (vals[i] - vals[i - 1]) * t
    return vals[-1]


PROF_Y = [0.000, 0.004, 0.012, 0.030, 0.060, 0.100, 0.140, 0.170, 0.195, 0.212, 0.222, 0.225]
PROF_A = [0.0770, 0.0785, 0.0795, 0.0800, 0.0800, 0.0800, 0.0800, 0.0802, 0.0808, 0.0815, 0.0822, 0.0825]
PROF_B = [0.0190, 0.0222, 0.0240, 0.0244, 0.0244, 0.0240, 0.0215, 0.0170, 0.0110, 0.0055, 0.0020, 0.0009]
# opened bag: the mouth is pulled open instead of pinched into the seal
OPEN_B = [0.0190, 0.0222, 0.0240, 0.0244, 0.0244, 0.0242, 0.0238, 0.0232, 0.0226, 0.0222, 0.0220, 0.0220]
GUSSET = 0.86   # |x| > GUSSET * a  -> side gusset


def ring_point(t, a, b, p):
    c, s = math.cos(t), math.sin(t)
    return (a * math.copysign(abs(c) ** (2 / p), c), b * math.copysign(abs(s) ** (2 / p), s))


def body_uv(x, y, z, a, b, region):
    v = min(1.0, max(0.0, 1 - y / LABEL_H))
    if region == 'front':
        return min(1.0, max(0.0, 0.5 + x / (2 * GUSSET * a))), v
    if region == 'back':
        return min(1.0, max(0.0, 0.5 - x / (2 * GUSSET * a))), v
    return 0.51 + 0.48 * min(1.0, max(0.0, 0.5 + z / (2 * max(b, 1e-4)))), v


def misut_body(mb, N, M, y_top, prof_b, scale=(1, 1, 1), tex_fb=None):
    """lofted gusseted body 0..y_top (closed-bag coordinates, then scaled)."""
    sx, sy, sz = scale
    ys = [y_top * (j / M) ** 1.0 for j in range(M + 1)]
    rings = []
    for y in ys:
        a = interp(y, PROF_Y, PROF_A); b = interp(y, PROF_Y, prof_b)
        p = 3.2 - 1.0 * min(1.0, y / LABEL_H)
        rings.append([(ring_point(2 * math.pi * i / N, a, b, p), a, b, y) for i in range(N)])
    for j in range(M):
        r0, r1 = rings[j], rings[j + 1]
        for i in range(N):
            i2 = (i + 1) % N
            q = [r0[i], r0[i2], r1[i2], r1[i]]
            cx = sum(e[0][0] for e in q) / 4; cz = sum(e[0][1] for e in q) / 4
            ca = sum(e[1] for e in q) / 4
            region = 'side' if abs(cx) > GUSSET * ca else ('front' if cz < 0 else 'back')
            tex = {'front': MISUT['front'], 'back': MISUT['back'], 'side': MISUT['parts']}[region]
            pts = [(e[0][0] * sx, e[3] * sy, e[0][1] * sz) for e in q]
            uvs = [body_uv(e[0][0], e[3], e[0][1], e[1], e[2], region) for e in q]
            mb.face(pts, uvs, tex, PLASTIC, (cx, 0, cz))
    return rings


def misut_closed_lod(N, M):
    mb = MeshBuilder()
    rings = misut_body(mb, N, M, LABEL_H, PROF_B)
    # flat gusset bottom (fan) in the print's green
    bot = rings[0]
    for i in range(N):
        i2 = (i + 1) % N
        pts = [(0, 0, 0), (bot[i][0][0], 0, bot[i][0][1]), (bot[i2][0][0], 0, bot[i2][0][1])]
        mb.face(pts, [(0, 0)] * 3, GREEN_TEX, PLASTIC, (0, -1, 0))
    # crimped top seal: thin full-width strip, ridged print on both faces
    y0, y1, t, hw = LABEL_H, 0.245, 0.0009, 0.0825
    K = max(4, N // 4)
    for k in range(K):
        xa, xb = -hw + 2 * hw * k / K, -hw + 2 * hw * (k + 1) / K
        ua, ub = 0.02 + 0.46 * k / K, 0.02 + 0.46 * (k + 1) / K
        for zs, flip in ((-t, False), (t, True)):
            pts = [(xa, y0, zs), (xb, y0, zs), (xb, y1, zs), (xa, y1, zs)]
            uu = [(ua, 0.48), (ub, 0.48), (ub, 0.02), (ua, 0.02)]
            if flip:
                uu = [(0.5 - u, v) for u, v in uu]
            mb.face(pts, uu, MISUT['parts'], PLASTIC, (0, 0, zs))
        mb.face([(xa, y1, -t), (xb, y1, -t), (xb, y1, t), (xa, y1, t)], [(0.25, 0.01)] * 4, MISUT['parts'], PLASTIC, (0, 1, 0))
    for sx in (-1, 1):
        mb.face([(sx * hw, y0, -t), (sx * hw, y1, -t), (sx * hw, y1, t), (sx * hw, y0, t)], [(0.25, 0.25)] * 4,
                MISUT['parts'], PLASTIC, (sx, 0, 0))
    return mb


def misut_open(N, M):
    """opened bag = the same bag cut open below the seal, scaled into the opened item's old box
    (x +-0.065, y 0..0.155, z +-0.022): x/y by k = 0.065/0.0825, z so the widest point is 0.022."""
    k = 0.065 / 0.0825
    sx, sy, sz = k, k, 0.022 / 0.0244
    y_cut = 0.155 / k
    mb = MeshBuilder()
    rings = misut_body(mb, N, M, y_cut, OPEN_B, scale=(sx, sy, sz))
    bot = rings[0]
    for i in range(N):
        i2 = (i + 1) % N
        pts = [(0, 0, 0), (bot[i][0][0] * sx, 0, bot[i][0][1] * sz), (bot[i2][0][0] * sx, 0, bot[i2][0][1] * sz)]
        mb.face(pts, [(0, 0)] * 3, GREEN_TEX, PLASTIC, (0, -1, 0))
    top = rings[-1]
    wall = 0.0007
    yr = y_cut * sy
    y_pow = yr - 0.011
    inner = []
    for (xz, a, b, y) in top:
        x, z = xz[0] * sx, xz[1] * sz
        ln = math.hypot(x, z) or 1
        inner.append((x - wall * x / ln, z - wall * z / ln))
    # rim (thin top edge of the cut film)
    for i in range(N):
        i2 = (i + 1) % N
        o0 = (top[i][0][0] * sx, yr, top[i][0][1] * sz); o1 = (top[i2][0][0] * sx, yr, top[i2][0][1] * sz)
        n0 = (inner[i][0], yr, inner[i][1]); n1 = (inner[i2][0], yr, inner[i2][1])
        mb.face([o0, o1, n1, n0], [(0.75, 0.5)] * 4, MISUT['parts'], PLASTIC, (0, 1, 0))
        # inner film wall down to the powder
        d0 = (inner[i][0], y_pow, inner[i][1]); d1 = (inner[i2][0], y_pow, inner[i2][1])
        mb.face([n0, n1, d1, d0], [(0.75, 0.3), (0.75, 0.3), (0.75, 0.45), (0.75, 0.45)], MISUT['parts'], PLASTIC,
                (-(n0[0] + n1[0]), 0, -(n0[2] + n1[2])))
    # powder: soft mound with a few lumps
    R = max(3, M // 5)
    ax = max(abs(p[0]) for p in inner); bz = max(abs(p[1]) for p in inner)

    def pp(ri, i):
        r = ri / R
        x, z = inner[i % N][0] * r, inner[i % N][1] * r
        h = 0.0042 * (1 - r * r) + 0.0009 * math.sin(x * 260 + 0.7) * math.sin(z * 410 + 1.3) * (1 - r)
        return (x, y_pow + h, z)

    def puv(p):
        return (0.25 + 0.23 * p[0] / ax, 0.75 + 0.23 * p[2] / bz)
    cen = (0.0, y_pow + 0.0042, 0.0)
    for i in range(N):
        a_, b_ = pp(1, i), pp(1, i + 1)
        mb.face([cen, a_, b_], [puv(cen), puv(a_), puv(b_)], MISUT['parts'], FOOD, (0, 1, 0))
        for ri in range(1, R):
            q = [pp(ri, i), pp(ri, i + 1), pp(ri + 1, i + 1), pp(ri + 1, i)]
            mb.face(q, [puv(p) for p in q], MISUT['parts'], FOOD, (0, 1, 0))
    return mb


def build_misutgaru():
    out = []
    for name in MISUT_MODELS:
        m = mf.load(original('KF_Pantry', name))
        mem0 = m.memory_points()
        geo0 = mf.Model.bounds(m.lod(mf.GEOMETRY))
        res = {}
        for l in m.visual_lods():
            r = l['resolution']
            N, M = {1.0: (64, 40), 3.0: (32, 20), 6.0: (16, 10)}[r]
            mb = misut_closed_lod(N, M) if name == 'misutgaru' else misut_open(N, M)
            res[r] = mb.write(l)
        digest = m.save(model_path('KF_Pantry', name))
        chk = mf.load(model_path('KF_Pantry', name))
        assert chk.memory_points() == mem0
        vis = mf.Model.bounds(chk.visual_lods()[0])
        print('%-16s faces %s  bounds %s  geometry %s' % (name, res, [[round(v, 4) for v in ax] for ax in vis],
                                                          [[round(v, 4) for v in ax] for ax in geo0]))
        out.append(dict(model='KF_Pantry/' + name, faces=res, bounds=vis, geometry_lod_bounds=geo0, sha256=digest))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blender', default=DEFAULT_BLENDER)
    ap.add_argument('--skip-textures', action='store_true')
    ap.add_argument('--misut-ref', default=None, help='old project references\\Misutgaru\\front_back_1kg.png (only needed once)')
    a = ap.parse_args()
    for addon, name, _ in [x for s in SURFACES.values() for x in s['models']]:
        original(addon, name)
    for name in MISUT_MODELS:
        original('KF_Pantry', name)
    layout = analyze()
    if not a.skip_textures:
        textures_cmd(a.blender, ['--misut-ref', a.misut_ref] if a.misut_ref else [])
    rep = dict(retextured=retexture_models(layout), shared=retexture_shared_in_place(), misutgaru=build_misutgaru())
    (TOOLS / 'reports' / 'fix_r049_photos.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf8')
    print('OK')


def textures_cmd(blender, extra):
    cmd = [blender, '-b', '--factory-startup', '--python', str(HERE / 'r049_photos_textures.py'), '--',
           '--layout', str(LAYOUT)] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace')
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith('R049')]
    print('\n'.join(lines))
    if r.returncode != 0 or 'R049_TEXTURES_DONE' not in r.stdout:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit('texture step failed')


if __name__ == '__main__':
    if '--analyze-only' in sys.argv:
        analyze()
    else:
        main()
