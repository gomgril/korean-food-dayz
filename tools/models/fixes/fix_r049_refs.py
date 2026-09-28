"""0.4.9 "refs" fix: re-texture products from the reference photos the user supplied
(tools/models/textures/refs-user/, git-ignored):

  doenjang_pack_front_and_bowl.webp  -> doenjangblock (closed pack) + doenjangblock_open (opened pack)
  mochagold_sticks_front.png          -> coffeemix_open (opened Maxim Mocha Gold stick), front
  mochagold_stick_back.webp           -> coffeemix_open, back (redrawn cleanly, no wrinkles / glare)
  whitegold_box_and_sticks.webp       -> whitegoldcoffee: cream + gold restyle of group 4's back / ends / top / bottom

Runs inside Blender (bpy + numpy, text via r049_compose with Malgun Gothic / Georgia / Arial from C:\\Windows\\Fonts):

  "<Blender>\\blender.exe" -b --factory-startup --python tools/models/fixes/fix_r049_refs.py -- [--only doenjang,stick,whitegold] [--no-p3d]

  --only    subset of the three jobs (default: all)
  --no-p3d  write the textures only, leave every p3d untouched (preview / no-op for models)

What it does (every model is rebuilt from tools/models/originals, so re-runs never accumulate):
* doenjangblock (closed, 0.10 x 0.13 m): the print faces (the shared 4-pouch photo atlas
  r043_freezedriedsoup_four_pouches_*) get r049_refs_doenjang_pack_co.paa: a clean redraw of the real
  "미소 된장국 SOYBEAN PASTE SOUP" pack (bowl photo cropped from the user's photo, expiry line, red 간편 집밥
  badge, title, teal icon row, crimped seals) on the left half, a plausible back (조리방법, info table,
  recycling mark, barcode) on the right half. Planar UV (front: u grows with +x, back mirrored so it reads
  from behind), exact physical aspect. Other faces untouched. The other soup packs keep the shared atlas.
* doenjangblock_open: built by group 3's fix_opened_contents.fix() (0.09 m width, freeze-dried block, new
  contents texture - all kept), then its print faces get r049_refs_doenjang_open_co.paa: the same pack art
  drawn at the opened pack's 0.09 m width with the top seal torn off (lower 0.12 of the 0.13 m pack).
* coffeemix_open: built by fix_opened_contents.fix() (powder contents kept), then the stick print faces
  (the 3-sticks photo batch02_19_CoffeeMix_front_co, squeezed ~3x and with transparent photo background)
  get r049_refs_mochagold_stick_co.paa: front (green EASY CUT! tab, vertical Maxim logo, 모카골드 마일드,
  coffee cup, gold crimp) | back (HACCP on the green end, 비닐류 OTHER, 중량 : 12 g, 스틱 끝부분이 날카로우니
  주의하세요., 유통기한, 동서식품, gold crimp) redrawn from the photos.
* whitegoldcoffee: group 4's box atlas (fix_packaging.build_box_texture) rebuilt with a White Gold theme
  (cream background, gold bands instead of the sampled peach / brown) as r049_refs_whitegold_box_co.paa and
  mapped with group 4's own remap_box (same rects). The front keeps its original art (it already is the
  clean Maxim 화이트골드 box print).
coffeemix (Mocha Gold box) is left as group 4 made it (colours already match the yellow stick);
coffeemix_cup / whitegoldcoffee_cup / *_drink show no stick print (checked), so nothing else changes.

Run order: AFTER fix_opened_contents.py and fix_packaging.py. A re-run of either of those rewrites
coffeemix_open / doenjangblock_open / whitegoldcoffee without this fix -> run this script again afterwards.
PNG sources: tools/models/textures/refs/, PAA: source/KF_Pantry/data/r049_refs_*_co.paa,
report: tools/models/reports/fix_r049_refs.json.
"""
import bpy
import sys, os, math, json, shutil, hashlib
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
import modelfix as mf  # noqa: E402
import r049_compose as rc  # noqa: E402

