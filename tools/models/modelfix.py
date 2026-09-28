"""modelfix - small, explicit edit helpers for the mod's MLOD (.p3d) files.

Built on the vendored lossless reader/writer mlod045.py (origin noted in that file).

COORDINATES: everything in this module uses FILE coordinates (x, y, z) with Y = up,
exactly as stored in the p3d. (mlod045's add_face/face_normal helpers use Blender
Z-up coordinates instead - do not mix them with this module.)

Typical use (python 3.x, stdlib only):

    import modelfix as mf
    m = mf.load(r"...\\pepero_open.p3d")
    print(m.summary())
    m.rotate('x', 180)                      # all LODs incl. geometry + memory, normals too
    m.translate((0, 0.01, 0))
    m.retexture(r"KF_Pantry\\data\\old_co.paa", r"KF_Pantry\\data\\new_co.paa")
    m.map_uv(lambda u, v: (u, 1 - v), texture=r"KF_Pantry\\data\\new_co.paa")
    m.save(r"...\\out.p3d")                 # re-reads the file and checks structure

Selections (named selections, incl. memory point names) are kept: vertex/face weights are
preserved on transform/UV/texture edits, extended with 0 on add_face and compacted on
remove_faces. #Mass# is extended with 0 for new vertices, #UVSet# stage-0 data is rebuilt
from the face corners, other #UVSet# stages / #SharpEdges# are kept (append-only safe).
"""
import math, struct, sys, os, hashlib, json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mlod045  # noqa: E402

GEOMETRY = 1e13
MEMORY = 1e15


def _is_named(tag):
    return not tag['name'].startswith('#')


# ------------------------------------------------------------------ matrices
def rot_matrix(axis, degrees):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    # snap exact multiples of 90 degrees so 180-degree flips are bit-exact
    c = round(c) if abs(c - round(c)) < 1e-12 else c
    s = round(s) if abs(s - round(s)) < 1e-12 else s
    axis = axis.lower()
    if axis == 'x':
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 'y':
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    if axis == 'z':
        return ((c, -s, 0), (s, c, 0), (0, 0, 1))
    raise ValueError(axis)


def _mul(m, p):
    return tuple(m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] for r in range(3))


