"""0.4.9 fix group 2 ("labels"): continuous side-label wraps without hard seams.

Problem: round cans/bottles/cups/jars and pillow bags carry their side print as two planar
photo projections (front half z<0 and back half z>0, sometimes the same photo twice). Where the
halves meet (x = +-r) the photo edges collide: mismatched art, stretched edge columns, and white
photo background (gatorade/ionthefit bottles, shin cup, cups, jars, bags).

Fix (per model, always from tools/models/originals):
1. The label faces of LOD 1 are re-baked into ONE new unrolled texture (u = angle around the
   body, v = height). The existing art is sampled through the existing UVs, so the front and back
   views look exactly as before.
2. A band around each side seam is replaced by a smooth per-row blend between the good art on
   both sides (labelkit.seam_band), so the halves meet with matching colours and no white gap.
3. All visual LODs get UVs from the same geometric mapping and the new texture
   (source/<Addon>/data/r049_labels_<model>_wrap_co.paa, PNG source in tools/models/textures/labels).
Geometry, selections, materials and all other faces are untouched.

Run:  blender.exe -b --factory-startup --python tools/models/fixes/fix_labels_wrap.py -- [--only a,b] [--preview]
      --preview only writes the raw unrolled bakes with a 30-degree grid to tools/models/work/labels/.
"""
import sys, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import labelkit as lk  # noqa: E402

# name: dict(addon, tex=[label textures], mode 'cyl'|'bag', bands=[(centre_deg, half_width_deg)],
#            mirror=bool (source art mirrored on the model), size=(W, H), ny=max |normal.y| of label faces)
C = dict
CONFIG = {
    # bottles (group 4): the same photo on both halves; bottle silhouette + white bg at the photo edges
    'gatorade':     C(tex=['gatorade_lemon_zero_blue_group'], bands=[(-124, -56), (56, 124)]),
    'gatoradeblue': C(tex=['gatorade_lemon_zero_blue_group'], bands=[(-124, -56), (56, 124)]),
    'gatoradezero': C(tex=['gatorade_lemon_zero_blue_group'], bands=[(-124, -56), (56, 124)]),
    'ionthefit':    C(tex=['ionthefit_front_group'], bands=[(-124, -56), (56, 124)]),
    # cans / jars (group 7)
    'friedkimchi':      C(tex=['atlases_friedkimchi'], bands=[(-127, -84), (80, 100)]),
    'friedkimchi_open': C(tex=['atlases_friedkimchi'], bands=[(-127, -84), (80, 100)], mat='metal'),
    'mccol':            C(tex=['mccol_slim_can'], bands=[(-126, -84), (54, 96)]),
    'sikhye':           C(tex=['sikhye_back_lid', 'sikhye_front'], bands=[(-110, -78), (72, 116)]),
    'sujeonggwa':       C(tex=['sujeonggwa_front'], bands=[(-126, -84), (54, 96)]),
    'ssaksak':          C(tex=['ssaksak_jeju', 'ssaksak_orange'], bands=[(-130, -84), (74, 100)]),
    'pinenuts':         C(tex=['pinenuts_jar'], bands=[(-126, -84), (54, 96)]),
    'pinenuts_open':    C(tex=['pinenuts_jar'], bands=[(-126, -84), (54, 96)]),
    'roastedblacksoy':  C(tex=['roastedblacksoy_jar'], bands=[(-126, -84), (54, 108)]),
    'roastedblacksoy_open': C(tex=['roastedblacksoy_jar'], bands=[(-126, -84), (54, 108)]),
    # cups (group 7 + group 6)
    'sesameramen':      C(tex=['sesameramen_cup_back_lid', 'sesameramen_cup_front'], bands=[(-100, -80), (80, 100)]),
    'sesameramen_open': C(tex=['sesameramen_cup_back_lid', 'sesameramen_cup_front'], bands=[(-100, -80), (80, 100)]),
    'tempuraudon':      C(tex=['tempuraudon_back', 'tempuraudon_front_lid'], bands=[(-112, -64), (58, 100)]),
    'tempuraudon_open': C(tex=['tempuraudon_back', 'tempuraudon_front_lid'], bands=[(-112, -64), (58, 100)]),
    'nurungji':         C(tex=['nurungji_back', 'nurungji_front'], bands=[(-136, -80), (60, 100)]),
    'nurungji_open':    C(tex=['nurungji_back', 'nurungji_front'], bands=[(-136, -80), (60, 100)]),
    'shin_cup_dry':     C(addon='KF_Food', tex=['r044_ref_09', 'r044_cup_fronts'], bands=[(-116, -62), (84, 128)], mat='paper'),
    'shin_cup_ready':   C(addon='KF_Food', tex=['r044_ref_09', 'r044_cup_fronts'], bands=[(-116, -62), (84, 128)], mat='paper'),
    # pillow bags (group 7): seam on the side fold, 'bag' = planar per half (degrees = % of half width)
    'neoguri_open':     C(tex=['neoguri_back', 'neoguri_front'], mode='bag', bands=[(-102, -78), (78, 102)], ny=0.9, mid_flat=0.5),
    'paldobibim_open':  C(tex=['paldobibim_back', 'paldobibim_front'], mode='bag', bands=[(-102, -78), (78, 102)], ny=0.9, mid_flat=0.5),
    'yugwa_open':       C(tex=['yugwa_back', 'yugwa_front'], mode='bag', bands=[(-102, -78), (78, 102)], ny=0.9, mid_flat=0.5),
    'matdongsan_open':  C(tex=['matdongsan_front_previous'], mode='bag', bands=[(-102, -78), (78, 102)], ny=0.9, mid_flat=0.5),
}
# Faces of the label with reversed winding (inner side of a double-sided label, e.g. ionthefit) showed the
# print mirrored through the clear bottle; they get a plain label-back colour instead.
BACKSIDE = '#(argb,8,8,3)color(0.9,0.92,0.93,1,CO)'
SEAM = 90.0          # texture u = 0 at the +X side (a vertex column on every model)


