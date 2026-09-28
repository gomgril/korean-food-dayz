"""0.4.9 follow-up to fix group 5 ("photos"): carry the clean r049_photos_* textures over to sibling models.

fix_r049_photos.py replaced wrinkled/studio photo textures on the source models by NEW paa files whose clean art
sits in the SAME uv rectangle the old photo occupied (reports/r049_photos_layout.json, 'rect' = union of the uvs of
all faces that used the old texture, sibling models included). On the source models it only re-pointed faces:
texture == old (and, for the curry pouch, front = face centre z < 0 / back = z > 0). UVs were not touched.

Siblings (opened / prepared variants) still reference the old textures. This script, working on the CURRENT files
(other groups' edits are kept):
  1. re-point  : in every source/KF_Pantry|KF_Food model (except group 5's own models), every visual-LOD face whose
                 texture is an old group-5 texture AND whose uvs all lie inside that surface's layout rect (+-0.001)
                 AND whose side matches (curry only) gets the new texture. Nothing else changes. Faces that use the
                 old texture outside the rect (other products in a shared atlas) are left alone and reported.
  2. re-bake   : neoguri_open / paldobibim_open no longer use the old back texture directly: fix group 2
                 (fix_labels_wrap.py) baked the old wrinkled back photo into r049_labels_<model>_wrap_co.paa. For
                 them group 2's own process() is re-run from the original with the back faces first re-pointed to
                 the clean back (step 1 rule), so the wrap keeps group 2's seam fix but bakes the clean back.
Idempotent: step 1 finds nothing to do on a second run; step 2 re-bakes to identical output and skips writing the
texture when the PNG source is unchanged. Run AFTER fix_r049_photos.py, fix_labels_wrap.py and fix_packet_bottom.py
(a re-run of those two scripts rebuilds their models from the originals; run this one again afterwards).
Backups: tools/models/originals/<Addon>/models/<model>.p3d, only if none exists yet.

Run:  blender.exe -b --factory-startup --python tools/models/fixes/fix_r049_siblings.py [-- --dry-run]
"""
import sys, json, shutil, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
import modelfix as mf  # noqa: E402
import fix_r049_photos as ph  # noqa: E402  (import only; its main() is guarded)

SRC = REPO / 'source'
ORIG = TOOLS / 'originals'
LAYOUT = json.loads((TOOLS / 'reports' / 'r049_photos_layout.json').read_text(encoding='utf8'))
REPORT = TOOLS / 'reports' / 'fix_r049_siblings.json'
TOL = 1e-3
REBAKE = [('KF_Pantry', 'neoguri_open'), ('KF_Pantry', 'paldobibim_open')]
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
DRY = '--dry-run' in ARGV


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).relative_to(REPO)).replace('\\', '/')


def build_mapping():
    """old texture (lower) -> [dict(key, old, new, rect, side)] from group 5's SURFACES + layout."""
    mp = {}
    for key, s in ph.SURFACES.items():
        sides = {side for _, _, side in s['models']}
        side = sides.pop() if len(sides) == 1 else 'all'
        mp.setdefault(s['old'].lower(), []).append(dict(key=key, old=s['old'], new=s['new'], rect=LAYOUT[key]['rect'], side=side))
    return mp


MAPPING = build_mapping()
GROUP5_MODELS = {(a, n) for s in ph.SURFACES.values() for a, n, _ in s['models']} | {('KF_Pantry', n) for n in ph.MISUT_MODELS}


def drop_in(lod, f):
    """the mapping entry whose new texture is a drop-in for this face, or None."""
    for e in MAPPING.get(f['texture'].lower(), []):
        u0, v0, u1, v1 = e['rect']
        if not all(u0 - TOL <= c[2] <= u1 + TOL and v0 - TOL <= c[3] <= v1 + TOL for c in f['corners']):
            continue
        if ph.side_ok(e['side'], ph.face_center(lod, f)):
            return e
    return None


def repoint(m):
    """re-point drop-in faces in all visual LODs of a loaded model. Returns (changed{key: n}, left{old: n})."""
    changed, left = {}, {}
    for lod in m.visual_lods():
        for f in lod['faces']:
            t = f['texture'].lower()
            if t not in MAPPING:
                continue
            e = drop_in(lod, f)
            if e is None:
                name = f['texture'].split('\\')[-1]
                left[name] = left.get(name, 0) + 1
                continue
            f['texture'] = e['new']
            changed[e['key']] = changed.get(e['key'], 0) + 1
    return changed, left


def backup(addon, name):
    o = ORIG / addon / 'models' / (name + '.p3d')
    if not o.exists():
        o.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / addon / 'models' / (name + '.p3d'), o)
        return True
    return False