ADDON = 'KF_Pantry'
SRC = REPO / 'source' / ADDON / 'models'
DATA = REPO / 'source' / ADDON / 'data'
ORIG = TOOLS / 'originals' / ADDON / 'models'
REFS = TOOLS / 'textures' / 'refs-user'
TEXOUT = TOOLS / 'textures' / 'refs'
WORK = TOOLS / 'work' / 'refs'
TEXPFX = 'KF_Pantry\\data\\'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {'doenjang', 'stick', 'whitegold'}
NO_P3D = '--no-p3d' in argv

TEX_SIZE = 1024
MARGIN_PX = 3          # edge-extended gutter around each half of a front|back texture


# =============================================================== small helpers
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def backup(name):
    b = ORIG / (name + '.p3d')
    if not b.exists():
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / (name + '.p3d'), b)
    return b


_xf = {}


def xfont(fname):
    if fname not in _xf:
        _xf[fname] = bpy.data.fonts.load(os.path.join(rc.FONT_DIR, fname), check_existing=True)
    return _xf[fname]


def txt(cv, s, x, y, size, color, bold=False, align='left', anchor='top', font=None, rot=0.0, maxw=None,
        char_spacing=1.0):
    """Canvas text with optional font file, rotation (degrees, + = counter-clockwise as seen) and max width."""
    sx = 1.0
    if maxw is not None:
        w = twidth(cv, s, size, bold, font, char_spacing)
        sx = min(1.0, maxw / w) if w > 0 else 1.0
    ob = cv.text(s, x, y, size, color, bold=bold, align=align, anchor=anchor, scale_x=sx, char_spacing=char_spacing)
    if font:
        ob.data.font = xfont(font)
    if rot:
        ob.rotation_euler = (0.0, 0.0, math.radians(rot))
    return ob


def twidth(cv, s, size, bold=False, font=None, char_spacing=1.0):
    ob = cv.text(s, 0, 0, size, '#000000', bold=bold, char_spacing=char_spacing)
    if font:
        ob.data.font = xfont(font)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    xs = [v.co.x for v in me.vertices]
    w = (max(xs) - min(xs)) * size if xs else 0.0
    ob.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    return w


def mix(c0, c1, t):
    a, b = rc.hex2rgb(c0), rc.hex2rgb(c1)
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def grad_strips(cv, x, y, w, h, stops, n=80, axis='x'):
    """Linear gradient as n strips. stops = [(t, '#rrggbb'), ...] with t in 0..1 along `axis`."""
    for k in range(n):
        t = (k + 0.5) / n
        for j in range(len(stops) - 1):
            if stops[j][0] <= t <= stops[j + 1][0]:
                f = (t - stops[j][0]) / max(1e-6, stops[j + 1][0] - stops[j][0])
                col = mix(stops[j][1], stops[j + 1][1], f)
                break
        else:
            col = rc.hex2rgb(stops[-1][1])
        if axis == 'x':
            cv.rect(x + w * k / n, y, w / n + 0.6, h, col)
        else:
            cv.rect(x, y + h * k / n, w, h / n + 0.6, col)


def ellipse(cv, cx, cy, rx, ry, color, alpha=1.0, seg=64):
    return cv.poly([(cx + rx * math.cos(2 * math.pi * i / seg), cy + ry * math.sin(2 * math.pi * i / seg))
                    for i in range(seg)], color, alpha)


def ring(cv, cx, cy, r0, r1, color, a0=0.0, a1=360.0, seg=48, sy=1.0):
    polys = []
    for i in range(seg):
        t0 = math.radians(a0 + (a1 - a0) * i / seg); t1 = math.radians(a0 + (a1 - a0) * (i + 1) / seg)
        p = [(cx + r0 * math.cos(t0), cy + r0 * math.sin(t0) * sy), (cx + r1 * math.cos(t0), cy + r1 * math.sin(t0) * sy),
             (cx + r1 * math.cos(t1), cy + r1 * math.sin(t1) * sy), (cx + r0 * math.cos(t1), cy + r0 * math.sin(t1) * sy)]
        area = sum(p[k][0] * p[(k + 1) % 4][1] - p[(k + 1) % 4][0] * p[k][1] for k in range(4))
        polys.append(p[::-1] if area > 0 else p)
    return cv._mesh(polys, cv._mat(color))