def _det(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _inv_transpose(m):
    d = _det(m)
    cof = [[0] * 3 for _ in range(3)]
    for r in range(3):
        for c in range(3):
            rows = [i for i in range(3) if i != r]
            cols = [j for j in range(3) if j != c]
            minor = m[rows[0]][cols[0]] * m[rows[1]][cols[1]] - m[rows[0]][cols[1]] * m[rows[1]][cols[0]]
            cof[r][c] = ((-1) ** (r + c)) * minor
    return tuple(tuple(cof[r][c] / d for c in range(3)) for r in range(3))  # (M^-1)^T = cof/det


def _norm(v):
    le = math.sqrt(sum(x * x for x in v))
    return tuple(x / le for x in v) if le else v


# ------------------------------------------------------------------ model
class Model:
    def __init__(self, path):
        self.path = str(path)
        self.doc = mlod045.read(path)
        self.source_sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for lod in self.doc['lods']:
            self._split_selections(lod)

    # selections are stored split (vertex bytes / face bytes) while editing
    @staticmethod
    def _split_selections(lod):
        nv, nf = lod['original_nv'], lod['original_nf']
        for t in lod['tags']:
            if _is_named(t):
                assert len(t['data']) == nv + nf, (t['name'], len(t['data']), nv, nf)
                t['_v'] = bytearray(t['data'][:nv])
                t['_f'] = bytearray(t['data'][nv:])

    @property
    def lods(self):
        return self.doc['lods']

    def lod(self, resolution):
        for l in self.lods:
            if abs(l['resolution'] - resolution) <= abs(resolution) * 1e-6:
                return l
        raise KeyError(resolution)

    def visual_lods(self):
        return [l for l in self.lods if l['resolution'] < 1000]

    def _select(self, lods):
        if lods is None:
            return self.lods
        if lods == 'visual':
            return self.visual_lods()
        return [l if isinstance(l, dict) else self.lod(l) for l in lods]

    # ---------------------------------------------------------- queries
    @staticmethod
    def bounds(lod):
        P = lod['vertices']
        if not P:
            return None
        return [(min(v[a] for v in P), max(v[a] for v in P)) for a in range(3)]

    def selections(self, lod):
        return [t['name'] for t in lod['tags'] if _is_named(t)]

    def selection_vertices(self, lod, name):
        t = next(t for t in lod['tags'] if t['name'] == name)
        return [i for i, w in enumerate(t['_v']) if w]

    def memory_points(self):
        """{name: [(x,y,z), ...]} from the memory LOD (resolution 1e15)."""
        try:
            lod = self.lod(MEMORY)
        except KeyError:
            return {}
        return {n: [tuple(lod['vertices'][i][:3]) for i in self.selection_vertices(lod, n)]
                for n in self.selections(lod)}

    def textures(self, lod=None):
        out = {}
        for l in self._select(None if lod is None else [lod]):
            for f in l['faces']:
                out[f['texture']] = out.get(f['texture'], 0) + 1
        return out

    def summary(self):
        rows = []
        for l in self.lods:
            b = self.bounds(l)
            rows.append(dict(resolution=l['resolution'], vertices=len(l['vertices']), faces=len(l['faces']),
                             bounds=[[round(x, 6) for x in ax] for ax in b] if b else None,
                             selections=self.selections(l)))
        return dict(path=self.path, lods=rows, memory_points=self.memory_points())

    # ---------------------------------------------------------- transforms
    def transform(self, matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), translate=(0, 0, 0), pivot=(0, 0, 0), lods=None):
        """p' = M (p - pivot) + pivot + translate, for vertices; normals get (M^-1)^T, renormalised.
        Applies to all LODs by default (visual, geometry, memory, ...).
        A mirroring matrix (det < 0) also reverses face corner order so faces stay outward."""
        d = _det(matrix)
        if abs(d) < 1e-12:
            raise ValueError('singular matrix')
        nm = _inv_transpose(matrix)
        off = tuple(pivot[k] + translate[k] for k in range(3))
        for l in self._select(lods):
            new = []
            for x, y, z, flag in l['vertices']:
                q = _mul(matrix, (x - pivot[0], y - pivot[1], z - pivot[2]))
                new.append((q[0] + off[0], q[1] + off[1], q[2] + off[2], flag))
            l['vertices'] = new
            l['normals'] = [_norm(_mul(nm, n)) for n in l['normals']]
            if d < 0:
                for f in l['faces']:
                    f['corners'] = list(reversed(f['corners']))
        return self

    def rotate(self, axis, degrees, pivot=(0, 0, 0), lods=None):
        return self.transform(rot_matrix(axis, degrees), pivot=pivot, lods=lods)

    def translate(self, offset, lods=None):
        return self.transform(translate=offset, lods=lods)

    def scale(self, factor, pivot=(0, 0, 0), lods=None):
        s = (factor,) * 3 if isinstance(factor, (int, float)) else tuple(factor)
        return self.transform(((s[0], 0, 0), (0, s[1], 0), (0, 0, s[2])), pivot=pivot, lods=lods)

    # ---------------------------------------------------------- UV / textures
    def faces_with_texture(self, lod, texture):
        t = texture.lower()
        return [i for i, f in enumerate(lod['faces']) if f['texture'].lower() == t]

    def set_face_uv(self, lod, face_index, uvs):
        f = lod['faces'][face_index]
        assert len(uvs) == len(f['corners'])
        f['corners'] = [(vi, ni, float(u), float(v)) for (vi, ni, _, _), (u, v) in zip(f['corners'], uvs)]

    def map_uv(self, fn, texture=None, lods='visual'):
        """fn(u, v) -> (u, v) for every face corner (optionally only faces using `texture`)."""
        n = 0
        for l in self._select(lods):
            for f in l['faces']:
                if texture is None or f['texture'].lower() == texture.lower():
                    f['corners'] = [(vi, ni, *map(float, fn(u, v))) for vi, ni, u, v in f['corners']]
                    n += 1
        return n

    def set_face_texture(self, lod, face_index, texture, material=None):
        f = lod['faces'][face_index]
        f['texture'] = texture
        if material is not None:
            f['material'] = material

    def retexture(self, old, new, material=None, lods=None):
        n = 0
        for l in self._select(lods):
            for f in l['faces']:
                if f['texture'].lower() == old.lower():
                    f['texture'] = new
                    if material is not None:
                        f['material'] = material
                    n += 1
        return n

    # ---------------------------------------------------------- add / remove
    def add_face(self, lod, points, texture='', material='', uv=None, normal=None, flags=0, selections=()):
        """Add a 3/4-corner face. points in FILE coords. Corner order as stored in the file
        (look at an existing face of the same model to match its winding convention).
        normal: stored normal (default: same convention as the generator, computed from points)."""
        assert len(points) in (3, 4)
        if normal is None:
            a, b, c = points[0], points[1], points[2]
            u = [b[i] - a[i] for i in range(3)]; w = [c[i] - a[i] for i in range(3)]
            normal = _norm((u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]))
        ni = len(lod['normals']); lod['normals'].append(tuple(normal))
        corners = []
        for i, p in enumerate(points):
            vi = len(lod['vertices']); lod['vertices'].append((float(p[0]), float(p[1]), float(p[2]), 0))
            u, v = uv[i] if uv else (0.0, 0.0)
            corners.append((vi, ni, float(u), float(v)))
        lod['faces'].append(dict(corners=corners, flags=flags, texture=texture, material=material))
        for t in lod['tags']:
            if _is_named(t):
                on = 1 if t['name'] in selections else 0
                t['_v'].extend(bytes([on]) * len(points)); t['_f'].append(on)
        return len(lod['faces']) - 1

    def remove_faces(self, lod, predicate):
        """Remove faces where predicate(index, face) is true. Vertices are kept (unused vertices
        are harmless and keep selection/mass/sharp-edge indices valid)."""
        keep = [i for i, f in enumerate(lod['faces']) if not predicate(i, f)]
        removed = len(lod['faces']) - len(keep)
        lod['faces'] = [lod['faces'][i] for i in keep]
        for t in lod['tags']:
            if _is_named(t):
                t['_f'] = bytearray(t['_f'][i] for i in keep)
        self._removed_faces = getattr(self, '_removed_faces', {})
        self._removed_faces.setdefault(id(lod), []).append(keep)
        return removed

    # ---------------------------------------------------------- save
    def _pack_tags(self, lod):
        nv, nf = len(lod['vertices']), len(lod['faces'])
        out = []
        for t in lod['tags']:
            t2 = dict(active=t['active'], name=t['name'], data=t['data'])
            if _is_named(t):
                v, f = bytes(t['_v']), bytes(t['_f'])
                v += bytes(nv - len(v)); assert len(v) == nv and len(f) == nf, t['name']
                t2['data'] = v + f
            elif t['name'] == '#Mass#':
                d = t['data']; old = len(d) // 4
                assert old <= nv
                t2['data'] = d + bytes(4 * (nv - old))
            elif t['name'] == '#UVSet#':
                stage = struct.unpack_from('<I', t['data'], 0)[0]
                if stage == 0:
                    buf = bytearray(struct.pack('<I', 0))
                    for fc in lod['faces']:
                        for _, _, u, v in fc['corners']:
                            buf += struct.pack('<ff', u, v)
                    t2['data'] = bytes(buf)
                elif getattr(self, '_removed_faces', {}).get(id(lod)) or nf != lod['original_nf']:
                    raise NotImplementedError('#UVSet# stage %d with face add/remove is not supported' % stage)
            out.append(t2)
        return out

    def save(self, path, check=True):
        doc = dict(version=self.doc['version'], lods=[])
        for l in self.lods:
            nl = dict(l)
            nl['tags'] = self._pack_tags(l)
            # tag data is already final: tell mlod045.write not to pad it again
            nl['original_nv'] = len(l['vertices']); nl['original_nf'] = len(l['faces'])
            doc['lods'].append(nl)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        mlod045.write(path, doc)
        if check:
            back = Model(path)
            assert len(back.lods) == len(self.lods)
            for a, b in zip(self.lods, back.lods):
                assert len(a['vertices']) == len(b['vertices']) and len(a['faces']) == len(b['faces'])
                assert [t['name'] for t in a['tags']] == [t['name'] for t in b['tags']]
                assert a['resolution'] == b['resolution']
            assert set(back.memory_points()) == set(self.memory_points())
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return Model(path)


