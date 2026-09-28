"""0.4.9 group 3: seasoned gim (opened tray + closed pack).

seasonedgim_open
- Defect: the tray is a 50 % alpha "glass" colour, so from below the floor looks missing (the
  seaweed shows through) and the walls show the sheet stack's side faces as horizontal smears
  (their UVs are a 1-texel-wide strip of the seaweed atlas).
- Fix: tray faces -> opaque light green-white plastic colour with r043_plastic.rvmat (floor and
  walls now close the tray); the sheet-stack side faces get planar UVs on the seaweed part of the
  atlas (same texel density as the top), so the stack edge reads as seaweed, not a smear.
seasonedgim (closed, checked as asked)
- Same kind of smear on its thin side faces (u spans the whole front art incl. the noisy edge
  columns) and flat grey top/bottom seals. Fix: sides and seals get planar UVs on a clean white
  film area, and the whole pack uses r049_seasonedgim_pack_co.paa: an opaque copy of the atlas whose
  cut-out alpha fringe / baked photo background columns were replaced by clean film (tex_g3_blender.py);
  the old atlas made the pack edges see-through.
"""
import g3common as g

ATLAS = 'r043_atlases_seasonedgim'
TRAY_OLD = 'color(0.68,0.74,0.7,0.5'
TRAY_NEW = '#(argb,8,8,3)color(0.74,0.8,0.76,1,CO)'
PLASTIC = r'KF_Pantry\data\r043_plastic.rvmat'
PACK = r'KF_Pantry\data\r049_seasonedgim_pack_co.paa'  # opaque copy of the atlas (tex_g3_blender.py)


def fix_open():
    m = g.load_original('KF_Pantry', 'seasonedgim_open')
    info = {}
    for lod in m.visual_lods():
        tray = g.faces_where(lod, lambda i, f: g.tex_has(f, TRAY_OLD))
        for i in tray:
            lod['faces'][i]['texture'] = TRAY_NEW
            lod['faces'][i]['material'] = PLASTIC
        gim = g.faces_where(lod, lambda i, f: g.tex_has(f, ATLAS))
        tops = [i for i in gim if abs(g.outward(lod, lod['faces'][i])[1]) > 0.8]
        sides = [i for i in gim if abs(g.outward(lod, lod['faces'][i])[1]) <= 0.8]
        fn, res = g.fit_affine_uv(lod, [i for i in tops if g.outward(lod, lod['faces'][i])[1] > 0], axes=(0, 2))
        # u per metre along x, v per metre along z (from the top mapping)
        du = fn((1, 0, 0))[0] - fn((0, 0, 0))[0]
        dv = fn((0, 0, 1))[1] - fn((0, 0, 0))[1]

        def side_uv(p, i):
            o = g.outward(lod, lod['faces'][i])
            if abs(o[0]) >= abs(o[2]):   # x-facing edge: run along z
                u = 0.5 + p[2] * abs(du)
            else:                        # z-facing edge: run along x
                u = 0.5 + p[0] * abs(du)
            return (u, 0.74 + (p[1] - 0.0085) * abs(dv) * 3.0)  # stacked sheets: slightly compressed grain
        g.set_uv(lod, sides, side_uv)
        info['lod%g' % lod['resolution']] = dict(tray_faces=len(tray), stack_side_faces=len(sides), top_fit_residual=round(res, 4))
    return m, info


def fix_closed():
    m = g.load_original('KF_Pantry', 'seasonedgim')
    info = {}
    for lod in m.visual_lods():
        pack = g.faces_where(lod, lambda i, f: g.tex_has(f, ATLAS))
        sides = [i for i in pack if abs(g.outward(lod, lod['faces'][i])[0]) > 0.7]
        seals = g.faces_where(lod, lambda i, f: g.tex_has(f, 'color(0.76,0.78,0.71') and abs(g.outward(lod, f)[1]) > 0.9)
        ys = [lod['vertices'][c[0]][1] for i in pack for c in lod['faces'][i]['corners']]
        y0, y1 = min(ys), max(ys)
        vs = [c[3] for i in pack for c in lod['faces'][i]['corners']]
        v0, v1 = min(vs), max(vs)
        g.set_uv(lod, sides, lambda p, i: (0.90 + p[2] * 1.2, v1 - (p[1] - y0) / (y1 - y0) * (v1 - v0)))
        mat = lod['faces'][pack[0]]['material']
        for i in pack + seals:
            lod['faces'][i]['texture'] = PACK
            lod['faces'][i]['material'] = mat
        g.set_uv(lod, seals, lambda p, i: (0.90 + p[0] * 1.6, 0.25 + p[2] * 1.6))
        info['lod%g' % lod['resolution']] = dict(side_faces=len(sides), seal_faces=len(seals))
    return m, info


def main():
    report = []
    m, info = fix_open(); g.save(m, 'KF_Pantry', 'seasonedgim_open', report, **info)
    m, info = fix_closed(); g.save(m, 'KF_Pantry', 'seasonedgim', report, **info)
    g.write_report('fix_seasonedgim', report)


if __name__ == '__main__':
    main()