def two_halves(front, back, size=TEX_SIZE):
    """front | back, each resampled into one half of a size x size texture with an edge-extended gutter."""
    out = np.zeros((size, size, 4), np.float32)
    half = size // 2
    for k, art in enumerate((front, back)):
        inner = rc.resample(art, half - 2 * MARGIN_PX, size)
        padded = np.pad(inner, ((0, 0), (MARGIN_PX, MARGIN_PX), (0, 0)), mode='edge')
        out[:, k * half:(k + 1) * half] = padded
    out[..., 3] = 1
    return out


U_EDGE = MARGIN_PX / TEX_SIZE


def write_texture(arr, stem, designs=()):
    TEXOUT.mkdir(parents=True, exist_ok=True)
    png = TEXOUT / (stem + '.png')
    rc.save_png(arr, str(png))
    for name, d in designs:
        rc.save_png(d, str(TEXOUT / ('%s_%s_design.png' % (stem, name))))
    paa = DATA / (stem + '.paa')
    rc.png2paa(str(png), str(paa))
    print('R049REFS texture', stem, arr.shape[1], 'x', arr.shape[0])
    return TEXPFX + stem + '.paa', png, paa


def planar_front_back(m, pred, newtex):
    """Re-point faces matching pred(face) to newtex with a planar UV: front (centre z < 0) -> left half,
    u grows with +x; back (z > 0) -> right half, mirrored so it reads from behind; v = 0 at the top."""
    counts = {}
    for lod in m.visual_lods():
        V = lod['vertices']
        fs = [f for f in lod['faces'] if pred(f)]
        if not fs:
            continue
        xs = [V[c[0]][0] for f in fs for c in f['corners']]
        ys = [V[c[0]][1] for f in fs for c in f['corners']]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        nf = nb = 0
        for f in fs:
            back = sum(V[c[0]][2] for c in f['corners']) / len(f['corners']) > 0
            nc = []
            for vi, ni, _, _ in f['corners']:
                t = (V[vi][0] - x0) / (x1 - x0)
                if back:
                    t = 1.0 - t
                u = (0.5 if back else 0.0) + U_EDGE + t * (0.5 - 2 * U_EDGE)
                v = (y1 - V[vi][1]) / (y1 - y0)
                nc.append((vi, ni, u, v))
            f['corners'] = nc
            f['texture'] = newtex
            nb += back; nf += not back
        counts['lod%g' % lod['resolution']] = dict(front=nf, back=nb, x=[round(x0, 4), round(x1, 4)], y=[round(y0, 4), round(y1, 4)])
    return counts


def check_geometry(a, b):
    """same vertices / normals / face vertex order / tags / memory points; only uv + texture may differ."""
    for la, lb in zip(a.lods, b.lods):
        assert la['vertices'] == lb['vertices'] and la['normals'] == lb['normals']
        assert len(la['faces']) == len(lb['faces'])
        for fa, fb in zip(la['faces'], lb['faces']):
            assert [c[:2] for c in fa['corners']] == [c[:2] for c in fb['corners']]
            assert fa['material'] == fb['material']
    assert a.memory_points() == b.memory_points()


# =============================================================== doenjang soup pack
INK = '#2a2b2b'
TEAL = '#3b8b7f'
RED = '#d6343a'
PACK = '#f1f3f2'
SEAL = '#e4e7e6'
SEAL_LINE = '#cdd2d0'
SIDE_W, CRIMP_H = 42, 92


def bowl_png():
    """the soup bowl (top view) cut out of the user's photo as a round image with a soft edge."""
    out = WORK / 'doenjang_bowl.png'
    a = rc.load_png(str(REFS / 'doenjang_pack_front_and_bowl.webp'))
    cx, cy, r = 463, 331, 106          # soup + white bowl rim, photo pixels
    c = a[cy - r:cy + r, cx - r:cx + r].copy()
    c = rc.resample(c, 4 * r, 4 * r)
    n = c.shape[0]
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    d = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    # brighter and a little warmer, like the printed photo on the pack
    c[..., :3] = np.clip(c[..., :3] * np.array([1.30, 1.26, 1.12], np.float32) + 0.03, 0, 1)
    c[..., 3] = np.clip((1.0 - d) / 0.025, 0, 1)
    WORK.mkdir(parents=True, exist_ok=True)
    rc.save_png(c, str(out))
    return str(out)


