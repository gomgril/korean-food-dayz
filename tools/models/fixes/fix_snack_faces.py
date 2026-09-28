"""0.4.9 group 3: opened dalgona / digestive / chocopie - untextured face.

Defect: the disc (dalgona), the 3-biscuit stack (digestive) and the half pie (chocopie) have the
food texture only on the file +Z face; the file -Z face is a flat procedural colour.

Fix: the -Z caps get the same food texture as the +Z caps. Their UVs come from an affine (x, y)
fit of the textured +Z cap of the same LOD, mirrored about the cap centre in X so the image is not
mirrored when seen from the -Z side. Hidden internal caps are left alone except digestive's plain
biscuit caps (all three get the biscuit texture; only the outer one is visible).

Orientation: NOT changed. These are KF_PantryHandSnack items held with the zagorky pose; the
v0.4.5 hand transform puts the bite end (kf_bite_end) at file -Y and the grip (kf_grip_center)
near the origin, and the item is held by the origin. Laying the disc flat would need a rotation
about the origin, which changes how it sits in the hand. Only UVs/textures change here: geometry,
memory points, face order, selections are untouched.
"""
import g3common as g

JOBS = {
    # name: (target colour texture substring, reference texture substring, reference uv filter)
    'dalgona_open': ('color(0.65,0.39,0.1,', 'dalgona_round_container_food', None),
    'digestive_open': ('color(0.72,0.44,0.12,', 'food-atlas', lambda u, v: u > 0.5 and v > 0.6),
    'chocopie_open': ('color(0.15,0.055,0.022,', 'food-atlas', lambda u, v: u > 0.5 and v < 0.33),
}


def fix(name):
    tgt_sub, ref_sub, uvfilter = JOBS[name]
    m = g.load_original('KF_Pantry', name)
    info = {}
    for lod in m.visual_lods():
        refs = g.faces_where(lod, lambda i, f: g.tex_has(f, ref_sub) and g.outward(lod, f)[2] > 0.9 and
                             (uvfilter is None or all(uvfilter(c[2], c[3]) for c in f['corners'])))
        tgts = g.faces_where(lod, lambda i, f: g.tex_has(f, tgt_sub) and g.outward(lod, f)[2] < -0.9)
        assert refs and tgts, (name, lod['resolution'], len(refs), len(tgts))
        fn, res = g.fit_affine_uv(lod, refs, axes=(0, 1))
        assert res < 0.01, ('reference cap is not a planar mapping', name, res)
        xs = [lod['vertices'][c[0]][0] for i in refs for c in lod['faces'][i]['corners']]
        cx = (min(xs) + max(xs)) / 2
        rf = lod['faces'][refs[0]]
        for i in tgts:
            lod['faces'][i]['texture'] = rf['texture']
            lod['faces'][i]['material'] = rf['material']
        g.set_uv(lod, tgts, lambda p, i: fn((2 * cx - p[0], p[1], p[2])))
        info['lod%g' % lod['resolution']] = dict(ref_faces=len(refs), retextured=len(tgts), fit_residual=round(res, 6))
    return m, info


def main():
    report = []
    for name in JOBS:
        m, info = fix(name)
        g.save(m, 'KF_Pantry', name, report, **info)
    g.write_report('fix_snack_faces', report)


if __name__ == '__main__':
    main()
