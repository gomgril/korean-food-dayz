"""0.4.9 group 3: jwipo_open (one sheet of dried filefish).

Defect: the sheet is a ~1.2 mm thick oval whose rim faces all map to one texel (uv 0.5, 0.5), so
edge-on it vanishes into a paper-thin line and the rim is a flat colour.

Fix (all visual LODs): the two faces of the sheet are pushed apart by 0.9 mm each (vertices of
the file -Z side move -Z, of the +Z side +Z; the rim that joins them stretches with them), giving
a ~3 mm sheet with a visible edge. The rim faces get the texture that lies under them in the
front mapping (affine x,y fit of the +Z side) sampled at 94 % of the radius, i.e. the browned
fish edge rather than the photo's background pixels. Rim normals are
recomputed. Geometry LOD box is widened by the same 0.9 mm in Z so it still matches LOD0.
bbox Z: -0.0028..0.0016 -> -0.0037..0.0025 (x, y and memory points unchanged).
"""
import g3common as g

D = 0.0009


def is_rim(f):
    return all(abs(c[2] - 0.5) < 1e-4 and abs(c[3] - 0.5) < 1e-4 for c in f['corners'])


def main():
    report = []
    m = g.load_original('KF_Pantry', 'jwipo_open')
    info = {}
    for lod in m.visual_lods():
        rim = g.faces_where(lod, lambda i, f: is_rim(f))
        sheet = [i for i in range(len(lod['faces'])) if i not in set(rim)]
        neg = [i for i in sheet if g.outward(lod, lod['faces'][i])[2] < 0]
        pos = [i for i in sheet if g.outward(lod, lod['faces'][i])[2] >= 0]
        kneg = {g.wkey(lod['vertices'][v]) for v in g.face_vertices(lod, neg)}
        kpos = {g.wkey(lod['vertices'][v]) for v in g.face_vertices(lod, pos)}
        assert not (kneg & kpos), 'the two sides share vertices - no rim in between'
        fit, res = g.fit_affine_uv(lod, pos, axes=(0, 1))
        allv = g.face_vertices(lod, range(len(lod['faces'])))
        moved = 0
        for vi in allv:
            k = g.wkey(lod['vertices'][vi])
            dz = -D if k in kneg else (D if k in kpos else 0.0)
            if dz:
                g.move_vertices(lod, lambda p: (p[0], p[1], p[2] + dz), [vi]); moved += 1
        # sample a little inside the outline (the photo's very edge has plate/background pixels)
        xs = [p[0] for p in lod['vertices']]; ys = [p[1] for p in lod['vertices']]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        g.set_uv(lod, rim, lambda p, i: fit((cx + 0.94 * (p[0] - cx), cy + 0.94 * (p[1] - cy), 0.0)))
        g.recompute_normals(lod, rim, angle=35)
        info['lod%g' % lod['resolution']] = dict(rim_faces=len(rim), side_neg=len(neg), side_pos=len(pos),
                                                 moved_vertices=moved, uv_fit_residual=round(res, 4))
    geo = m.lod(g.mf.GEOMETRY)
    zs = [v[2] for v in geo['vertices']]
    zmin, zmax = min(zs), max(zs)
    for vi, v in enumerate(geo['vertices']):
        if abs(v[2] - zmin) < 1e-7:
            g.move_vertices(geo, lambda p: (p[0], p[1], p[2] - D), [vi])
        elif abs(v[2] - zmax) < 1e-7:
            g.move_vertices(geo, lambda p: (p[0], p[1], p[2] + D), [vi])
    vis = g.mf.Model.bounds(m.visual_lods()[0]); gb = g.mf.Model.bounds(geo)
    assert all(abs(vis[a][k] - gb[a][k]) < 1e-5 for a in range(3) for k in range(2)), (vis, gb)
    g.save(m, 'KF_Pantry', 'jwipo_open', report, **info)
    g.write_report('fix_jwipo_open', report)


if __name__ == '__main__':
    main()