def pack_seals(cv, W, H):
    for x in (0, W - SIDE_W):
        cv.rect(x, 0, SIDE_W, H, SEAL)
        cv.rects([(x, y, SIDE_W, 2.2) for y in range(CRIMP_H, H - CRIMP_H, 9)], SEAL_LINE)
    for y0 in (0, H - CRIMP_H):
        cv.rect(0, y0, W, CRIMP_H, SEAL)
        cv.rects([(0, y0 + k, W, 3.2) for k in range(7, CRIMP_H - 4, 10)], SEAL_LINE)
    cv.rect(0, CRIMP_H - 2, W, 2, '#d7dbd9')
    cv.rect(0, H - CRIMP_H, W, 2, '#d7dbd9')


def doenjang_front(W, H=1300, bowl=None):
    cv = rc.Canvas(W, H, bg=PACK)
    # soup photo (round bowl, top cut by the seal as on the real pack)
    D = 0.56 * 1000
    cv.image(bowl, (0, 0, 1, 1), W / 2 - D / 2, 20, D, D)
    txt(cv, '2023.05.18까지', W / 2, 592, 40, INK, bold=True, align='center')
    txt(cv, '조리예', W - SIDE_W - 34, 606, 24, '#5d6060', align='right')
    # 간편 집밥 badge
    by = 715
    cv.circle(W / 2, by, 64, RED)
    cv.circle(W / 2, by, 57, '#ffffff')
    txt(cv, '간편', W / 2, by - 36, 31, RED, bold=True, align='center')
    txt(cv, '집밥', W / 2, by + 2, 31, RED, bold=True, align='center')
    # title
    w1 = twidth(cv, '미소', 100); w2 = twidth(cv, '된장국', 152, bold=True)
    gap = 24
    x = W / 2 - (w1 + gap + w2) / 2
    txt(cv, '미소', x, 928, 100, INK, anchor='baseline')
    txt(cv, '된장국', x + w1 + gap, 928, 152, INK, bold=True, anchor='baseline')
    txt(cv, 'SOYBEAN PASTE SOUP', W / 2, 948, 30, '#333535', align='center', font='arialbd.ttf', char_spacing=1.35)
    # icon row
    x0, y0, rw, rh = 108, 1004, W - 216, 92
    fr = [0.14, 0.17, 0.25, 0.22, 0.22]
    cv.rect(x0, y0, rw, rh, '#f7f9f8')
    cv.frame(x0, y0, rw, rh, TEAL, t=3)
    xs = [x0]
    for f in fr:
        xs.append(xs[-1] + f * rw)
    for xx in xs[1:-1]:
        cv.rect(xx - 1, y0 + 8, 2, rh - 16, '#9cc5bd')
    c0 = (xs[0] + xs[1]) / 2          # mountain icon
    cv.poly([(c0 - 30, y0 + 52), (c0 - 10, y0 + 18), (c0 + 4, y0 + 40), (c0 + 14, y0 + 26), (c0 + 30, y0 + 52)], TEAL)
    txt(cv, '원료', c0, y0 + 58, 19, TEAL, align='center')
    c1 = (xs[1] + xs[2]) / 2          # factory icon
    cv.rect(c1 - 24, y0 + 24, 48, 30, TEAL)
    cv.rects([(c1 - 17 + 12 * k, y0 + 31, 7, 16) for k in range(3)], '#f7f9f8')
    cv.rect(c1 - 24, y0 + 16, 12, 10, TEAL)
    txt(cv, '제조시설', c1, y0 + 58, 19, TEAL, align='center', maxw=xs[2] - xs[1] - 10)
    cv.rect(xs[2] + 6, y0 + 6, xs[3] - xs[2] - 12, rh - 12, TEAL)
    c2 = (xs[2] + xs[3]) / 2
    txt(cv, '뜨거운물', c2, y0 + 13, 27, '#ffffff', bold=True, align='center', maxw=xs[3] - xs[2] - 20)
    txt(cv, '바로', c2 - 22, y0 + 47, 27, '#ffffff', bold=True, align='center')
    txt(cv, '(150mL)', c2 + 38, y0 + 56, 15, '#ffffff', align='center')
    c3 = (xs[3] + xs[4]) / 2
    txt(cv, '10g', c3, y0 + 6, 44, TEAL, bold=True, align='center')
    txt(cv, '(51 kcal)', c3, y0 + 60, 17, TEAL, align='center')
    c4 = (xs[4] + xs[5]) / 2
    txt(cv, '실온', c4, y0 + 12, 26, TEAL, align='center')
    txt(cv, '보관', c4, y0 + 48, 26, TEAL, align='center')
    txt(cv, '된장 43.3%  |  알갱이유부 26.6%  |  건미역 3.4%', W / 2, 1112, 24, '#3c3e3e', align='center',
        maxw=W - 2 * SIDE_W - 120)
    pack_seals(cv, W, H)
    return cv.render(1300)


