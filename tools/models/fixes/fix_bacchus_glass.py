"""0.4.9 group 3: Bacchus-D / Bacchus-F bottle base.

Defect: two vertex rings of the brown glass body - the base edge (y ~0.0185) and the heel just
above it (y ~0.0225) - have a random radius per vertex (e.g. 0.0194..0.0223 and 0.0227..0.0253
on bacchus, i.e. wider than the 0.024 body), so from above/below the bottle outline is an
irregular wavy dark blob.

Fix (all visual LODs): for every height ring within 10 mm of the bottle bottom (glass-body texture)
whose outer vertices vary
in radius by more than 3 %, the outer vertices (r > 0.6 r_max) are put on a circle with the ring's
mean radius (angle and height kept, axis = the ring's own centre = file origin). Normals of the
touched glass faces are recomputed. Geometry LOD / memory untouched; LOD0 x-extent shrinks by
~1 mm (the wobble), see report.
"""
import math, collections
import g3common as g

GLASS = 'color(0.21,0.07,0.012,0.6'


def main():
    report = []
    for name in ('bacchus', 'bacchusf'):
        m = g.load_original('KF_Pantry', name)
        info = {}
        for lod in m.visual_lods():
            faces = g.faces_where(lod, lambda i, f: g.tex_has(f, GLASS))
            verts = g.face_vertices(lod, faces)
            rings = collections.defaultdict(list)
            for vi in verts:
                rings[round(lod['vertices'][vi][1], 4)].append(vi)
            fixed = {}
            touched = set()
            ymin = min(rings)
            for y, vs in rings.items():
                if y > ymin + 0.01:   # only the base / heel rings (the neck lip is a real torus)
                    continue
                rs = {vi: math.hypot(lod['vertices'][vi][0], lod['vertices'][vi][2]) for vi in vs}
                rmax = max(rs.values())
                if rmax < 1e-4:
                    continue
                outer = [vi for vi in vs if rs[vi] > 0.6 * rmax]
                lo = min(rs[vi] for vi in outer)
                if (rmax - lo) / rmax <= 0.03:
                    continue
                target = sum(rs[vi] for vi in outer) / len(outer)
                for vi in outer:
                    x, yy, z, fl = lod['vertices'][vi]
                    s = target / rs[vi]
                    lod['vertices'][vi] = (x * s, yy, z * s, fl)
                    touched.add(vi)
                fixed[y] = dict(before=(round(lo, 4), round(rmax, 4)), after=round(target, 4), n=len(outer))
            tf = [i for i in faces if any(c[0] in touched for c in lod['faces'][i]['corners'])]
            g.recompute_normals(lod, tf, angle=50)
            info['lod%g' % lod['resolution']] = dict(rings=fixed, faces_renormalled=len(tf))
        g.save(m, 'KF_Pantry', name, report, **info)
    g.write_report('fix_bacchus_glass', report)


if __name__ == '__main__':
    main()