# ------------------------------------------------------------------ 1. re-point siblings in place
def repoint_siblings():
    out, untouched = [], []
    skip = GROUP5_MODELS | set(REBAKE)
    for addon in ('KF_Pantry', 'KF_Food'):
        for p in sorted((SRC / addon / 'models').glob('*.p3d')):
            if (addon, p.stem) in skip:
                continue
            m = mf.load(p)
            changed, left = repoint(m)
            if left:
                untouched.append(dict(model='%s/%s' % (addon, p.stem), faces_left_on_old_texture=left,
                                      reason='uvs outside the layout rect (not a drop-in)'))
            if not changed:
                continue
            before = sha(p)
            if not DRY:
                backup(addon, p.stem)
                m.save(p)
            out.append(dict(model='%s/%s' % (addon, p.stem), faces_repointed={MAPPING_KEYNEW[k]: n for k, n in changed.items()},
                            sha256_before=before, sha256_after=None if DRY else sha(p),
                            backup=rel(ORIG / addon / 'models' / (p.stem + '.p3d'))))
            print('REPOINT %-36s %s' % (addon + '/' + p.stem, ', '.join('%s x%d' % (k, n) for k, n in changed.items())))
    return out, untouched


MAPPING_KEYNEW = {e['key']: e['new'].split('\\')[-1] for es in MAPPING.values() for e in es}


# ------------------------------------------------------------------ 2. re-bake group 2's wraps with the clean back
def rebake_wraps():
    import numpy as np
    path = HERE / 'fix_labels_wrap.py'
    code = path.read_text(encoding='utf8').rstrip()
    assert code.endswith('\nmain()'), 'fix_labels_wrap.py layout changed'
    ns = {'__name__': 'fix_labels_wrap_lib', '__file__': str(path)}
    exec(compile(code[:-len('main()')], str(path), 'exec'), ns)       # group 2's code, without running its main()
    lk = ns['lk']
    load0, publish0 = lk.load_original, lk.publish
    state = {}

    def load_repointed(addon, name):
        m, target = load0(addon, name)                              # the untouched original (backs it up if missing)
        state['changed'], state['left'] = repoint(m)
        return m, target

    def publish_if_changed(arr, topic, name, addon='KF_Pantry'):
        png = lk.TEXSRC / topic / ('r049_%s_%s_co.png' % (topic, name))
        paa = SRC / addon / 'data' / ('r049_%s_%s_co.paa' % (topic, name))
        a = arr.copy(); a[..., 3] = 1.0
        if png.exists() and paa.exists():
            old = lk.load_png(png)
            if old.shape == a.shape and float(np.abs(old - np.clip(a, 0, 1)).max()) < 0.75 / 255:
                state['texture_written'] = False
                return '%s\\data\\%s' % (addon, paa.name)
        state['texture_written'] = True
        return publish0(arr, topic, name, addon)

    lk.load_original, lk.publish = load_repointed, publish_if_changed
    out = []
    try:
        for addon, name in REBAKE:
            target = SRC / addon / 'models' / (name + '.p3d')
            before = sha(target)
            if DRY:
                m, _ = load_repointed(addon, name)
                out.append(dict(model='%s/%s' % (addon, name), dry_run=True, back_faces_repointed_before_bake=state['changed']))
                continue
            r = ns['process'](name, ns['CONFIG'][name])
            out.append(dict(model='%s/%s' % (addon, name), back_faces_repointed_before_bake=
                            {MAPPING_KEYNEW[k]: n for k, n in state['changed'].items()},
                            left_on_old_texture=state['left'], wrap_texture=r['texture'],
                            wrap_texture_rewritten=state['texture_written'], label_faces=r['faces_changed'],
                            sha256_before=before, sha256_after=r['sha256'], model_changed=before != sha(target)))
            print('REBAKE  %-36s back faces %s, wrap %s (rewritten: %s)' % (addon + '/' + name, state['changed'],
                                                                           r['texture'], state['texture_written']))
    finally:
        lk.load_original, lk.publish = load0, publish0
    return out


def main():
    mapping = [dict(key=e['key'], old=e['old'], new=e['new'], rect=[round(x, 4) for x in e['rect']], side=e['side'])
               for es in MAPPING.values() for e in es]
    rep, untouched = repoint_siblings()
    rb = rebake_wraps()
    if REPORT.exists() and not DRY:
        # a re-run finds nothing left to re-point: keep the record of what earlier runs changed
        done = {r['model'] for r in rep}
        prev = json.loads(REPORT.read_text(encoding='utf8')).get('repointed', [])
        rep = [dict(r, note='re-pointed by an earlier run') if 'note' not in r else r
               for r in prev if r['model'] not in done] + rep
    report = dict(criterion='visual-LOD faces with an old group-5 texture whose uvs lie inside the layout rect '
                            '(+-%g) and whose side matches -> new texture; uvs/geometry untouched' % TOL,
                  mapping=mapping, repointed=rep, rebaked_wraps=rb, left_alone=untouched, dry_run=DRY)
    if not DRY:
        REPORT.write_text(json.dumps(report, indent=1, default=str), encoding='utf8')
    print('R049_SIBLINGS_DONE repointed %d, rebaked %d' % (len(rep), len(rb)))


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    raise SystemExit(1)
