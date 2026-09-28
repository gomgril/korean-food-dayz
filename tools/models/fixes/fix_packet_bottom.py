"""0.4.9 group 3: ramen packets prepared in the bag (뽀글이, *_packet_ready) - bottom face.

Defect: the bag bottom is a flat single-colour ellipse (procedural brand colour).

Fix (all visual LODs): the downward bottom faces (outward -Y at the lowest height, procedural
colour) get the packet's back art: u = the back side's own u(x) mapping (affine fit of the back
faces, so the print continues from the back and reads un-mirrored from below), v = a band of the
back art just above its bottom edge, scaled with the back's own v-per-metre so nothing is
stretched. The hidden upward-facing inner copy of the bottom is left alone.
The foil liner's downward bottom, coplanar with the bag bottom (z-fighting grey ellipse), is
removed. No vertices move; bbox unchanged.
"""
import collections
import g3common as g

MODELS = ['ansung_packet_ready', 'chapagetti_packet_ready', 'jin_hot_packet_ready', 'jin_mild_packet_ready',
          'shin_packet_ready']
FOIL = 'color(0.65,0.67,0.68'   # inner foil liner (not the printed outer bag)
SHARED_REPOINT = {'jin_mild_packet_ready': [(r'KF_Food\data\r044_ref_03_co.paa', r'KF_Food\data\r049_photos_jin_mild_back_co.paa')]}


def main():
    report = []
    for name in MODELS:
        m = g.load_original('KF_Food', name)
        info = {}
        for lod in m.visual_lods():
            P = lod['vertices']
            ymin = min(P[c[0]][1] for f in lod['faces'] for c in f['corners'])
            art = [i for i, f in enumerate(lod['faces']) if not f['texture'].startswith('#') and 'noodles' not in f['texture']]
            back_tex = collections.Counter(lod['faces'][i]['texture'] for i in art
                                           if g.outward(lod, lod['faces'][i])[2] > 0.9).most_common(1)[0][0]
            back = [i for i in art if lod['faces'][i]['texture'] == back_tex and g.outward(lod, lod['faces'][i])[2] > 0.9]
            fit, res = g.fit_affine_uv(lod, back, axes=(0, 1))
            dvdy = abs(fit((0, 1, 0))[1] - fit((0, 0, 0))[1])
            vb = [c[3] for i in back for c in lod['faces'][i]['corners']]
            v_bottom_edge = max(vb) if fit((0, 0, 0))[1] > fit((0, 1, 0))[1] else min(vb)
            bottom = g.faces_where(lod, lambda i, f: f['texture'].startswith('#') and FOIL not in f['texture'] and g.outward(lod, f)[1] < -0.9
                                   and max(P[c[0]][1] for c in f['corners']) < ymin + 0.0002)
            zs = [P[c[0]][2] for i in bottom for c in lod['faces'][i]['corners']]
            zb = max(abs(z) for z in zs)
            span = 2 * zb * dvdy
            sign = 1 if v_bottom_edge > 0.5 else -1          # band lies just inside the back's bottom edge
            v_hi = v_bottom_edge - sign * 0.03
            mat = lod['faces'][back[0]]['material']
            old = lod['faces'][bottom[0]]['texture']
            for i in bottom:
                lod['faces'][i]['texture'] = back_tex; lod['faces'][i]['material'] = mat
            # v grows towards -z (the front side): reads upright when looking up with +z at the top
            g.set_uv(lod, bottom, lambda p, i: (fit(p)[0], v_hi - sign * span * (p[2] + zb) / (2 * zb)))
            # the foil liner has its own downward bottom exactly coplanar (y = ymin) with the bag
            # bottom -> z-fighting grey ellipse over the print; it is always covered by the opaque
            # bag bottom, so it is removed (only downward faces at ymin; the liner's inside stays)
            liner = set(g.faces_where(lod, lambda i, f: FOIL in f['texture'] and g.outward(lod, f)[1] < -0.9
                                      and max(P[c[0]][1] for c in f['corners']) < ymin + 1e-5))
            nb = len(bottom)
            m.remove_faces(lod, lambda i, f: i in liner)
            info['lod%g' % lod['resolution']] = dict(bottom_faces=nb, removed_liner_faces=len(liner), old_texture=old, back_texture=back_tex,
                                                     back_fit_residual=round(res, 4), v_band=[round(v_hi - sign * span, 3), round(v_hi, 3)])
        # fix group 5 (fix_r049_photos.py) re-points jin_mild_packet_ready's back art in place to a clean
        # redraw placed in the same UV rectangle; keep that when re-running this script from the original
        for old, new in SHARED_REPOINT.get(name, []):
            if (g.REPO / 'source' / new.replace('\\', '/')).exists():
                info['repointed_%s' % new.split('\\')[-1]] = m.retexture(old, new, lods='visual')
        g.save(m, 'KF_Food', name, report, **info)
    g.write_report('fix_packet_bottom', report)


if __name__ == '__main__':
    main()