def doenjang_back(W, H=1300):
    cv = rc.Canvas(W, H, bg=PACK)
    x0, x1 = SIDE_W + 48, W - SIDE_W - 48
    txt(cv, '미소 된장국', W / 2, 128, 72, INK, bold=True, align='center')
    txt(cv, 'SOYBEAN PASTE SOUP', W / 2, 228, 26, '#333535', align='center', font='arialbd.ttf', char_spacing=1.35)
    # 조리방법
    py = 290
    cv.rect(x0, py, x1 - x0, 236, TEAL, r=16)
    txt(cv, '조리방법', x0 + 26, py + 18, 34, '#ffffff', bold=True)
    for k, s in enumerate(('① 봉지를 뜯어 블록을 컵이나 그릇에 넣습니다.', '② 뜨거운 물 150 mL를 붓습니다.',
                           '③ 잘 저어 10초 후 드세요.')):
        txt(cv, s, x0 + 26, py + 76 + k * 50, 27, '#ffffff', maxw=x1 - x0 - 52)
    # info table
    rows = [('제품명', '미소 된장국'), ('식품유형', '즉석조리식품 (동결건조)'), ('내용량', '10 g (51 kcal)'),
            ('원재료명', '된장, 알갱이유부, 건미역, 대파'), ('보관방법', '직사광선을 피해 실온 보관')]
    ty = 566
    cv.rect(x0, ty - 8, x1 - x0, len(rows) * 66 + 16, '#ffffff', r=10)
    for k, (a, b) in enumerate(rows):
        y = ty + k * 66
        txt(cv, a, x0 + 22, y + 14, 25, TEAL, bold=True)
        txt(cv, b, x0 + 190, y + 14, 25, INK, maxw=x1 - x0 - 210)
        if k:
            cv.rect(x0 + 14, y, x1 - x0 - 28, 2, '#d5dcda')
    # recycling mark, expiry note, barcode
    rx, ry = x0 + 70, 1030
    for a in range(3):
        t0 = math.radians(-90 + 120 * a); t1 = math.radians(-90 + 120 * (a + 1))
        cv.line(rx + 58 * math.cos(t0), ry + 58 * math.sin(t0), rx + 58 * math.cos(t1), ry + 58 * math.sin(t1), INK, t=7)
    txt(cv, '비닐류', rx, ry - 6, 22, INK, bold=True, align='center')
    txt(cv, 'OTHER', rx, ry + 44, 20, INK, align='center', font='arialbd.ttf')
    txt(cv, '유통기한 : 앞면 표기일까지', x0 + 170, 1000, 24, INK, maxw=x1 - x0 - 480)
    txt(cv, '뜨거운 물 사용 시 화상에 주의하세요.', x0 + 170, 1044, 22, '#555858', maxw=x1 - x0 - 480)
    cv.barcode(x1 - 280, 985, 270, 110, '8809421520019')
    pack_seals(cv, W, H)
    return cv.render(1300)