def compare(path_a, path_b):
    """Structural comparison of two MLODs: counts, textures, selections, UVs, max vertex delta."""
    a, b = load(path_a), load(path_b)
    rows = []
    for la, lb in zip(a.lods, b.lods):
        same_topology = len(la['vertices']) == len(lb['vertices']) and len(la['faces']) == len(lb['faces'])
        row = dict(resolution=la['resolution'], same_topology=same_topology,
                   same_textures=[f['texture'] for f in la['faces']] == [f['texture'] for f in lb['faces']],
                   same_uv=same_topology and all([c[2:] for c in fa['corners']] == [c[2:] for c in fb['corners']]
                                                 for fa, fb in zip(la['faces'], lb['faces'])),
                   same_selections=[(t['name'], t['data']) for t in la['tags'] if _is_named(t)] ==
                                   [(t['name'], t['data']) for t in lb['tags'] if _is_named(t)],
                   bounds_a=Model.bounds(la), bounds_b=Model.bounds(lb))
        rows.append(row)
    return dict(lod_count=(len(a.lods), len(b.lods)), lods=rows,
                memory_a=a.memory_points(), memory_b=b.memory_points())


# ------------------------------------------------------------------ CLI
def _main(argv):
    import argparse
    p = argparse.ArgumentParser(description='Inspect / edit DayZ MLOD p3d files (FILE coords, Y up).')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('info'); s.add_argument('p3d')
    s = sub.add_parser('compare'); s.add_argument('a'); s.add_argument('b')
    s = sub.add_parser('rotate'); s.add_argument('src'); s.add_argument('dst')
    s.add_argument('--axis', required=True, choices='xyz'); s.add_argument('--deg', type=float, required=True)
    s.add_argument('--pivot', default='0,0,0')
    s = sub.add_parser('translate'); s.add_argument('src'); s.add_argument('dst'); s.add_argument('--by', required=True)
    s = sub.add_parser('retexture'); s.add_argument('src'); s.add_argument('dst')
    s.add_argument('--old', required=True); s.add_argument('--new', required=True)
    a = p.parse_args(argv)
    vec = lambda t: tuple(float(x) for x in t.split(','))
    if a.cmd == 'info':
        print(json.dumps(load(a.p3d).summary(), indent=1, default=str))
    elif a.cmd == 'compare':
        print(json.dumps(compare(a.a, a.b), indent=1, default=str))
    else:
        m = load(a.src)
        if a.cmd == 'rotate':
            m.rotate(a.axis, a.deg, pivot=vec(a.pivot))
        elif a.cmd == 'translate':
            m.translate(vec(a.by))
        elif a.cmd == 'retexture':
            print('faces changed:', m.retexture(a.old, a.new))
        print('saved', a.dst, m.save(a.dst))


if __name__ == '__main__':
    _main(sys.argv[1:])
