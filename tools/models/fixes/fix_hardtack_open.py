"""0.4.9 group 3: opened hardtack (쌀건빵) bag.

Defects
- Half of each side gusset looked grey/unfinished: the side faces sample the outermost columns of
  the front art (u 0.016-0.03), which are transparent in the packaging atlas, so the side is
  see-through there and the grey inner liner shows.
- The crackers read as flat card strips: their rounded edges carry a stretched strip of the
  biscuit texture (u runs 0.5..1.0 around the edge, v ~0), and all 13 stand perfectly parallel.
- (also) front and back of the bag both showed the front art; the atlas has the real back art.

Fix (all visual LODs)
- Bag side faces (|n.x| > |n.z|): planar (z, y) UVs on the opaque cream margin of the art
  (u 0.021-0.045, left of the printed text; same v as before) -> closed, printed side.
- Bag back faces (n.z > 0): same UVs shifted by +0.5 onto the back art of the same atlas.
- Crackers (connected pieces with the biscuit texture, + their dark docking-hole discs): each
  piece is made 1.4x thicker about its own centre and turned by a small deterministic yaw
  (-7..+7 deg) about its vertical axis, holes follow; edge/bevel faces get planar UVs (along the
  edge x thickness) on the biscuit area; the flat-colour underside strip gets the same texture;
  smooth normals recomputed for the pieces.
Bag geometry, memory point, bbox are unchanged (crackers stay inside the bag's box).
"""
import math, collections
import g3common as g

PACK = 'packaging-atlas'
FOOD = 'food-atlas'
CRUMB = 'color(0.72,0.44,0.12'
HOLE = 'color(0.3,0.15,0.045'
THICK = 1.4


def components(lod, faces):
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    first = {}
    for i in faces:
        cs = lod['faces'][i]['corners']
        for c in cs:
            k = g.wkey(lod['vertices'][c[0]]); first.setdefault(k, c[0])
            parent[find(c[0])] = find(first[k])
        for c in cs[1:]:
            parent[find(c[0])] = find(cs[0][0])
    comp = collections.defaultdict(list)
    for i in faces:
        comp[find(lod['faces'][i]['corners'][0][0])].append(i)
    return list(comp.values())


def fix_bag(lod):
    bag = g.faces_where(lod, lambda i, f: g.tex_has(f, PACK))
    sides, backs = [], []
    for i in bag:
        o = g.outward(lod, lod['faces'][i])
        if abs(o[0]) > abs(o[2]):
            sides.append(i)
        elif o[2] > 0:
            backs.append(i)
    zs = [lod['vertices'][c[0]][2] for i in sides for c in lod['faces'][i]['corners']]
    zmax = max(abs(z) for z in zs)
    for i in sides:
        f = lod['faces'][i]
        f['corners'] = [(vi, ni, 0.033 + 0.012 * lod['vertices'][vi][2] / zmax, v) for vi, ni, u, v in f['corners']]
    for i in backs:
        f = lod['faces'][i]
        f['corners'] = [(vi, ni, u + 0.5 if u < 0.5 else u, v) for vi, ni, u, v in f['corners']]
    return dict(side_faces=len(sides), back_faces=len(backs))


def fix_crackers(m, lod):
    food = g.faces_where(lod, lambda i, f: g.tex_has(f, FOOD, CRUMB, HOLE))
    comps = components(lod, food)
    crackers = [c for c in comps if any(g.tex_has(lod['faces'][i], FOOD) for i in c)]
    holes = [c for c in comps if all(g.tex_has(lod['faces'][i], HOLE) for i in c)]
    ref = next(lod['faces'][i] for i in crackers[0] if g.tex_has(lod['faces'][i], FOOD))

    def cen(c):
        vs = g.face_vertices(lod, c)
        return tuple(sum(lod['vertices'][v][k] for v in vs) / len(vs) for k in range(3))
    cc = [cen(c) for c in crackers]
    attach = collections.defaultdict(list)
    for h in holes:
        hc = cen(h)
        k = min(range(len(crackers)), key=lambda j: (hc[0] - cc[j][0]) ** 2 + (hc[1] - cc[j][1]) ** 2 + (hc[2] - cc[j][2]) ** 2)
        attach[k].append(h)
    all_faces = []
    for k, c in enumerate(crackers):
        cx, cy, cz = cc[k]
        # deterministic yaw from the (LOD independent) position of the piece
        seed = (round(cx * 1000) * 7 + round(cz * 1000) * 13 + round(cy * 1000) * 3) % 15
        ang = math.radians(seed - 7)
        ca, sa = math.cos(ang), math.sin(ang)

        def tf(p):
            x, y, z = p[0] - cx, p[1] - cy, (p[2] - cz) * THICK
            return (cx + ca * x + sa * z, cy + y, cz - sa * x + ca * z)
        faces = c + [i for h in attach[k] for i in h]
        g.move_vertices(lod, tf, g.face_vertices(lod, faces))
        # UVs: biscuit texture on the edges / bevels / flat underside strip
        for i in c:
            f = lod['faces'][i]
            o = g.outward(lod, f)
            if abs(o[2] * ca + o[0] * sa) > 0.9 and g.tex_has(f, FOOD):
                continue                                  # big front/back faces keep their mapping
            t = g.unit((-o[1], o[0], 0.0)) if abs(o[2]) < 0.999 else (1.0, 0.0, 0.0)
            f['texture'] = ref['texture']; f['material'] = ref['material']
            f['corners'] = [(vi, ni, 0.75 + 20 * ((lod['vertices'][vi][0] - cx) * t[0] + (lod['vertices'][vi][1] - cy) * t[1]),
                             0.83 + 20 * ((lod['vertices'][vi][0] - cx) * sa + (lod['vertices'][vi][2] - cz) * ca))
                            for vi, ni, u, v in f['corners']]
        all_faces += faces
    g.recompute_normals(lod, all_faces, angle=50)
    return dict(crackers=len(crackers), holes=len(holes))


def main():
    report = []
    m = g.load_original('KF_Pantry', 'hardtack_open')
    info = {}
    for lod in m.visual_lods():
        info['lod%g' % lod['resolution']] = dict(**fix_bag(lod), **fix_crackers(m, lod))
    b0 = g.mf.Model.bounds(g.load_original('KF_Pantry', 'hardtack_open').visual_lods()[0])
    b1 = g.mf.Model.bounds(m.visual_lods()[0])
    assert all(b1[a][0] >= b0[a][0] - 1e-6 and b1[a][1] <= b0[a][1] + 1e-6 for a in range(3)), (b0, b1)
    g.save(m, 'KF_Pantry', 'hardtack_open', report, **info)
    g.write_report('fix_hardtack_open', report)


if __name__ == '__main__':
    main()
