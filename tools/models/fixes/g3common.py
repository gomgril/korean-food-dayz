"""Shared helpers for the 0.4.9 fix group 3 ("opened") scripts (fix_*.py in this folder).

FILE coordinates everywhere (x, y, z), Y up, exactly as modelfix.py.
Face winding / stored normals in these MLODs: cross(b - a, c - a) of the first three corners
(file coords) points INTO the model and equals the stored normal; the outward direction is its
negation (verified on every group-3 model with work/g3 tools before writing the fixes).

Every fix derives from tools/models/originals/<Addon>/models/<name>.p3d (copied there on first
run), so reruns never accumulate.
"""
import sys, os, math, json, shutil, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import modelfix as mf  # noqa: E402


def src_path(addon, name):
    return REPO / 'source' / addon / 'models' / (name + '.p3d')


def orig_path(addon, name):
    return TOOLS / 'originals' / addon / 'models' / (name + '.p3d')


def load_original(addon, name):
    """Back up source -> originals (first run only) and load the original."""
    o = orig_path(addon, name)
    if not o.exists():
        o.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path(addon, name), o)
    return mf.load(o)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(m, addon, name, report, **info):
    target = src_path(addon, name)
    digest = m.save(target)
    vis = mf.Model.bounds(m.visual_lods()[0])
    report.append(dict(model='%s/models/%s.p3d' % (addon, name), original_sha256=sha(orig_path(addon, name)),
                       fixed_sha256=digest, lod0_bounds=[[round(a, 5) for a in ax] for ax in vis], **info))
    print('saved %-28s %s' % (name, info if info else ''))
    return target


def write_report(topic, report):
    out = TOOLS / 'reports'
    out.mkdir(exist_ok=True)
    (out / (topic + '.json')).write_text(json.dumps(report, indent=1, default=str), encoding='utf8')
    print('report', out / (topic + '.json'))


# ------------------------------------------------------------------ geometry
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(v):
    le = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / le, v[1] / le, v[2] / le) if le > 1e-20 else (0.0, 0.0, 0.0)


def face_points(lod, f):
    return [lod['vertices'][c[0]][:3] for c in f['corners']]


def inward(lod, f):
    """Stored-normal convention (points into the model)."""
    p = face_points(lod, f)
    n = cross(sub(p[1], p[0]), sub(p[2], p[0]))
    if len(p) == 4 and max(abs(x) for x in n) < 1e-18:
        n = cross(sub(p[2], p[0]), sub(p[3], p[0]))
    return unit(n)


def outward(lod, f):
    n = inward(lod, f)
    return (-n[0], -n[1], -n[2])


def centroid(lod, f):
    p = face_points(lod, f)
    return tuple(sum(q[k] for q in p) / len(p) for k in range(3))


def faces_where(lod, pred):
    return [i for i, f in enumerate(lod['faces']) if pred(i, f)]


def tex_has(f, *subs):
    t = f['texture'].lower()
    return any(s.lower() in t for s in subs)


# ------------------------------------------------------------------ UV helpers
def _solve3(A, b):
    """Solve 3x3 linear system (Cramer)."""
    def det(M):
        return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
                + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))
    d = det(A)
    out = []
    for k in range(3):
        M = [list(r) for r in A]
        for r in range(3):
            M[r][k] = b[r]
        out.append(det(M) / d)
    return out


def fit_affine_uv(lod, faces, axes=(0, 1)):
    """Least squares u = a*p[ax0] + b*p[ax1] + c (same for v) over the corners of `faces`.
    Returns (fn(p) -> (u, v), max_residual)."""
    rows = []
    for i in faces:
        for vi, ni, u, v in lod['faces'][i]['corners']:
            p = lod['vertices'][vi]
            rows.append((p[axes[0]], p[axes[1]], u, v))
    coef = []
    for t in (2, 3):
        A = [[0.0] * 3 for _ in range(3)]; b = [0.0] * 3
        for r in rows:
            x = (r[0], r[1], 1.0)
            for i in range(3):
                b[i] += x[i] * r[t]
                for j in range(3):
                    A[i][j] += x[i] * x[j]
        coef.append(_solve3(A, b))
    res = max(max(abs(cu[0] * r[0] + cu[1] * r[1] + cu[2] - r[2 + k]) for k, cu in enumerate(coef)) for r in rows)

    def fn(p):
        a, b_ = p[axes[0]], p[axes[1]]
        return (coef[0][0] * a + coef[0][1] * b_ + coef[0][2], coef[1][0] * a + coef[1][1] * b_ + coef[1][2])
    return fn, res


def set_uv(lod, faces, fn):
    """fn(point_xyz, face_index) -> (u, v) for every corner of the listed faces."""
    for i in faces:
        f = lod['faces'][i]
        f['corners'] = [(vi, ni, *map(float, fn(lod['vertices'][vi][:3], i))) for vi, ni, u, v in f['corners']]


# ------------------------------------------------------------------ normals / vertices
def wkey(p, q=1e-6):
    return (round(p[0] / q), round(p[1] / q), round(p[2] / q))


def recompute_normals(lod, faces, angle=60.0):
    """Give the listed faces fresh smooth normals (stored convention), averaging adjacent faces of
    the same list that share a (welded) corner position and differ by less than `angle` degrees."""
    cosl = math.cos(math.radians(angle))
    fn = {i: inward(lod, lod['faces'][i]) for i in faces}
    at = {}
    for i in faces:
        for c in lod['faces'][i]['corners']:
            at.setdefault(wkey(lod['vertices'][c[0]]), []).append(i)
    for i in faces:
        f = lod['faces'][i]; n0 = fn[i]; new = []
        for vi, ni, u, v in f['corners']:
            acc = [0.0, 0.0, 0.0]
            for j in at[wkey(lod['vertices'][vi])]:
                nj = fn[j]
                if sum(a * b for a, b in zip(n0, nj)) >= cosl:
                    acc = [a + b for a, b in zip(acc, nj)]
            n = unit(acc)
            if n == (0.0, 0.0, 0.0):
                n = n0
            lod['normals'].append(n)
            new.append((vi, len(lod['normals']) - 1, u, v))
        f['corners'] = new


def move_vertices(lod, fn, indices):
    """fn(xyz) -> xyz applied to the given vertex indices (flags kept)."""
    V = lod['vertices']
    for i in indices:
        x, y, z, fl = V[i]
        q = fn((x, y, z))
        V[i] = (float(q[0]), float(q[1]), float(q[2]), fl)


def face_vertices(lod, faces):
    s = set()
    for i in faces:
        for c in lod['faces'][i]['corners']:
            s.add(c[0])
    return s


def add_face_out(m, lod, points, out_dir, texture, material, uv, selections=()):
    """Add a face and make sure its winding faces `out_dir` (outward)."""
    n = unit(cross(sub(points[1], points[0]), sub(points[2], points[0])))
    if sum(a * b for a, b in zip(n, out_dir)) > 0:  # stored normal must point inward
        points = list(reversed(points)); uv = list(reversed(uv))
    return m.add_face(lod, points, texture, material, uv, selections=selections)