def job_doenjang(report):
    bowl = bowl_png()
    # closed pack 0.10 x 0.13 m
    f, b = doenjang_front(1000, bowl=bowl), doenjang_back(1000)
    tex_c, png_c, paa_c = write_texture(two_halves(f, b), 'r049_refs_doenjang_pack_co', [('front', f), ('back', b)])
    # opened pack 0.09 m wide, top seal torn off: lower 1200 of 1300 design units
    fo, bo = doenjang_front(900, bowl=bowl), doenjang_back(900)
    cut = lambda a: a[int(round(a.shape[0] * 100 / 1300)):]
    fo, bo = cut(fo), cut(bo)
    tex_o, png_o, paa_o = write_texture(two_halves(fo, bo), 'r049_refs_doenjang_open_co', [('front', fo), ('back', bo)])
    if NO_P3D:
        return
    # closed: from the original
    orig = backup('doenjangblock')
    m = mf.load(orig)
    counts = planar_front_back(m, lambda f: 'freezedriedsoup_four_pouches' in f['texture'].lower(), tex_c)
    save(m, 'doenjangblock', orig, report, texture=tex_c, png=png_c, paa=paa_c, faces=counts,
         note='print faces re-pointed from the shared 4-pouch atlas; geometry unchanged')
    # opened: group 3's result (from its original) + new print
    import fix_opened_contents as g3
    m, info = g3.fix('doenjangblock_open')
    counts = planar_front_back(m, lambda f: 'doenjangblock_front_group' in f['texture'].lower(), tex_o)
    save(m, 'doenjangblock_open', ORIG / 'doenjangblock_open.p3d', report, texture=tex_o, png=png_o, paa=paa_o,
         faces=counts, group3=info, note='fix_opened_contents.fix() (width 0.09 m, freeze-dried block) + new print')


# =============================================================== Maxim Mocha Gold stick
GOLD_STOPS = [(0.0, '#b47a0b'), (0.14, '#e2aa18'), (0.42, '#f9d648'), (0.60, '#f6cd2e'), (0.86, '#dca116'),
              (1.0, '#b07509')]
GREEN_STOPS = [(0.0, '#0a6a28'), (0.3, '#17913a'), (0.55, '#22a444'), (1.0, '#0b6c29')]
BROWN = '#6a3410'
SW, SH = 440, 1200        # stick 0.044 x 0.12 m in 0.1 mm units
TAB_H, CRIMP_Y = 165, 1122


def stick_body(cv, green_extra=None):
    grad_strips(cv, 0, 0, SW, SH, GOLD_STOPS, n=88)
    grad_strips(cv, 0, 0, SW, TAB_H, GREEN_STOPS, n=44)
    cv.rect(0, TAB_H - 3, SW, 7, '#e8c65c')
    if green_extra:
        green_extra(cv)
    # gold crimp (sealed end)
    cv.rect(0, CRIMP_Y, SW, SH - CRIMP_Y, '#c9a14a')
    cv.rects([(x, CRIMP_Y + 4, 4, SH - CRIMP_Y - 4) for x in range(3, SW, 12)], '#e9cc79')
    cv.rects([(x + 6, CRIMP_Y + 4, 3, SH - CRIMP_Y - 4) for x in range(3, SW, 12)], '#9c782b')
    cv.rect(0, CRIMP_Y, SW, 4, '#a07c2e')


def stick_front():
    cv = rc.Canvas(SW, SH, bg='#f2c524')

    def tab(cv):
        txt(cv, 'EASY', 40, 22, 50, '#fff8c8', font='ariblk.ttf', rot=6)
        txt(cv, 'CUT!', 74, 72, 50, '#fff8c8', font='ariblk.ttf', rot=6)
        cv.frame(96, 132, 30, 22, '#f4e27c', t=3, r=4)
        for k in range(15):
            cv.circle(146 + 18 * k, 143 - 1.2 * k, 3.6, '#f4e27c', seg=12)
    stick_body(cv, tab)
    # Maxim logo, vertical (reads top -> bottom) with a brown drop shadow
    size = 520 / (twidth(cv, 'Maxim', 1.0, font='georgiab.ttf') or 1)
    for col, d in ((BROWN, 7), ('#fff7e4', 0)):
        txt(cv, 'Maxim', 178 + d, 470 + d, size, col, align='center', anchor='center', font='georgiab.ttf', rot=-90)
    txt(cv, '모카골드 마일드', 322, 510, 52, BROWN, bold=True, align='left', anchor='center', rot=-90, maxw=420)
    txt(cv, '커피믹스', 390, 560, 34, BROWN, bold=True, align='left', anchor='center', rot=-90)
    # coffee cup (side view) above the crimp
    ellipse(cv, 220, 1030, 205, 110, '#fff2cc', alpha=0.45)
    ellipse(cv, 222, 1086, 188, 30, '#f8f1e1')
    ellipse(cv, 222, 1082, 120, 17, '#e3d6bb')
    ring(cv, 348, 960, 30, 46, '#f6efe2', a0=-100, a1=110, seg=24, sy=1.1)
    body = [(92, 902)] + [(222 - 130 * math.cos(math.radians(a)), 902 + 170 * math.sin(math.radians(a)) ** 1.6)
                          for a in range(0, 181, 6)] + [(352, 902)]
    cv.poly(body, '#fdfbf6')
    cv.poly([(300, 910), (348, 906), (330, 1010), (290, 1062), (292, 990)], '#e7dfcf', alpha=0.8)
    ellipse(cv, 222, 902, 131, 30, '#fdfbf6')
    ellipse(cv, 222, 905, 118, 24, '#b88150')
    ellipse(cv, 206, 903, 64, 12, '#e0bd8e')
    ellipse(cv, 240, 908, 38, 7, '#cd9e6a')
    return cv.render(1400)