def label_faces(m, lod, cfg, backside=False):
    keys = [t.lower() for t in cfg['tex']]
    ny = cfg.get('ny', 0.6); mat = cfg.get('mat')
    out = []
    for i, f in enumerate(lod['faces']):
        t = f['texture'].lower()
        if not t.endswith('.paa') or not any(k in t for k in keys):
            continue
        if mat and mat not in f['material'].lower():
            continue
        n = lk.face_normal(lod, f)
        if abs(n[1]) > ny:
            continue
        P = lk.corners_xyz(lod, f)
        cx = sum(p[0] for p in P) / len(P); cz = sum(p[2] for p in P) / len(P)
        reversed_ = n[0] * cx + n[2] * cz > 0      # file convention: outward faces give a negative value
        if reversed_ == backside:
            out.append(i)
    return out


def process(name, cfg, preview=False):
    addon = cfg.get('addon', 'KF_Pantry')
    m, target = lk.load_original(addon, name)
    lod1 = m.visual_lods()[0]
    faces = label_faces(m, lod1, cfg)
    assert faces, name
    P = [lod1['vertices'][c[0]] for i in faces for c in lod1['faces'][i]['corners']]
    y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
    sx = max(abs(p[0]) for p in P); sz = max(abs(p[2]) for p in P)
    mode = cfg.get('mode', 'cyl')
    W, H = cfg.get('size', (1024, 512))
    srcs = {}
    for i in faces:
        t = lod1['faces'][i]['texture'].lower()
        if t not in srcs:
            srcs[t] = lk.load_tex(lod1['faces'][i]['texture'])
    newuv = [lk.unrolled_uv(lod1, lod1['faces'][i], SEAM, y0, y1, mode, sx, sz) for i in faces]
    img, cov = lk.rebake(lod1, faces, newuv, W, H, srcs)
    img = lk.fill_uncovered(img, cov)

    if preview:
        g = img.copy()
        for d in range(-180, 180, 30):
            c = lk.deg_col(d, SEAM, W) % W
            g[:, c, :3] = (1, 0, 1) if d % 90 == 0 else (0, 1, 1)
        lk.save_png(g, lk.WORK / 'preview' / (name + '.png'))
        print('preview', name, 'faces', len(faces), 'y', y0, y1, 'sx', sx, 'sz', sz, 'coverage', cov.mean())
        return None
    for d0, d1 in cfg['bands']:
        c0 = lk.deg_col(d0, SEAM, W)
        lk.seam_band(img, c0, c0 + int(round((d1 - d0) / 360.0 * W)) - 1, mid_flat=cfg.get('mid_flat', 0.0))
    newtex = lk.publish(img, 'labels', name + '_wrap', addon)
    changed = backs = 0
    for lod in m.visual_lods():
        for i in label_faces(m, lod, cfg):
            f = lod['faces'][i]
            m.set_face_uv(lod, i, lk.unrolled_uv(lod, f, SEAM, y0, y1, mode, sx, sz))
            f['texture'] = newtex
            changed += 1
        for i in label_faces(m, lod, cfg, backside=True):
            lod['faces'][i]['texture'] = BACKSIDE
            backs += 1
    digest = m.save(target)
    print('%-22s label faces %d, label back faces %d (all LODs) -> %s' % (name, changed, backs, newtex))
    return dict(model=name, addon=addon, texture=newtex, faces_changed=changed, backside_faces=backs, bands=cfg['bands'],
                mode=mode, size=(W, H), sha256=digest)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else list(CONFIG)
    preview = '--preview' in argv
    rep = [r for r in (process(n, CONFIG[n], preview) for n in only) if r]
    if not preview:
        lk.write_report('fix_labels_wrap' + ('' if len(only) == len(CONFIG) else '_partial'), rep)


main()
