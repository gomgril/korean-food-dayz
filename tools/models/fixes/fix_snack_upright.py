"""Pilot fix (2026-09-28): stand opened Pepero x6 and opened yanggaeng x2 upright.

v0.4.5 (old project work/kf-snacks045/make_snacks.py hand_transform) turned these models 180 deg
about X so the bite end sits at file -Y (y = -0.062) and the wrapper/grip at +Y. On the ground and
in the inventory preview (both use the model's own axes; the inventory preview renders the model
with orientation 0,0,0) they therefore look upside down.

This script undoes that flip with a pure 180-degree rotation about the file X axis THROUGH THE
MODEL ORIGIN: (x, y, z) -> (x, -y, -z), applied to every LOD (visual 1/3/6, geometry, memory),
normals included. The models use autocenter=0, so the origin is the point the engine attaches to
the hand; rotating about the origin keeps the same physical grip point at the hand and only turns
the product over. Memory points follow the geometry (kf_bite_end -> +Y top, kf_grip_center -> -Y).
UVs, textures, selections, mass and face order are untouched (det = +1, so winding stays valid).

Always derives from tools/models/originals/<name>.p3d (made on first run) - reruns never accumulate.

Run:  <python> tools/models/fixes/fix_snack_upright.py
"""
import sys, os, shutil, json, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import modelfix as mf  # noqa: E402

MODELS = ['pepero_open', 'peperoalmond_open', 'peperochococookie_open', 'peperochocofilled_open',
          'peperocrunky_open', 'peperowhitecookie_open', 'yanggaeng_open', 'chestnutyanggaeng_open']
SRC = REPO / 'source' / 'KF_Pantry' / 'models'
ORIG = TOOLS / 'originals' / 'KF_Pantry' / 'models'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ORIG.mkdir(parents=True, exist_ok=True)
    report = []
    for name in MODELS:
        target = SRC / (name + '.p3d')
        backup = ORIG / (name + '.p3d')
        if not backup.exists():
            shutil.copy2(target, backup)
        m = mf.load(backup)
        mem0 = m.memory_points()
        assert set(mem0) == {'kf_bite_end', 'kf_grip_center'}, mem0
        assert mem0['kf_bite_end'][0][1] < 0 < mem0['kf_grip_center'][0][1], 'original is not the v0.4.5 flipped state'
        before = [mf.Model.bounds(l) for l in m.lods]
        m.rotate('x', 180)
        digest = m.save(target)

        # ---- verification against the untouched original
        new, old = mf.load(target), mf.load(backup)
        for lo, ln in zip(old.lods, new.lods):
            assert len(lo['vertices']) == len(ln['vertices']) and len(lo['faces']) == len(ln['faces'])
            for (x, y, z, fl), (x2, y2, z2, fl2) in zip(lo['vertices'], ln['vertices']):
                assert (x2, y2, z2, fl2) == (x, -y, -z, fl) or max(abs(x2 - x), abs(y2 + y), abs(z2 + z)) < 1e-7
            for fo, fn in zip(lo['faces'], ln['faces']):
                assert [c[0] for c in fo['corners']] == [c[0] for c in fn['corners']]
                assert [c[2:] for c in fo['corners']] == [c[2:] for c in fn['corners']]  # UV identical
                assert (fo['texture'], fo['material'], fo['flags']) == (fn['texture'], fn['material'], fn['flags'])
            assert [(t['name'], t['data']) for t in lo['tags']] == [(t['name'], t['data']) for t in ln['tags']]
        mem = new.memory_points()
        vis = mf.Model.bounds(new.visual_lods()[0])
        bite, grip = mem['kf_bite_end'][0], mem['kf_grip_center'][0]
        assert abs(bite[1] - vis[1][1]) < 1e-6, 'bite end must be the top of the model'
        assert grip[1] < bite[1]
        geo = mf.Model.bounds(new.lod(mf.GEOMETRY))
        assert all(abs(geo[a][k] - vis[a][k]) < 1e-6 for a in range(3) for k in range(2)), 'geometry box = LOD0 box'
        report.append(dict(model=name, original_sha256=sha(backup), fixed_sha256=digest,
                           bounds_before=before[0], bounds_after=vis, memory_before=mem0, memory_after=mem))
        print('%-24s y %.4f..%.4f  bite_end y=%.4f  grip y=%.4f' % (name, vis[1][0], vis[1][1], bite[1], grip[1]))
    out = TOOLS / 'reports'
    out.mkdir(exist_ok=True)
    (out / 'fix_snack_upright.json').write_text(json.dumps(report, indent=1), encoding='utf8')
    print('OK', len(report), 'models; report', out / 'fix_snack_upright.json')


if __name__ == '__main__':
    main()