def stick_back():
    cv = rc.Canvas(SW, SH, bg='#f2c524')
    ink = '#3b2410'

    def tab(cv):
        cv.circle(110, 84, 60, '#ffffff')
        cv.circle(110, 84, 52, '#cde9ef')
        txt(cv, 'HACCP', 118, 84, 30, '#2a73b0', align='center', anchor='center', font='arialbd.ttf', rot=-90)
        txt(cv, '식품안전관리인증', 70, 84, 12, '#2a73b0', align='center', anchor='center', rot=-90)
        txt(cv, '제조원 :', 392, 22, 26, '#ffffff', align='left', anchor='center', rot=-90)
    stick_body(cv, tab)
    # fin seal down the middle of the back
    cv.rect(217, TAB_H + 4, 7, CRIMP_Y - TAB_H - 4, '#d9a318')
    cv.rect(224, TAB_H + 4, 3, CRIMP_Y - TAB_H - 4, '#fbe27e')
    # perforation
    for k in range(29):
        cv.circle(10 + 15 * k, 184, 3, '#7a5418', seg=10)
    # left half: recycling mark, weight / warning, expiry (all reading top -> bottom)
    rx, ry = 120, 262
    for a in range(3):
        t0 = math.radians(120 * a); t1 = math.radians(120 * (a + 1))
        cv.line(rx + 50 * math.cos(t0), ry + 50 * math.sin(t0), rx + 50 * math.cos(t1), ry + 50 * math.sin(t1), ink, t=7)
    txt(cv, '비닐류', rx + 4, ry, 17, ink, bold=True, align='center', anchor='center', rot=-90)
    txt(cv, 'OTHER', rx - 70, ry, 20, ink, align='center', anchor='center', font='arialbd.ttf', rot=-90)
    txt(cv, '• 중량 : 12 g', 158, 360, 44, ink, align='left', anchor='center', rot=-90)
    txt(cv, '• 스틱 끝부분이 날카로우니 주의하세요.', 158, 640, 27, ink, align='left', anchor='center', rot=-90, maxw=470)
    txt(cv, '유통기한 :', 62, 360, 32, ink, align='left', anchor='center', rot=-90)
    txt(cv, '2024.08.01 14:16 AG27', 62, 560, 34, '#20140a', bold=True, align='left', anchor='center', rot=-90, maxw=420)
    txt(cv, '까지', 62, 1010, 28, ink, align='left', anchor='center', rot=-90)
    # right half: maker, packaging note, sugar note
    txt(cv, '동서식품', 392, 150 + TAB_H - 120, 48, '#4d260c', bold=True, align='left', anchor='center', rot=-90)
    cv.frame(252, 470, 104, 600, ink, t=3, r=6)
    txt(cv, '이 제품은 재활용이 용이한 포장재를 사용하였습니다.', 326, 486, 21, ink, align='left', anchor='center',
        rot=-90, maxw=570)
    txt(cv, '(• 사용코드 : T100503  • 유효기간 : 2025-03-16)', 282, 486, 21, ink, align='left', anchor='center',
        rot=-90, maxw=570)
    txt(cv, '설탕조절부문', 400, 760, 30, ink, align='left', anchor='center', rot=-90, maxw=330)
    return cv.render(1400)


