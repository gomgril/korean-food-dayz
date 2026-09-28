"""0.4.9 group 3: paper cups.

A) tea_cup family (tea_cup, mix_cup - same cup mesh, cream wall + grey rolled rim):
   - a separate grey torus (r 0.040-0.042 m, y 0.002-0.004) floats around the foot, wider than
     the 0.036 m cup base; its far half shows below/through the cup, which made the cup read as
     semi-transparent with a stray ring. It is removed (grey faces whose highest point is below
     y 0.01; the rim torus at y ~0.115 stays).
   - the rim torus is recoloured from grey metal to the cup's inner paper colour.
   All cup materials are opaque procedural colours with food.rvmat (no alpha), wall faces are
   single-sided and outward (checked), so nothing else is needed for opacity.
B) white paper-cup family (paper_cup and every KF_Pantry *_cup / *_drink built on the same
   0.0744 x 0.091 cup, found by its colour #(argb,8,8,3)color(0.91,0.92,0.9,1,CO)):
   - the outer wall gets r049_paper_cup_band_co.paa (white paper with a subtle teal printed band,
     tools/models/textures/paper_cup/band.png from tex_g3.py): u = angle / 360 deg (the band is
     seamless, 12 wave periods), v = distance from the rim / wall height. Same material.
Geometry of B unchanged; A loses only the stray ring (bbox y/x unchanged, see report).
"""
import math
import g3common as g

PAPER = 'color(0.91,0.92,0.9,1'
BAND = r'KF_Pantry\data\r049_paper_cup_band_co.paa'
GREY = 'color(0.65,0.68,0.7,1'
TEA_INNER = '#(argb,8,8,3)color(0.88,0.85,0.77,1,CO)'
TEA_FAMILY = ['tea_cup', 'mix_cup']


def paper_family():
    import csv
    out = []
    for p in sorted((g.REPO / 'source' / 'KF_Pantry' / 'models').glob('*.p3d')):
        n = p.stem
        if not (n.endswith('_cup') or n.endswith('_drink')) or n in TEA_FAMILY:
            continue
        m = g.mf.load(g.orig_path('KF_Pantry', n) if g.orig_path('KF_Pantry', n).exists() else p)
        if any(PAPER in f['texture'] for f in m.visual_lods()[0]['faces']):
            out.append(n)
    return out


def fix_tea(name):
    m = g.load_original('KF_Pantry', name)
    info = {}
    for lod in m.visual_lods():
        P = lod['vertices']
        ring = set(g.faces_where(lod, lambda i, f: GREY in f['texture'] and max(P[c[0]][1] for c in f['corners']) < 0.01))
        rim = g.faces_where(lod, lambda i, f: GREY in f['texture'] and i not in ring)
        for i in rim:
            lod['faces'][i]['texture'] = TEA_INNER
        m.remove_faces(lod, lambda i, f: i in ring)
        info['lod%g' % lod['resolution']] = dict(removed_ring_faces=len(ring), recoloured_rim_faces=len(rim))
    return m, info


def fix_paper(name):
    m = g.load_original('KF_Pantry', name)
    info = {}
    for lod in m.visual_lods():
        P = lod['vertices']

        def is_outer(i, f):
            if PAPER not in f['texture']:
                return False
            cen = g.centroid(lod, f); o = g.outward(lod, f)
            r = math.hypot(cen[0], cen[2])
            fy = [P[c[0]][1] for c in f['corners']]   # wall quads run rim-to-foot (not the tea-bag tag)
            return r > 1e-6 and (o[0] * cen[0] + o[2] * cen[2]) / r > 0.5 and 0.02 < cen[1] < 0.09 and max(fy) - min(fy) > 0.05
        wall = g.faces_where(lod, is_outer)
        ys = [P[c[0]][1] for i in wall for c in lod['faces'][i]['corners']]
        y0, y1 = min(ys), max(ys)
        for i in wall:
            f = lod['faces'][i]
            us = [(math.atan2(P[c[0]][2], P[c[0]][0]) / (2 * math.pi)) % 1.0 for c in f['corners']]
            if max(us) - min(us) > 0.5:          # face straddles the seam: unwrap
                us = [u + 1.0 if u < 0.5 else u for u in us]
            f['texture'] = BAND
            f['corners'] = [(vi, ni, u, (y1 - P[vi][1]) / (y1 - y0)) for (vi, ni, _, _), u in zip(f['corners'], us)]
        info['lod%g' % lod['resolution']] = dict(outer_wall_faces=len(wall), wall_y=[round(y0, 4), round(y1, 4)])
    return m, info


def main():
    report = []
    for name in TEA_FAMILY:
        m, info = fix_tea(name)
        g.save(m, 'KF_Pantry', name, report, **info)
    fam = paper_family()
    print('paper-cup family:', fam)
    for name in fam:
        m, info = fix_paper(name)
        g.save(m, 'KF_Pantry', name, report, **info)
    g.write_report('fix_paper_cups', report)


if __name__ == '__main__':
    main()
