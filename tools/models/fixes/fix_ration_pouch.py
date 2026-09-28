"""0.4.9 group 3: combat-ration retort pouches (5 kinds, sealed + opened).

Defects (sealed)
- The label tile is projected straight along Y, so its upper third (title "식량, 전투용 I 형" and the
  menu line) lands on the steep pillow top above the shoulder: seen from above the print is
  squashed, and the back's title reads upside down.
- Bottom face: flat grey procedural colour. Top seal strip: grey line.
- Side gussets (|n.x| dominant) sample the 1-2 % wide edge of the tile (dark seam lines between
  atlas tiles) stretched across the gusset: mirrored streaky stripes.
(opened) the same sides and bottom.

Fix (all visual LODs; texture = the pouch's own tile of r043_atlases_rationlabels)
- sealed front/back: v re-mapped per height with a piecewise-linear table: the slope above the
  shoulder shows only the tile's plain foil top margin (tile t 0.02-0.22), the print (title at
  t 0.25) starts just below the shoulder, the logo stays above the bottom curve. Horizontal u is
  unchanged. Text is now less compressed vertically than before (4.9k vs 4.0k px/m on 50 g pouch).
- sides: u = plain crinkled-foil margin of the tile (t_u 0.03-0.13) across the gusset depth, v as
  the front at the same height -> no seam lines, no mirroring.
- bottom: atlas foil, u as the front (x), v across depth in the plain band between the menu line
  and the weight line (t 0.46-0.58).  Top seal (sealed): top foil margin.
- opened pouches keep their front/back mapping (the cut top already removes the slope) except the
  bottom curve, whose two rows had the same v (a stretched streak seen from below).
- sealed and opened: bottom curve t 0.93 -> 0.965 -> 0.995 (plain foil under the logo).
Geometry is unchanged.
"""
import math
import g3common as g

ATLAS = 'r043_atlases_rationlabels'
GREY = 'color(0.64,0.67,0.64'
MODELS = ['rationanchovy', 'rationkimchirice', 'rationmeatballs', 'rationtofu', 'rationwhiterice']


def interp(knots, y):
    ks = sorted(knots)
    if y <= ks[0][0]:
        return ks[0][1]
    for (y0, t0), (y1, t1) in zip(ks, ks[1:]):
        if y <= y1:
            return t0 + (t1 - t0) * (y - y0) / (y1 - y0)
    return ks[-1][1]


def fix(name):
    sealed = not name.endswith('_open')
    m = g.load_original('KF_Pantry', name)
    lod1 = m.visual_lods()[0]
    lab1 = g.faces_where(lod1, lambda i, f: g.tex_has(f, ATLAS))
    ref = lod1['faces'][lab1[0]]
    us = [c[2] for i in lab1 for c in lod1['faces'][i]['corners']]
    vs = [c[3] for i in lab1 for c in lod1['faces'][i]['corners']]
    tu0 = math.floor(min(us) * 3 + 1e-6) / 3
    tv0 = 0.5 if min(vs) >= 0.4 else 0.0
    rows = sorted({round(lod1['vertices'][c[0]][1], 4) for i in lab1 for c in lod1['faces'][i]['corners']})
    H = rows[-1]
    if sealed:
        assert len(rows) == 7, rows
        knots = [(H, 0.02), (rows[-2], 0.06), (rows[-3], 0.22), (rows[2], 0.93), (rows[1], 0.965), (rows[0], 0.995)]
    else:  # opened: only the bottom curve (below the y=0.018 row) is re-spread, the rest keeps its v
        v018 = next(c[3] for i in lab1 for c in lod1['faces'][i]['corners'] if abs(lod1['vertices'][c[0]][1] - rows[2]) < 1e-4)
        knots = [(rows[2], (v018 - tv0) / 0.5), (rows[1], 0.965), (rows[0], 0.995)]
    info = dict(tile_u0=round(tu0, 4), tile_v0=tv0, rows=rows)
    for lod in m.visual_lods():
        lab = g.faces_where(lod, lambda i, f: g.tex_has(f, ATLAS))
        side = [i for i in lab if abs(g.outward(lod, lod['faces'][i])[0]) > abs(g.outward(lod, lod['faces'][i])[2])]
        face = [i for i in lab if i not in set(side)]
        ufit, ures = g.fit_affine_uv(lod, [i for i in face if g.outward(lod, lod['faces'][i])[2] < 0], axes=(0, 1))  # front side only (back is mirrored)
        zs = [lod['vertices'][c[0]][2] for i in lab for c in lod['faces'][i]['corners']]
        zmax = max(abs(z) for z in zs)

        def vfront(p, old_v):
            return tv0 + 0.5 * interp(knots, p[1]) if (sealed or p[1] < rows[2] - 1e-5) else old_v
        for i in face:
            f = lod['faces'][i]
            f['corners'] = [(vi, ni, u, vfront(lod['vertices'][vi], v)) for vi, ni, u, v in f['corners']]
        for i in side:
            f = lod['faces'][i]
            f['corners'] = [(vi, ni, tu0 + (0.08 + 0.05 * lod['vertices'][vi][2] / zmax) / 3,
                             vfront(lod['vertices'][vi], v)) for vi, ni, u, v in f['corners']]
        # bottom (and sealed top seal strip): grey procedural faces with |n.y| dominant at the ends
        bottom = g.faces_where(lod, lambda i, f: g.tex_has(f, GREY) and g.outward(lod, f)[1] < -0.9
                               and max(lod['vertices'][c[0]][1] for c in f['corners']) < 0.002)
        top = g.faces_where(lod, lambda i, f: sealed and g.tex_has(f, GREY) and g.outward(lod, f)[1] > 0.9
                            and min(lod['vertices'][c[0]][1] for c in f['corners']) > H - 0.002)
        for i in bottom + top:
            lod['faces'][i]['texture'] = ref['texture']; lod['faces'][i]['material'] = ref['material']
        bz = max(abs(lod['vertices'][c[0]][2]) for i in bottom for c in lod['faces'][i]['corners'])
        g.set_uv(lod, bottom, lambda p, i: (ufit(p)[0], tv0 + 0.5 * (0.52 + 0.06 * p[2] / bz)))
        g.set_uv(lod, top, lambda p, i: (ufit(p)[0], tv0 + 0.5 * 0.015))
        info['lod%g' % lod['resolution']] = dict(front_back=len(face), sides=len(side), bottom=len(bottom), top_seal=len(top), u_fit_residual=round(ures, 4))
    return m, info


def main():
    report = []
    for base in MODELS:
        for name in (base, base + '_open'):
            m, info = fix(name)
            g.save(m, 'KF_Pantry', name, report, **info)
    g.write_report('fix_ration_pouch', report)


if __name__ == '__main__':
    main()