def job_stick(report):
    f, b = stick_front(), stick_back()
    tex, png, paa = write_texture(two_halves(f, b), 'r049_refs_mochagold_stick_co', [('front', f), ('back', b)])
    if NO_P3D:
        return
    import fix_opened_contents as g3
    m, info = g3.fix('coffeemix_open')
    counts = planar_front_back(m, lambda f: 'coffeemix_front' in f['texture'].lower(), tex)
    save(m, 'coffeemix_open', ORIG / 'coffeemix_open.p3d', report, texture=tex, png=png, paa=paa, faces=counts,
         group3=info, note='fix_opened_contents.fix() (powder contents) + new stick print front|back')


# =============================================================== Maxim White Gold box
WG_CREAM = 'f6efde'
WG_GOLD = 'c29a4e'


def job_whitegold(report):
    import fix_packaging as fp
    name = 'whitegoldcoffee'
    orig = fp.backup(name)
    m = mf.load(orig)
    theme = dict(fp.THEMES[name])
    theme.update(bg=fp.hexc(WG_CREAM), back_band=(fp.hexc(WG_GOLD), 0.035), end_band=(fp.hexc(WG_GOLD), 0.1),
                 accent=fp.hexc('9a6a2a'), info_bg=(1.0, 1.0, 1.0))
    sR, sV = fp.front_orientation(m)
    atlas, rects = fp.build_box_texture(name, m, theme)
    # group 4's layout must be unchanged, so its UVs and ours agree side for side
    prev = json.loads((TOOLS / 'reports' / 'fix_packaging.json').read_text(encoding='utf8'))
    prev_rects = {e['model']: e.get('rects') for e in prev}.get(name)
    assert prev_rects is None or {k: list(v) for k, v in rects.items()} == prev_rects, (rects, prev_rects)
    tex, png, paa = write_texture(atlas, 'r049_refs_whitegold_box_co')
    if NO_P3D:
        return
    counts = fp.remap_box(m, rects, tex, sR, sV)
    target = save(m, name, orig, report, texture=tex, png=png, paa=paa,
                  faces={'%g_%s' % k: n for k, n in counts.items()},
                  note="group 4's box atlas + remap_box with a cream/gold White Gold theme; front art unchanged")
    fp.verify(orig, target, tex)


# =============================================================== save / main
def save(m, name, orig, report, **info):
    target = SRC / (name + '.p3d')
    before = sha(target)
    digest = m.save(target)
    chk = mf.load(target)
    if name in ('doenjangblock', 'whitegoldcoffee'):
        check_geometry(mf.load(orig), chk)
    for k in ('png', 'paa'):
        if k in info:
            info[k] = str(Path(info[k]).relative_to(REPO)).replace('\\', '/')
    report.append(dict(model='%s/models/%s.p3d' % (ADDON, name), original=str(orig.relative_to(REPO)).replace('\\', '/'),
                       original_sha256=sha(orig), sha256_before=before, sha256_after=digest,
                       lod1_bounds=[[round(a, 5) for a in ax] for ax in mf.Model.bounds(chk.lod(1))],
                       memory_points_unchanged=chk.memory_points() == mf.load(orig).memory_points(), **info))
    print('R049REFS saved %-20s %s' % (name, info.get('faces')))
    return target


def main():
    report = []
    if 'doenjang' in ONLY:
        job_doenjang(report)
    if 'stick' in ONLY:
        job_stick(report)
    if 'whitegold' in ONLY:
        job_whitegold(report)
    if not NO_P3D:
        rp = TOOLS / 'reports' / 'fix_r049_refs.json'
        old = []
        if rp.exists() and ONLY != {'doenjang', 'stick', 'whitegold'}:
            done = {r['model'] for r in report}
            old = [r for r in json.loads(rp.read_text(encoding='utf8')) if r['model'] not in done]
        rp.write_text(json.dumps(old + report, indent=1, default=str), encoding='utf8')
        print('R049REFS report', rp)
    print('R049REFS_DONE', len(report), 'models')


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    raise SystemExit(1)
