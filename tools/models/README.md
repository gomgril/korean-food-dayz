# tools/models — model fix pipeline

Small, repeatable pipeline for fixing individual MLOD models (`source/<Addon>/models/*.p3d`) and
shipping only those models, without re-binarizing the other ~400 models (Binarize is not
run-to-run deterministic, so a full rebuild changes every model).

Python: any Python 3 works (stdlib only, Pillow is not needed). Used and tested with Blender 5.2's
bundled interpreter (`<Blender>\5.2\python\bin\python.exe`, Python 3.13).

## Files

| File | Purpose |
|---|---|
| `mlod045.py` | Vendored, unchanged copy of the lossless MLOD reader/writer from the old project (`work\kf-fix045\mlod045.py`; origin + sha256 in its header). |
| `modelfix.py` | Edit helpers on top of it. **All coordinates are file coordinates (x, y, z), Y up.** |
| `build-changed.ps1` | Binarize only the listed models, overlay onto the base PBO, repack, sign, verify, diff. |
| `fixes/*.py` | One script per fix. Each backs up the originals first and always derives from them. |
| `originals/<Addon>/models/` | Untouched copies of models before a fix (made by the fix scripts). |
| `base/` | Backup of the 0.4.8 base PBOs (+ .bisign) used as the default overlay base. |
| `reports/` | JSON reports written by fix scripts. |
| `out/`, `work/` | Build output / scratch (ignored by git). |

## modelfix.py

```python
import sys; sys.path.insert(0, r"...\tools\models")
import modelfix as mf
m = mf.load(r"source\KF_Pantry\models\x.p3d")
m.summary()                     # LODs, counts, bounds, selections, memory points
m.rotate('x', 180)              # all LODs incl. geometry + memory; normals follow
m.translate((0, .01, 0)); m.scale(1.1, pivot=(0, 0, 0))
m.transform(matrix, translate, pivot, lods=None)   # generic; mirror (det<0) also flips face winding
m.map_uv(lambda u, v: (u, 1 - v), texture=r"KF_Pantry\data\a_co.paa")  # UVs of faces with a texture
m.set_face_uv(lod, face_index, [(u, v), ...])
m.retexture(old, new, material=None)                 # change texture path of matching faces
m.set_face_texture(lod, face_index, texture, material=None)
m.add_face(lod, [(x,y,z)...], texture, material, uv, selections=('component01',))
m.remove_faces(lod, lambda i, f: ...)
m.save(r"out.p3d")              # re-reads and checks LOD/face/selection/memory-point structure
```

`lods=` accepts `None` (all), `'visual'`, resolutions (`1`, `mf.GEOMETRY`, `mf.MEMORY`) or LOD dicts.
Named selections (incl. memory point names) are always kept; load+save without edits is
byte-identical (checked on 60 models).

CLI: `python modelfix.py info|compare|rotate|translate|retexture ...` (see `--help`).

## build-changed.ps1

```powershell
powershell -ExecutionPolicy Bypass -File tools\models\build-changed.ps1 -Addon KF_Pantry `
    -Models pepero_open,yanggaeng_open -PrivateKey <key.biprivatekey> `
    [-Files data\x_co.paa,data\x.rvmat] [-OutDir ...] [-AllowTextChanges] [-KeepWork]
```
The signing key is `-PrivateKey` or `$env:KF_SIGN_KEY` (the matching `.bikey` must sit next to it).
Never copy the private key into the repo.

1. Base = `tools\models\base\<Addon>.pbo` (copied from `@KoreanFood\Addons` on first use), extracted with BankRev.
2. Stages only the listed MLODs + `model.cfg` and binarizes them in one Binarize run (`-silent -always src dst *.p3d`, as build-full.ps1); every output must start with `ODOL`.
3. Overlays the models, the `-Files` (.paa/.rvmat), and config.cpp/scripts/stringtable.csv from source (as repack.ps1).
4. FileBank `-property prefix=<Addon>`, DSSignFile with the private key, DSCheckSignatures.
5. Unpacks the result and hash-compares every file with the base. Fails if anything else changed, if an intended file did not change, or if the PBO prefix differs. Text files that differ from base fail unless `-AllowTextChanges`.

Output: `out\Addons\<Addon>.pbo` (+ .bisign), `out\Keys\*.bikey`, `out\build-changed-<Addon>.json`.
It never writes the repo's `@KoreanFood\Addons`; copy the output there after review.

## Rendering

`korean-food-dayz-review\render_review.py` gained `--src <root>` / `--out <dir>` and comma lists in `--only`:

```
blender.exe -b --factory-startup --python render_review.py -- --src <root with KF_Pantry\models> --out <dir> --force
```
