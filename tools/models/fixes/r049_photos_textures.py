"""r049 group 5 ("photos") texture builder - run by fix_r049_photos.py inside Blender:

  blender -b --factory-startup --python r049_photos_textures.py -- --layout <reports/r049_photos_layout.json> [--only k1,k2] [--no-paa]

Sources are the repo's own .paa files (converted to PNG under tools/models/work/photos_src).
Outputs: tools/models/textures/photos/<key>.png (+ _design.png = the unplaced art) and source/<Addon>/data/r049_photos_*_co.paa
"""
import sys, os, json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r049_compose as rc  # noqa: E402
import r049_photos_layouts as L  # noqa: E402
from r049_photos_layouts import Img, INK, GREY  # noqa: E402

TOOLS = HERE.parent
REPO = TOOLS.parents[1]
SRCDIR = TOOLS / 'work' / 'photos_src'
OUTDIR = TOOLS / 'textures' / 'photos'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
LAYOUT = json.loads(Path(argv[argv.index('--layout') + 1]).read_text(encoding='utf8')) if '--layout' in argv else {}
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
NO_PAA = '--no-paa' in argv

_imgs = {}


def src(texture):
    """'KF_Food\\data\\r044_ref_05_co.paa' -> Img (PNG converted from the repo paa)."""
    if texture in _imgs:
        return _imgs[texture]
    paa = REPO / 'source' / texture.replace('\\', os.sep)
    png = SRCDIR / (texture.replace('\\', '__').replace('.paa', '.png'))
    rc.paa2png(str(paa), str(png))
    import bpy
    im = bpy.data.images.load(str(png), check_existing=True)
    _imgs[texture] = Img(str(png), *im.size)
    return _imgs[texture]


def P(addon, name):
    return '%s\\data\\%s.paa' % (addon, name)


def derived_png(name, arr):
    """save an intermediate image (cleaned crop etc.) and return an Img for it"""
    path = SRCDIR / (name + '.png')
    rc.save_png(arr, str(path))
    return Img(str(path), arr.shape[1], arr.shape[0])


# ------------------------------------------------------------------ image cleanup helpers (numpy)
def blur(a, r):
    """separable box blur x3 (approx gaussian), a: (h, w, c)"""
    out = a.astype(np.float32)
    for _ in range(3):
        for axis in (0, 1):
            c = np.cumsum(np.pad(out, [(r + 1, r) if k == axis else (0, 0) for k in range(out.ndim)], mode='edge'), axis=axis)
            n = out.shape[axis]
            hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
            lo = np.take(c, np.arange(0, n), axis=axis)
            out = (hi - lo) / (2 * r + 1)
    return out


def background_mask(arr, thresh=0.86, sat=0.10, alpha_thresh=0.5):
    """pixels connected to the image border that are near-white/grey studio background or transparent"""
    rgb = arr[..., :3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    cand = ((mn > thresh) & (mx - mn < sat)) | (arr[..., 3] < alpha_thresh)
    h, w = cand.shape
    mask = np.zeros_like(cand)
    mask[0, :] = cand[0, :]; mask[-1, :] = cand[-1, :]; mask[:, 0] = cand[:, 0]; mask[:, -1] = cand[:, -1]
    while True:
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]; grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]; grown[:, :-1] |= mask[:, 1:]
        grown &= cand
        if (grown == mask).all():
            break
        mask = grown
    return mask


def fill_from_neighbours(arr, mask, iters=400):
    """replace masked pixels by repeatedly averaging known neighbours (push-pull style dilation)"""
    a = arr.copy()
    known = ~mask
    a[mask] = 0
    for _ in range(iters):
        if known.all():
            break
        acc = np.zeros_like(a); cnt = np.zeros(mask.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sh = np.roll(np.roll(a, dy, 0), dx, 1); kn = np.roll(np.roll(known, dy, 0), dx, 1)
            acc += sh * kn[..., None]; cnt += kn
        new = (~known) & (cnt > 0)
        a[new] = acc[new] / cnt[new][:, None]
        known = known | new
    # smooth the propagated colours (the flood leaves diagonal streaks)
    b = blur(a, 5)
    a[mask] = b[mask]
    a[..., 3] = 1
    return a


def clean_front(arr, grow=2, **kw):
    m = background_mask(arr, **kw)
    for _ in range(grow):  # eat the anti-aliased fringe
        g = m.copy(); g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]; m = g
    return fill_from_neighbours(arr, m), m


def dark_ink_alpha(arr, lo=0.25, hi=0.62):
    """alpha matte of dark print on a light background (for lifting calligraphy off a shaded photo)"""
    lum = arr[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
    bg = blur(np.maximum(lum, blur(lum[..., None], 6)[..., 0])[..., None], 14)[..., 0]
    rel = lum / np.maximum(bg, 1e-3)
    return np.clip((hi - rel) / (hi - lo), 0, 1)


def recolor_red(arr, region, target, keep=None):
    """map strongly red pixels inside region (x0,y0,x1,y1 px) to `target` colour, keeping their shading."""
    x0, y0, x1, y1 = region
    sub = arr[y0:y1, x0:x1]
    r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
    red = np.clip((r - np.maximum(g, b) - 0.18) / 0.25, 0, 1)
    if keep is not None:
        kx0, ky0, kx1, ky1 = keep
        mk = np.zeros(red.shape, bool)
        mk[max(0, ky0 - y0):max(0, ky1 - y0), max(0, kx0 - x0):max(0, kx1 - x0)] = True
        red[mk] = 0
    shade = np.clip(r / 0.86, 0, 1.25)[..., None]
    tgt = np.array(rc.hex2rgb(target), np.float32)[None, None, :] * shade
    # light pinkish highlight lines become light blue-ish
    sub[..., :3] = sub[..., :3] * (1 - red[..., None]) + np.clip(tgt, 0, 1) * red[..., None]
    arr[y0:y1, x0:x1] = sub
    return arr


def feather(img, box, name, fade=0.10, matte=None, tol=0.18, upscale=1):
    """Cut a pixel box out of img and give it soft alpha edges (fade = fraction of the short side).
    matte: optional background rgb -> pixels close to it become transparent too (lifts art off a flat print)."""
    x0, y0, x1, y1 = box
    a = rc.load_png(img.path)[y0:y1, x0:x1].copy()
    if upscale > 1:
        a = rc.resample(a, a.shape[1] * upscale, a.shape[0] * upscale)
    h, w = a.shape[:2]
    f = max(1.0, fade * min(w, h))
    yy = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None]
    xx = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :]
    al = np.clip(np.minimum(yy, xx) / f, 0, 1)
    if matte is not None:
        d = np.sqrt(((a[..., :3] - np.array(rc.hex2rgb(matte), np.float32)) ** 2).sum(-1))
        al = al * np.clip((d - tol * 0.5) / (tol * 0.5), 0, 1)
    a[..., 3] = al * a[..., 3]
    return derived_png(name, a)


def border_colour(img, box):
    x0, y0, x1, y1 = box
    a = rc.load_png(img.path)[y0:y1, x0:x1, :3]
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    c = np.median(edge, 0)
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in c)


def crop_header(items, panel=None, pad=18, gap=26, r=24, dy=0):
    """header callback: items = [(Img, h_units)] placed in a row, centred, on an optional rounded panel."""
    def draw(cv, W, H, y):
        widths = [h * im.w / im.h for im, h in items]
        total = sum(widths) + gap * (len(items) - 1)
        hmax = max(h for _, h in items)
        x = (W - total) / 2
        if panel:
            cv.rect(x - pad * 2, y + dy, total + pad * 4, hmax + 2 * pad, panel, r=r)
        for (im, h), w in zip(items, widths):
            cv.image(im.path, (0, 0, 1, 1), x, y + dy + pad + (hmax - h) / 2, w, h)
            x += w + gap
        return y + dy + hmax + 2 * pad + 12
    return draw


def stack(*callbacks):
    def draw(cv, W, H, y):
        for c in callbacks:
            y = c(cv, W, H, y)
        return y
    return draw


def text_header(lines):
    """lines: [(text, size, color, outline, t, bold)] centred"""
    def draw(cv, W, H, y):
        for s, size, color, outline, t in lines:
            L.outlined(cv, s, W / 2, y, size, color, outline=outline, t=t, align='center')
            y += size * 1.2
        return y + 10
    return draw


# ------------------------------------------------------------------ output
def tex_dims(entry):
    u0, v0, u1, v1 = entry['rect']
    pw, ph = entry['size_m']
    ideal = (v1 - v0) / (u1 - u0) * 0 + ph / pw * (u1 - u0) / (v1 - v0)  # tex_h / tex_w for uniform density
    if ideal > 1.45:
        return 512, 1024
    if ideal < 0.69:
        return 1024, 512
    return 1024, 1024


def write(key, design, dims=None, rect=None, fill=None):
    e = LAYOUT[key]
    tw, th = dims or tex_dims(e)
    arr = rc.place(design, tw, th, rect or e['rect'], fill=fill)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rc.save_png(design, str(OUTDIR / (key + '_design.png')))
    png = OUTDIR / (Path(e['new'].replace('\\', '/')).stem + '.png')
    rc.save_png(arr, str(png))
    if not NO_PAA:
        paa = REPO / 'source' / e['new'].replace('\\', os.sep)
        rc.png2paa(str(png), str(paa))
    print('R049 wrote %-28s %dx%d -> %s' % (key, tw, th, e['new']))


def write_full(key, arr):
    """textures that are full replacements with the old layout (fronts cleaned in place)."""
    e = LAYOUT[key]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    png = OUTDIR / (Path(e['new'].replace('\\', '/')).stem + '.png')
    rc.save_png(arr, str(png))
    if not NO_PAA:
        rc.png2paa(str(png), str(REPO / 'source' / e['new'].replace('\\', os.sep)))
    print('R049 wrote %-28s %dx%d -> %s (full)' % (key, arr.shape[1], arr.shape[0], e['new']))


def aspect(key):
    w, h = LAYOUT[key]['size_m']
    return h / w


def upscale(arr, f):
    return rc.resample(arr, arr.shape[1] * f, arr.shape[0] * f)


DESIGNS = {}


def design(key):
    def deco(fn):
        DESIGNS[key] = fn
        return fn
    return deco


def header_row(items, gap=26, align='center'):
    """header drawing callback: items = list of callables(cv, x, y) -> (w, h) with known width via 'w' key.
    Each item: dict(kind='img', img=Img, crop=(px), h=..) | dict(kind='text', s=.., size=.., color=.., outline=..)"""
    def draw(cv, W, H, y):
        widths = []
        for it in items:
            if it['kind'] == 'img':
                widths.append(it['h'] * it['img'].aspect(*it['crop']))
            elif it['kind'] == 'text':
                widths.append(cv.text_width(it['s'], it['size'], bold=True) * it.get('scale_x', 1) + it['size'] * 0.1)
            else:
                widths.append(it['w'])
        total = sum(widths) + gap * (len(items) - 1)
        x = (W - total) / 2 if align == 'center' else 60
        hmax = max(it.get('h', it.get('size', 0) * 1.3) for it in items)
        for it, w in zip(items, widths):
            ih = it.get('h', it.get('size', 0) * 1.3)
            yy = y + (hmax - ih) / 2 + it.get('dy', 0)
            if it['kind'] == 'img':
                cv.image(it['img'].path, it['img'].crop(*it['crop']), x, yy, w, it['h'], alpha=it.get('alpha', True))
            elif it['kind'] == 'text':
                L.outlined(cv, it['s'], x, yy, it['size'], it['color'], outline=it.get('outline', '#ffffff'),
                           t=it.get('t'), scale_x=it.get('scale_x', 1), shear=it.get('shear', 0))
            else:
                it['draw'](cv, x, yy, w, ih)
            x += w + gap
        return y + hmax + 16
    return draw


# ====================================================================== designs
NONGSHIM_NOTES = ['개봉 후에는 즉시 조리해 드십시오.', '끓는 물에 조리 시 화상에 주의하십시오.',
                  '본 제품은 소비자분쟁해결기준에 의거 교환 또는 보상받을 수 있습니다.', '부정·불량식품 신고는 국번없이 1399']


GENERIC_NOTES = ['개봉 후에는 가급적 빨리 드십시오.', '직사광선을 피하고 서늘하고 건조한 곳에 보관하십시오.',
                 '본 제품은 소비자분쟁해결기준에 의거 교환 또는 보상받을 수 있습니다.', '부정·불량식품 신고는 국번없이 1399']
RETORT_NOTES = ['조리 시 화상에 주의하십시오.', '전자레인지 조리 시 반드시 전자레인지용 용기에 옮겨 데우십시오.',
                '부풀거나 새는 제품은 드시지 마시고 구입처에서 교환하십시오.', '부정·불량식품 신고는 국번없이 1399']


def ramen_nut(total, kcal, na, carb, sugar, fat, trans, sat, chol, prot, extra=None):
    items = [('나트륨', *na), ('탄수화물', *carb), ('당류', *sugar), ('지방', *fat), ('트랜스지방', trans, ''),
             ('포화지방', *sat), ('콜레스테롤', *chol), ('단백질', *prot)]
    if extra:
        items.append(extra)
    return dict(total=total, kcal=kcal, items=items)


def nongshim(f, logo_box):
    return feather(f, logo_box, 'nongshim_logo_%d' % logo_box[0], fade=0.12, matte='#ffffff', tol=0.25)


def jinhot():
    return src(P('KF_Food', 'r044_jin_hot_back_co'))


def ottogi_logo():
    return feather(jinhot(), (650, 100, 862, 296), 'ottogi_logo', fade=0.02, matte='#ffe600', tol=0.35)


@design('ansung_back')
def d_ansung(key):
    f = src(P('KF_Food', 'r044_ref_05_co'))
    title = feather(f, (116, 182, 398, 266), 'ansung_title', fade=0.05, matte='#ffffff', tol=0.22)
    hanja = feather(f, (254, 262, 373, 296), 'ansung_hanja', fade=0.05, matte='#ffffff', tol=0.22)
    logo = nongshim(f, (140, 112, 230, 156))
    spec = dict(name=key, bg='#e8661f', band='#d4561a', band_line='#b0420c', band_h=0.06, accent='#e8661f', line='#e07a3c',
                nut_color='#4a2b1a',
                header=crop_header([(logo, 60), (title, 104), (hanja, 44)], panel='#ffffff', gap=22),
                steps=['물 550ml(3컵 정도)를 끓입니다.', '면과 스프를 같이 넣고 4분 30초간 더 끓입니다.',
                       '구수한 안성탕면이 완성됩니다.'],
                barcode='8801043014731',
                table=[('제품명', '안성탕면'), ('식품유형', '유탕면'),
                       ('원재료명', '면/소맥분(밀:미국산, 호주산), 팜유(말레이시아산), 감자전분, 변성전분, 정제소금, '
                                  '면류첨가알칼리제(산도조절제), 비타민B2 / 스프/정제소금, 된장분말, 설탕, 양념간장분말, '
                                  '고춧가루, 마늘분말, 후추분말, 건조파, 건조미역'),
                       ('알레르기', '밀, 대두, 계란, 돼지고기, 닭고기, 쇠고기 함유'), ('포장재질', '폴리프로필렌')],
                nutrition=ramen_nut('총 내용량 125 g', '525 kcal', ('1,790 mg', '90%'), ('82 g', '25%'), ('3 g', '3%'),
                                    ('17 g', '31%'), '0 g', ('9 g', '60%'), ('0 mg', '0%'), ('11 g', '20%'),
                                    ('칼슘', '163 mg', '23%')),
                maker_logo=(logo, (0, 0, logo.w, logo.h), 52),
                maker='(주)농심  서울특별시 동작구 여의대방로 112  고객상담실 080-023-5181',
                blocks=[('steps',), ('codes',), ('table',), ('nutrition',), ('maker',)])
    return L.bag_back(spec, aspect(key))


@design('chapagetti_back')
def d_chapagetti(key):
    f = src(P('KF_Food', 'r044_ref_07_co'))
    title = feather(f, (108, 182, 408, 282), 'chapa_title', fade=0.04, matte='#dfe3c6', tol=0.2)
    olive = feather(f, (100, 280, 204, 384), 'chapa_olive', fade=0.08, matte='#dfe3c6', tol=0.2)
    logo = feather(f, (96, 144, 190, 184), 'chapa_logo', fade=0.06, matte='#dfe3c6', tol=0.2)
    spec = dict(name=key, bg='#dfe3c6', band='#b99a4a', band_line='#8c7129', band_h=0.06, accent='#6b4a2b', line='#9c8a5a',
                nut_color='#3b2a1c', panel='#fbfaf3',
                header=crop_header([(logo, 50), (title, 118), (olive, 100)], gap=18, pad=6),
                steps=['물 600ml(3컵 정도)를 끓인 후 면과 후레이크를 넣고 5분 더 끓입니다.',
                       '물 8스푼(약 150ml) 정도만 남기고 따라 버립니다.',
                       '과립스프와 올리브 조미유를 넣고 잘 비벼 드십시오.'],
                barcode='8801043015226',
                table=[('제품명', '짜파게티'), ('식품유형', '유탕면'),
                       ('원재료명', '면/소맥분(밀:호주산, 미국산), 팜유(말레이시아산), 감자전분, 변성전분, 정제소금, '
                                  '올리브유 / 분말스프/춘장분말, 설탕, 양파분말, 캐러멜색소, 볶음양념분말, 건조양배추'),
                       ('알레르기', '밀, 대두, 우유, 쇠고기, 돼지고기 함유'), ('포장재질', '폴리프로필렌')],
                nutrition=ramen_nut('총 내용량 140 g', '610 kcal', ('1,100 mg', '55%'), ('96 g', '30%'), ('7 g', '7%'),
                                    ('20 g', '37%'), '0 g', ('8 g', '53%'), ('5 mg', '2%'), ('11 g', '20%'),
                                    ('칼슘', '162 mg', '23%')),
                maker_logo=(logo, (0, 0, logo.w, logo.h), 44),
                maker='(주)농심  서울특별시 동작구 여의대방로 112  고객상담실 080-023-5181',
                blocks=[('steps',), ('codes',), ('table',), ('nutrition',), ('maker',)])
    return L.bag_back(spec, aspect(key))


@design('neoguri_back')
def d_neoguri(key):
    f = src(P('KF_Pantry', 'r043_neoguri_front_def96c5_co'))
    title = feather(f, (140, 152, 386, 250), 'neoguri_title', fade=0.08)
    sub = feather(f, (224, 118, 304, 158), 'neoguri_sub', fade=0.15)
    logo = feather(f, (120, 106, 222, 152), 'neoguri_logo', fade=0.12)
    panel = border_colour(f, (140, 152, 386, 250))
    spec = dict(name=key, bg='#c3171d', band='#a51217', band_line='#7c0c10', band_h=0.06, accent='#d5261e', line='#e0703a',
                nut_color='#5a1010',
                header=crop_header([(logo, 50), (sub, 42), (title, 104)], panel=panel, gap=14, pad=10),
                steps=['물 550ml에 분말스프, 후레이크, 다시마를 넣고 끓입니다.', '물이 끓으면 면을 넣고 5분간 더 끓입니다.',
                       '얼큰한 너구리가 완성됩니다.'],
                barcode='8801043014984',
                table=[('제품명', '얼큰한 너구리'), ('식품유형', '유탕면'),
                       ('원재료명', '면/소맥분(밀:호주산, 미국산), 팜유(말레이시아산), 감자전분, 변성전분, 정제소금, '
                                  '면류첨가알칼리제(산도조절제) / 스프/정제소금, 고춧가루, 해물맛베이스, 조미오징어분말, '
                                  '건조다시마, 건조미역, 건조당근'),
                       ('알레르기', '밀, 대두, 오징어, 조개류(홍합), 게, 새우 함유'), ('포장재질', '폴리프로필렌')],
                nutrition=ramen_nut('총 내용량 120 g', '505 kcal', ('1,700 mg', '85%'), ('81 g', '25%'), ('4 g', '4%'),
                                    ('17 g', '31%'), '0 g', ('8 g', '53%'), ('0 mg', '0%'), ('9 g', '16%'),
                                    ('칼슘', '160 mg', '23%')),
                maker_logo=(logo, (0, 0, logo.w, logo.h), 44),
                maker='(주)농심  서울특별시 동작구 여의대방로 112  고객상담실 080-023-5181',
                blocks=[('steps',), ('codes',), ('table',), ('nutrition',), ('maker',)])
    return L.bag_back(spec, aspect(key))


@design('odongtong_back')
def d_odongtong(key):
    logo = ottogi_logo()

    def head(cv, W, H, y):
        _, _, lw, lh = cv.image_fit(logo.path, (0, 0, 1, 1), 150, y + 6, h=112)
        L.outlined(cv, '오동통', 580, y + 4, 92, '#ffffff', outline='#1a0d08', t=7, align='center')
        cv.text('Odongtong Myon', 580, y + 108, 30, '#f1a33a', bold=True, align='center')
        return y + 160
    spec = dict(name=key, bg='#3b2016', band='#2a150e', band_line='#140906', band_h=0.06, accent='#e4572e', line='#8a5a44',
                nut_color='#3b2016', header=head,
                steps=['물 550ml에 다시마와 건더기스프를 넣고 물을 끓입니다.', '분말스프와 면을 넣고 5분간 더 끓입니다.',
                       '파, 어묵, 계란 등을 곁들이면 더욱 좋습니다.'],
                barcode='8801045522883', date='측면 표기일까지',
                table=[('제품명', '오동통면'), ('식품유형', '유탕면'),
                       ('원재료명', '면/소맥분(밀:호주산, 미국산), 팜유(말레이시아산), 변성전분, 정제소금, 면류첨가알칼리제 / '
                                  '스프/정제소금, 해물맛베이스, 고춧가루, 간장분말, 다시마(완도산), 건조미역, 건조어묵'),
                       ('알레르기', '밀, 대두, 새우, 오징어, 고등어, 쇠고기 함유'), ('포장재질', '폴리프로필렌')],
                nutrition=ramen_nut('총 내용량 120 g', '510 kcal', ('1,690 mg', '85%'), ('82 g', '25%'), ('4 g', '4%'),
                                    ('17 g', '31%'), '0 g', ('8 g', '53%'), ('0 mg', '0%'), ('9 g', '16%')),
                maker_logo=(logo, (0, 0, logo.w, logo.h), 52),
                maker='(주)오뚜기  경기도 안양시 동안구 흥안대로 405  고객상담실 080-088-1212',
                blocks=[('steps',), ('codes',), ('table',), ('nutrition',), ('maker',)])
    return L.bag_back(spec, aspect(key))


@design('paldobibim_back')
def d_paldo(key):
    f = src(P('KF_Pantry', 'r043_paldobibim_front_47f4e60_co'))
    title = feather(f, (92, 112, 418, 244), 'paldo_title', fade=0.06)
    logo = feather(f, (70, 70, 152, 110), 'paldo_logo', fade=0.12)
    spec = dict(name=key, bg='#1c8ad2', band='#1270b4', band_line='#0a4f86', band_h=0.07, accent='#d9262c', line='#6fb3e3',
                nut_color='#0d4f8c', scale=0.92,
                header=crop_header([(logo, 50), (title, 110)], panel=border_colour(f, (92, 112, 418, 244)), gap=24, pad=6),
                steps=['물 550ml를 끓여 면을 넣고 3분간 삶습니다.', '삶은 면을 찬물에 여러 번 헹궈 물기를 뺍니다.',
                       '액상스프를 넣고 잘 비벼 드십시오.'],
                barcode='8801128503013',
                table=[('제품명', '팔도비빔면'), ('식품유형', '유탕면'),
                       ('원재료명', '면/소맥분(밀:미국산, 호주산), 팜유(말레이시아산), 감자전분, 정제소금 / 액상스프/고추장, '
                                  '물엿, 설탕, 사과농축과즙, 양조간장, 참기름, 식초'),
                       ('알레르기', '밀, 대두, 쇠고기, 사과 함유'), ('포장재질', '폴리프로필렌')],
                nutrition=ramen_nut('총 내용량 130 g', '525 kcal', ('1,120 mg', '56%'), ('90 g', '28%'), ('17 g', '17%'),
                                    ('16 g', '30%'), '0 g', ('8 g', '53%'), ('0 mg', '0%'), ('9 g', '16%')),
                maker_logo=(logo, (0, 0, logo.w, logo.h), 44),
                maker='(주)팔도  서울특별시 용산구 원효로 90  고객상담실 080-022-8200',
                blocks=[('steps',), ('cols', [(1, [('table', dict(label_w=110)), ('maker',)]),
                                              (1, [('nutrition', dict(cols=2)), ('codes',)])])])
    return L.bag_back(spec, aspect(key))


def haitai_spec(key, bg, band, band_line, accent, header, nut_color, flavour, kcal, barcode):
    return dict(name=key, bg=bg, band=band, band_line=band_line, band_h=0.07, accent=accent, line=nut_color,
                nut_color=nut_color, header=header, margin=34, head_pad=8, scale=0.9,
                barcode=barcode, marks=['recycle'],
                table=[('제품명', '홈런볼 ' + flavour), ('식품유형', '과자'), ('내용량', '41 g (%s)' % kcal),
                       ('원재료명', '밀가루(밀:미국산), 혼합식용유, 가공유지, 설탕, 전란액, 코코아분말, 유크림, 정제소금, 합성향료'),
                       ('알레르기', '우유, 땅콩, 대두, 계란, 밀, 쇠고기 함유'), ('제조원', '해태제과식품(주) 충남 아산시 음봉면 아산밸리로 388번길')],
                nutrition=dict(total='총 내용량 41 g', kcal=kcal, items=[
                    ('나트륨', '115 mg', '6%'), ('탄수화물', '21 g', '6%'), ('당류', '14 g', '14%'),
                    ('지방', '14 g', '26%'), ('포화지방', '5 g', '33%'), ('단백질', '3 g', '5%')]),
                notes=GENERIC_NOTES[:3],
                blocks=[('cols', [(1.1, [('table', dict(size=15, label_w=100))]),
                                  (1, [('nutrition', dict(cols=2)), ('codes',)])])])


@design('homerunball_back')
def d_homerunball(key):
    f = src(P('KF_Pantry', 'r043_homerunball_front_design_1_95c2037_co'))
    logo = feather(f, (80, 172, 280, 318), 'hrb_logo', fade=0.10)
    kid = feather(f, (258, 174, 368, 342), 'hrb_kid', fade=0.10)
    head = crop_header([(logo, 96), (kid, 104)], gap=40, pad=0)
    return L.bag_back(haitai_spec(key, '#b8cf2c', '#a3ba1e', '#6f8210', '#d62a26', head, '#3f5a12', '초코', '225 kcal',
                                  '8801019310254'), aspect(key))


@design('homerunballsaltmilk_back')
def d_hrb_salt(key):
    f = src(P('KF_Pantry', 'r043_atlases_homerunballsaltmilk_41ba713_co'))
    logo = feather(f, (40, 60, 1210, 830), 'hrb_salt_logo', fade=0.04)
    head = crop_header([(logo, 118)], panel=border_colour(f, (40, 60, 1210, 830)), pad=4)
    return L.bag_back(haitai_spec(key, '#2aa3e6', '#1d8bd0', '#0f5f98', '#1d64c4', head, '#153f7a', '소금우유', '225 kcal',
                                  '8801019318474'), aspect(key))


@design('kkokkalcornroasted_back')
def d_kkokkal(key):
    def head(cv, W, H, y):
        cv.text('LOTTE', 110, y + 18, 34, '#ffffff', bold=True)
        cv.text('Since 1983', W / 2, y + 2, 30, '#8fc641', bold=True, align='center')
        L.outlined(cv, '꼬깔콘', W / 2, y + 36, 118, '#ffffff', outline='#d8232a', t=9, align='center')
        cv.text('군옥수수맛', W / 2, y + 180, 44, '#f6c343', bold=True, align='center')
        return y + 250
    spec = dict(name=key, bg='#3a241b', band='#2b1911', band_line='#120a06', band_h=0.05, accent='#d8232a', line='#b08560',
                nut_color='#3a241b', header=head, steps_title='더 맛있게 즐기는 법!',
                steps=['손가락에 끼워 먹기', '생크림 찍어 먹기', '아이스크림 채워 먹기', '우유에 말아 먹기'],
                barcode='8801062635533',
                table=[('제품명', '꼬깔콘 군옥수수맛'), ('식품유형', '과자(유탕처리제품)'), ('내용량', '72 g'),
                       ('원재료명', '옥수수(호주산, 이탈리아산), 혼합식용유(팜올레인유:말레이시아산), 해바라기유, 설탕, '
                                  '정제소금, 버터오일조미분말, 군옥수수시즈닝'),
                       ('알레르기', '밀, 대두, 우유 함유'), ('포장재질', '폴리에틸렌')],
                nutrition=dict(total='총 내용량 72 g', kcal='410 kcal', items=[
                    ('나트륨', '310 mg', '16%'), ('탄수화물', '42 g', '13%'), ('당류', '4 g', '4%'),
                    ('지방', '25 g', '46%'), ('트랜스지방', '0 g', ''), ('포화지방', '8 g', '53%'),
                    ('콜레스테롤', '0 mg', '0%'), ('단백질', '4 g', '7%')]),
                maker='롯데웰푸드(주)  서울특별시 영등포구 양평로21길 10  고객지원센터 080-024-6060',
                blocks=[('steps',), ('table',), ('nutrition',), ('codes',), ('maker',)])
    return L.bag_back(spec, aspect(key))


@design('ojingeopeanut_back')
def d_ojingeo(key):
    f = src(P('KF_Pantry', 'r043_ojingeopeanut_front_0f32656_co'))
    title = feather(f, (144, 94, 380, 196), 'ojp_title', fade=0.03, matte='#f2f3f5', tol=0.3)
    ttang = feather(f, (290, 194, 364, 234), 'ojp_ttang', fade=0.05, matte='#1f4fa8', tol=0.3)
    logo = feather(f, (152, 64, 306, 92), 'ojp_logo', fade=0.05, matte='#e9ebee', tol=0.3)

    def head(cv, W, H, y):
        cv.rect(150, y, W - 300, 170, '#ffffff', r=30)
        cv.image(logo.path, (0, 0, 1, 1), 210, y + 12, 170, 170 * logo.h / logo.w)
        _, _, tw, th = cv.image_fit(title.path, (0, 0, 1, 1), 390, y + 12, h=140)
        cv.image_fit(ttang.path, (0, 0, 1, 1), 390 + tw + 4, y + 96, h=62)
        return y + 200
    spec = dict(name=key, bg='#1f4fa8', band='#6cc2ea', band_line='#2f8ec2', band_h=0.05, accent='#1f4fa8', line='#7aa5d8',
                nut_color='#16357a', header=head,
                barcode='8801117760908',
                table=[('제품명', '오징어땅콩'), ('식품유형', '과자'), ('내용량', '98 g (492 kcal)'),
                       ('원재료명', '가공땅콩(중국산), 밀가루(밀:미국산), 찹쌀옥수수전분, 백설탕, 오징어채(오징어:페루산), '
                                  '맛소금, 물엿, 새우엑기스, 식염'),
                       ('알레르기', '밀, 땅콩, 오징어, 새우, 게, 조개류(굴) 함유'), ('품목보고번호', '19760487005150')],
                nutrition=dict(total='총 내용량 98 g', kcal='492 kcal', items=[
                    ('나트륨', '320 mg', '16%'), ('탄수화물', '57 g', '18%'), ('당류', '20 g', '20%'),
                    ('지방', '24 g', '44%'), ('트랜스지방', '0 g', ''), ('포화지방', '6 g', '40%'),
                    ('콜레스테롤', '5 mg', '1%'), ('단백질', '12 g', '22%')]),
                notes=GENERIC_NOTES,
                maker='(주)오리온  서울특별시 용산구 백범로 90다길 13  고객센터 080-023-5700',
                blocks=[('table',), ('nutrition',), ('codes',), ('notes',), ('maker',)])
    return L.bag_back(spec, aspect(key))


def bibigo_back(key, product, header, weight, kcal, nut, table_extra, barcode, band_title):
    def footer(cv, W, H, yend, bottom):
        pass
    spec = dict(name=key, bg='#f1ece2', panel='#fbf8f2', band_h=0, seams=False, accent='#c8161d', line='#c8b9a0',
                nut_color='#c8161d', header=header, margin=36, bottom_pad=150,
                steps_title='%s 조리방법' % product,
                steps=['전자레인지: 용기에 붓고 덮개를 씌워 4분 30초 데웁니다(700W).',
                       '냄비: 내용물을 붓고 끓어오르면 4~5분 더 끓입니다.',
                       '끓는 물: 봉지째 넣고 5~6분간 데웁니다.'],
                barcode=barcode, marks=['haccp', 'recycle'],
                table=[('식품유형', '즉석조리식품(레토르트식품/멸균제품)'), ('내용량', '%s (%s)' % (weight, kcal))] + table_extra +
                      [('포장재질', '폴리프로필렌(내면)'), ('제조원', 'CJ제일제당(주) 서울특별시 중구 동호로 330')],
                nutrition=nut, notes=RETORT_NOTES,
                blocks=[('steps',), ('table', dict(label_w=130)), ('nutrition',), ('codes',), ('notes',)])

    def bg_draw(cv, W, H):
        cv.rect(0, H - 130, W, 130, '#c8161d')
        cv.text(band_title, W / 2, H - 100, 52, '#ffffff', bold=True, align='center')
    spec['bg_draw'] = bg_draw
    return spec


@design('samgyetang_back')
def d_samgyetang(key):
    f = src(P('KF_Pantry', 'r043_samgyetang_front_14ffeb4_co'))
    brand = feather(f, (136, 266, 258, 342), 'sgt_brand', fade=0.08, matte=border_colour(f, (136, 266, 258, 342)), tol=0.18)
    name = feather(f, (266, 294, 390, 342), 'sgt_name', fade=0.08, matte=border_colour(f, (266, 294, 390, 342)), tol=0.18)
    head = crop_header([(brand, 120), (name, 80)], gap=60, pad=10)
    spec = bibigo_back(key, '비비고 삼계탕', head, '800 g', '660 kcal', dict(total='총 내용량 800 g', kcal='660 kcal', items=[
        ('나트륨', '1,820 mg', '91%'), ('탄수화물', '30 g', '9%'), ('당류', '1 g', '1%'), ('지방', '28 g', '52%'),
        ('트랜스지방', '0 g', ''), ('포화지방', '9 g', '60%'), ('콜레스테롤', '420 mg', '140%'), ('단백질', '72 g', '131%')]),
        [('원재료명', '닭고기(국내산), 찹쌀(국산), 수삼(국산), 대추(국산), 마늘, 정제소금, 생강')],
        '8801007326559', '비비고 삼계탕')
    return L.bag_back(spec, aspect(key))


@design('yukgaejangsoup_back')
def d_yukgaejang(key):
    f = src(P('KF_Pantry', 'r043_yukgaejangsoup_front_53419c4_co'))
    brand = feather(f, (82, 128, 240, 232), 'ygj_brand', fade=0.08, matte=border_colour(f, (82, 128, 240, 232)), tol=0.2)
    name = feather(f, (80, 292, 252, 352), 'ygj_name', fade=0.06, matte=border_colour(f, (80, 292, 252, 352)), tol=0.2)
    head = crop_header([(brand, 110), (name, 90)], gap=50, pad=10)
    spec = bibigo_back(key, '비비고 육개장', head, '500 g', '150 kcal', dict(total='총 내용량 500 g', kcal='150 kcal', items=[
        ('나트륨', '2,050 mg', '102%'), ('탄수화물', '12 g', '4%'), ('당류', '5 g', '5%'), ('지방', '6 g', '11%'),
        ('트랜스지방', '0 g', ''), ('포화지방', '1.3 g', '9%'), ('콜레스테롤', '15 mg', '5%'), ('단백질', '12 g', '22%')]),
        [('원재료명', '정제수, 대파(중국산), 토란대(미얀마산), 양지(쇠고기:호주산) 3%, 사골농축액, 고춧가루, 간장')],
        '8801007526515', '비비고 육개장')
    return L.bag_back(spec, aspect(key))


# ---------------------------------------------------------------- jin ramen mild: recoloured clean Jin Hot back
@design('jin_mild_back')
def d_jin_mild(key):
    import bpy
    j = jinhot()
    a = rc.load_png(j.path)
    keep_logo = (650, 100, 862, 296)
    a = recolor_red(a, (0, 0, 2048, 2048), '#1f3c96', keep=keep_logo)
    # the cooking illustrations (pots, flames) keep their original colours
    orig = rc.load_png(j.path)
    a[520:770, 190:1900] = orig[520:770, 190:1900]
    a[480:560, 930:1140] = orig[480:560, 930:1140]  # 분말스프 sachet
    base = derived_png('jin_mild_base', a)
    W, H0 = 2048.0, 2048.0
    Hn = W * aspect(key)
    cv = rc.Canvas(W, Hn, bg='#ffe600')
    split = 1938
    cv.image(base.path, (0, 0, 1, split / H0), 0, 0, W, split, alpha=False)
    gap = Hn - H0
    # stretch the yellow separator row (with its side crimp stripes) over the inserted gap
    cv.image(base.path, (0, (split - 1) / H0, 1, split / H0), 0, split, W, gap, alpha=False)
    cv.image(base.path, (0, split / H0, 1, 1), 0, split + gap, W, H0 - split, alpha=False)
    # text patches (Hot -> Mild)
    cv.rect(1336, 106, 256, 116, '#1f3c96', r=58)
    cv.text('순한맛', 1464, 118, 74, '#ffffff', bold=True, align='center')
    cv.rect(1060, 226, 420, 92, '#ffe600')
    t = cv.text('Jin Ramen Mild', 1064, 228, 76, '#1f3c96', bold=True)
    t.data.shear = 0.18
    cv.rect(1655, 444, 250, 60, '#ffffff')
    cv.text('진라면 순한맛이', 1658, 446, 46, '#1f3c96', bold=True)
    cv.rect(330, 1044, 240, 56, '#ffffff')
    cv.text('진라면 순한맛', 334, 1046, 40, INK)
    # extra band in the inserted gap
    y = split + 20
    cv.rect(150, y, W - 300, gap - 60, '#ffffff', r=40)
    cv.frame(150, y, W - 300, gap - 60, '#1f3c96', t=6, r=40)
    cv.image_fit(ottogi_logo().path, (0, 0, 1, 1), 220, y + 40, h=gap - 140)
    L.outlined(cv, '진라면 순한맛', 1150, y + 50, 150, '#1f3c96', outline='#ffffff', t=0, align='center')
    cv.text('Jin Ramen Mild  ·  120 g (500 kcal)', 1150, y + 250, 64, INK, bold=True, align='center')
    return cv.render(1600)


# ---------------------------------------------------------------- curry pouch (front + back, silver retort pouch)
def curry_common(cv, W, H):
    cv.rect(0, 0, W, H, '#d9dbdc')
    cv.rect(0, 0, W, 60, '#cfd1d3')
    cv.rect(0, H - 60, W, 60, '#cfd1d3')
    for k in range(6):  # red register marks along the seals
        cv.rect(70 + k * 170, 12, 26, 26, '#d8232a')
        cv.rect(70 + k * 170, H - 38, 26, 26, '#d8232a')


@design('curry_front')
def d_curry_front(key):
    W = 1000.0; H = W * aspect(key)
    cv = rc.Canvas(W, H, bg='#d9dbdc')
    curry_common(cv, W, H)
    logo = ottogi_logo()
    L.pill(cv, '간편하게 뜯으세요!', 640, 80, 26, '#d8232a')
    cv.text('◀ EASY CUT', 700, 128, 22, '#d8232a', bold=True)
    cv.image_fit(logo.path, (0, 0, 1, 1), 90, 200, h=170)
    L.outlined(cv, '3분', 560, 150, 130, '#d8232a', outline='#ffffff', t=6)
    L.outlined(cv, '카레', 470, 300, 150, '#d8232a', outline='#ffffff', t=6)
    L.pill(cv, '매운맛', 560, 490, 44, '#d8232a')
    cv.text('OTTOGI CURRY SAUCE(SPICY)', W / 2, 580, 38, '#d8232a', bold=True, align='center')
    y = 660
    cv.rect(60, y, W - 120, 56, '#d8232a')
    cv.text('조리방법', W / 2, y + 6, 36, '#ffffff', bold=True, align='center')
    cv.frame(60, y, W - 120, 470, '#d8232a', t=4)
    cv.rect(W / 2 - 2, y + 56, 4, 414, '#d8232a')
    for i, (t1, t2, mins) in enumerate((('전자레인지 700W 이용시', '밥 위에 부은 후 전자레인지용 덮개를 덮고 2분간 데워 드십시오.', '2분'),
                                        ('끓는 물 이용시', '봉지 그대로 끓는 물에 넣고 3분간 데운 후 밥 위에 부어 드십시오.', '3분'))):
        x = 80 + i * (W / 2 - 60)
        cv.text(t1, x + (W / 2 - 100) / 2, y + 76, 28, INK, bold=True, align='center')
        cv.circle(x + (W / 2 - 100) / 2, y + 190, 58, '#ffffff')
        cv.frame(x + (W / 2 - 100) / 2 - 58, y + 132, 116, 116, '#d8232a', t=5, r=58)
        cv.text(mins, x + (W / 2 - 100) / 2, y + 162, 44, '#d8232a', bold=True, align='center')
        L.para(cv, t2, x + 10, y + 270, W / 2 - 120, 25, INK)
    y2 = y + 500
    L.para(cv, '• 가열된 제품은 매우 뜨거워 화상의 우려가 있으므로 주의하십시오.', 70, y2, 470, 23, '#d8232a')
    L.para(cv, '• 소비자기본법에 따라 피해 보상', 70, y2 + 80, 470, 23, '#d8232a')
    cv.barcode(560, y2 + 10, 240, 110, '8801045290324')
    L.recycle_mark(cv, 820, y2 - 5, 1.0)
    cv.text('내용량 200 g (145 kcal)', 70, y2 + 130, 30, INK, bold=True)
    return cv.render(1400)


@design('curry_back')
def d_curry_back(key):
    W = 1000.0; H = W * aspect(key)
    logo = ottogi_logo()
    spec = dict(name=key, bg='#d9dbdc', seams=False, band_h=0, accent='#d8232a', line='#d8232a', nut_color='#d8232a',
                panel='#f4f4f3', margin=50, head_pad=70, bottom_pad=70, scale=0.95,
                bg_draw=lambda cv, W, H: curry_common(cv, W, H),
                header=lambda cv, W, H, y: (cv.image_fit(logo.path, (0, 0, 1, 1), 110, y, h=110),
                                            L.outlined(cv, '3분 카레 매운맛', 640, y + 20, 70, '#d8232a', outline='#ffffff', t=4,
                                                       align='center'), y + 130)[-1],
                barcode='8801045290324', marks=['recycle'],
                table=[('제품명', '3분 카레 매운맛'), ('식품유형', '카레(레토르트식품)'), ('내용량', '200 g (145 kcal)'),
                       ('원재료명', '감자(국산), 당근(국산), 양파, 돼지고기(국산), 카레분(인도산), 밀가루, 설탕, 정제소금, 고춧가루'),
                       ('알레르기', '밀, 대두, 우유, 돼지고기, 쇠고기 함유'), ('제조원', '(주)오뚜기 경기도 안양시 동안구 흥안대로 405')],
                nutrition=dict(total='총 내용량 200 g', kcal='145 kcal', items=[
                    ('나트륨', '850 mg', '43%'), ('탄수화물', '19 g', '6%'), ('당류', '4 g', '4%'),
                    ('지방', '6 g', '11%'), ('포화지방', '3 g', '20%'), ('단백질', '4 g', '7%')]),
                notes=RETORT_NOTES[:3],
                blocks=[('table', dict(label_w=120, size=18)), ('nutrition', dict(cols=2)), ('notes',), ('codes',)])
    return L.bag_back(spec, aspect(key))


# ---------------------------------------------------------------- combat ration (식량, 전투용, II형) pouch
@design('combatbibimbap')
def d_combat(key):
    W = 1000.0; H = W * aspect(key)
    cv = rc.Canvas(W, H, bg='#3d3f41')
    cv.rect(0, 0, W, 70, '#353638')
    cv.rect(0, 70, W, 3, '#2a2b2c')
    rects = [(x, 12, 5, 46) for x in range(10, int(W), 14)]
    cv.rects(rects, '#303133')
    # 군 용 + emblem
    cv.text('군', 330, 150, 64, '#1d1e1f', bold=True, align='center')
    cv.text('용', 670, 150, 64, '#1d1e1f', bold=True, align='center')
    cv.circle(500, 190, 46, '#1d1e1f')
    cv.circle(500, 190, 36, '#3d3f41')
    cv.poly([(500, 150), (512, 180), (544, 182), (518, 200), (528, 230), (500, 212), (472, 230), (482, 200), (456, 182), (488, 180)], '#1d1e1f')
    cv.rect(380, 178, 90, 10, '#1d1e1f'); cv.rect(530, 178, 90, 10, '#1d1e1f')
    y = 280
    cv.rect(150, y, 700, 110, '#141414')
    cv.text('식량, 전투용, Ⅱ형', 500, y + 14, 70, '#e8e8e8', bold=True, align='center')
    cv.text('(1식단:김치비빔밥)', 500, y + 130, 64, '#141414', bold=True, align='center')
    cv.rect(330, y + 230, 340, 44, '#141414')
    cv.text('김치(2.25%/국산배추)', 500, y + 234, 28, '#cfcfcf', align='center')
    # white stock label
    lx, ly, lw = 230, y + 320, 540
    rows = [('재고번호', None), ('품    명', '김치비빔밥'), ('단    위', 'EA    수량    1'), ('제조일자\n유효일자', '2024.03.15 ~ 2027.03.14'),
            ('제조회사', '(주)삼양식품')]
    rh = [70, 56, 56, 90, 56]
    total = sum(rh)
    cv.rect(lx, ly, lw, total, '#f4f4f2', r=6)
    cv.frame(lx, ly, lw, total, '#141414', t=3, r=6)
    yy = ly
    for (lab, val), h in zip(rows, rh):
        cv.rect(lx + 150, yy, 3, h, '#141414')
        L.para(cv, lab, lx + 12, yy + 10, 140, 26, '#141414', bold=True)
        if val is None:
            cv.barcode(lx + 175, yy + 8, 320, h - 14, '8970379345408', text=False)
        else:
            cv.text(val, lx + 170, yy + (h - 34) / 2, 28, '#141414', bold=val == '김치비빔밥')
        yy += h
        if yy < ly + total:
            cv.rect(lx, yy, lw, 2.5, '#141414')
    cv.text('섭취방법: 봉지를 개봉하여 물을 붓고 10분 후 드십시오.', 500, ly + total + 40, 26, '#1d1e1f', bold=True, align='center')
    cv.rect(0, H - 60, W, 60, '#353638')
    cv.rects([(x, H - 50, 5, 40) for x in range(10, int(W), 14)], '#303133')
    return cv.render(1400)


# ---------------------------------------------------------------- misutgaru 1 kg stand-up bag (front, back, parts atlas)
MISUT_REF = None


def misut_ref():
    """product photo (old project reference, read-only) - copied once into tools/models/textures/photos/src."""
    global MISUT_REF
    if MISUT_REF is None:
        local = OUTDIR / 'src' / 'misutgaru_front_back_1kg.png'
        if not local.exists():
            import shutil
            cand = [a for a in argv if a.endswith('front_back_1kg.png')]
            if not cand:
                raise SystemExit('misutgaru reference missing: pass --misut-ref <old project>\\work\\kf-product-review\\references\\Misutgaru\\front_back_1kg.png')
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cand[0], local)
        import bpy
        im = bpy.data.images.load(str(local), check_existing=True)
        MISUT_REF = Img(str(local), *im.size)
    return MISUT_REF


def noise(h, w, scales, seed=1):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    for r, amp in scales:
        n = rng.standard_normal((h, w, 1)).astype(np.float32)
        if r > 0:
            n = blur(n, r)
            n /= max(1e-6, n.std())
        out += amp * n[..., 0]
    return out


def powder_png(name, w, h, base='#d3bb9c', seed=3, lumps=True):
    c = np.array(rc.hex2rgb(base), np.float32)
    n = noise(h, w, [(0, 0.035), (2, 0.03), (10, 0.035), (40, 0.03)], seed)
    a = np.ones((h, w, 4), np.float32)
    a[..., :3] = np.clip(c[None, None, :] * (1 + n[..., None]), 0, 1)
    if lumps:  # a few darker grain specks (roasted grains)
        rng = np.random.default_rng(seed + 7)
        k = rng.random((h, w)) < 0.004
        a[k, :3] *= 0.72
    return derived_png(name, a)


GREEN = '#3c9f35'
GREEN_D = '#2b7d27'


def misut_bands(cv, W, H, seal=False):
    top = 150
    cv.rect(0, 0, W, top, GREEN)
    cv.rect(0, top - 8, W, 8, GREEN_D)
    # tear line with scissors mark
    cv.rects([(40 + k * 22, 48, 12, 3) for k in range(int((W - 80) / 22))], '#1f5a1c')
    cv.text('X', 14, 34, 26, '#1f5a1c', bold=True)
    cv.text('※ 지퍼백 포장을 이용하시면 맛과 품질을 유지할 수 있습니다.', 40, 88, 24, '#ffffff', bold=True)
    b = 110
    cv.rect(0, H - b, W, b, GREEN)
    cv.rect(0, H - b, W, 8, GREEN_D)
    cv.text('POWDER MADE OF MIXED GRAINS  ·  17곡 미숫가루 A+', W / 2, H - b + 34, 26, '#ffffff', bold=True, align='center')


def dilate(m, r):
    out = m.copy()
    for _ in range(r):
        g = out.copy()
        g[1:] |= out[:-1]; g[:-1] |= out[1:]; g[:, 1:] |= out[:, :-1]; g[:, :-1] |= out[:, 1:]
        out = g
    return out


def misut_title(r):
    """re-ink the calligraphy: dark strokes -> solid near-black, clean white outline, transparent elsewhere
    (drops the photo's glare, powder and film wrinkles)."""
    x0, y0, x1, y1 = 224, 578, 588, 696
    a = rc.load_png(r.path)[y0:y1, x0:x1].copy()
    a = rc.resample(a, a.shape[1] * 3, a.shape[0] * 3)
    lum = a[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
    ink = blur(np.clip((0.42 - lum) / 0.14, 0, 1)[..., None], 1)[..., 0]
    core = ink > 0.5
    halo = blur(dilate(core, 9).astype(np.float32)[..., None], 2)[..., 0]
    out = np.zeros_like(a)
    out[..., :3] = 1.0
    out[..., :3] = out[..., :3] * (1 - ink[..., None]) + np.array([0.07, 0.06, 0.06])[None, None, :] * ink[..., None]
    out[..., 3] = np.clip(np.maximum(halo, ink), 0, 1)
    return derived_png('misut_title', out)


def misut_header(cv, W, y, big=True):
    r = misut_ref()
    logo = feather(r, (176, 443, 240, 534), 'misut_logo', fade=0.06)
    title = misut_title(r)
    s = 1.0 if big else 0.8
    cv.rect(52, y + 10, 120 * s, 170 * s, '#ffffff', r=8)
    cv.image_fit(logo.path, (0, 0, 1, 1), 58, y + 14, 108 * s, 162 * s, align='center')
    bw, bh = 300 * s, 140 * s
    bx = W / 2 - bw / 2
    cv.rect(bx, y + 40 * s, bw, bh, '#161616')
    cv.rect(bx, y + 40 * s + bh - 8 * s, bw, 8 * s, '#8cc63f')
    cv.text('17곡', W / 2, y + 52 * s, 96 * s, '#ffffff', bold=True, align='center')
    tw = 820 * s
    th = tw * title.h / title.w
    cv.image(title.path, (0, 0, 1, 1), W / 2 - tw / 2 + 20, y + 40 * s + bh + 10, tw, th)
    return y + 40 * s + bh + 10 + th


def misut_canvas(W, H):
    cv = rc.Canvas(W, H, bg='#d3bb9c')
    pw = powder_png('misut_powder_label', 700, int(700 * H / W), seed=5)
    cv.image(pw.path, (0, 0, 1, 1), 0, 0, W, H, alpha=False)
    return cv


def misut_front():
    W, H = 1000.0, 1360.0
    r = misut_ref()
    cv = misut_canvas(W, H)
    misut_bands(cv, W, H)
    y = misut_header(cv, W, 170)
    grains = feather(r, (262, 868, 648, 1034), 'misut_grains', fade=0.10)
    mascot = feather(r, (172, 866, 268, 986), 'misut_mascot', fade=0.12)
    gw = 700
    gh = gw * grains.h / grains.w
    cv.image(grains.path, (0, 0, 1, 1), W - gw - 20, H - 110 - gh - 10, gw, gh)
    mh = 250
    cv.image(mascot.path, (0, 0, 1, 1), 40, H - 110 - mh - 70, mh * mascot.w / mascot.h, mh)
    cv.text('1kg', 70, H - 110 - 76, 52, '#1a1a1a', bold=True)
    cv.text('(4,100 kcal)', 58, H - 110 - 20 - 0, 24, '#1a1a1a', bold=True)
    return cv.render(1400)


def misut_back():
    W, H = 1000.0, 1360.0
    r = misut_ref()
    cv = misut_canvas(W, H)
    misut_bands(cv, W, H)
    y = misut_header(cv, W, 160, big=False) + 10
    P = dict(accent='#2b7d27', line='#6b5a48', nut_color='#1f1f1f', barcode='8805017210488', marks=['recycle'],
             table=[('제품명', '17곡미숫가루A+'), ('식품유형', '곡류가공품'), ('내용량', '1 kg (4,100 kcal)'),
                    ('원재료명', '보리30%(국산), 찹쌀29%(외국산), 현미18%(외국산), 대두, 찹쌀, 옥수수, 통밀, 수수, 조, '
                               '흑태, 흑미, 서리태, 율무, 참깨, 땅콩, 흑임자'),
                    ('알레르기', '대두, 밀, 땅콩 함유'), ('보관방법', '직사광선을 피하여 서늘한 곳에 보관'),
                    ('제조원', '(주)뚜레반 경기도 고양시 일산동구')],
             nutrition=dict(total='총 내용량 1,000 g', kcal='4,100 kcal', items=[
                 ('나트륨', '15 mg', '1%'), ('탄수화물', '74 g', '23%'), ('당류', '1 g', '1%'), ('지방', '6 g', '11%'),
                 ('포화지방', '1 g', '7%'), ('단백질', '16 g', '29%')]),
             notes=['물 또는 우유 200ml에 3~5스푼 넣고 잘 저어 드십시오.', '기호에 따라 꿀이나 설탕을 타서 드시면 더욱 좋습니다.'])
    x0, w = 60, W - 120
    s = 0.95
    cv.rect(x0 - 10, y, w + 20, H - 110 - 190 - y, '#ffffff', r=16, alpha=0.93)
    yy = y + 14
    colw = (w - 20) / 2
    y1 = L.block_table(cv, x0, yy, colw + 20, s, P, label_w=100, size=17)
    y2 = L.block_nutrition(cv, x0 + colw + 40, yy, colw - 20, s, P, cols=1)
    cv.barcode(x0 + colw + 60, yy + y2 + 6, 250, 100, P['barcode'])
    L.recycle_mark(cv, x0 + colw + 340, yy + y2 - 4, 0.85)
    yy += y1
    L.block_notes(cv, x0, yy, colw + 20, s, P, title='※ 드시는 방법', color='#2b7d27')
    grains = feather(r, (262, 868, 648, 1034), 'misut_grains', fade=0.10)
    mascot = feather(r, (172, 866, 268, 986), 'misut_mascot', fade=0.12)
    gw = 560
    gh = gw * grains.h / grains.w
    cv.image(grains.path, (0, 0, 1, 1), W - gw - 20, H - 110 - gh - 6, gw, gh)
    mh = 170
    cv.image(mascot.path, (0, 0, 1, 1), 60, H - 110 - mh - 10, mh * mascot.w / mascot.h, mh)
    return cv.render(1400)


def misut_parts():
    """512x512 atlas: u0-.5/v0-.5 crimp seal, u.5-1 full height = side gusset column, u0-.5/v.5-1 powder surface."""
    N = 1024
    a = np.zeros((N, N, 4), np.float32); a[..., 3] = 1
    g = np.array(rc.hex2rgb(GREEN), np.float32)
    gd = np.array(rc.hex2rgb(GREEN_D), np.float32)
    # crimp seal: vertical ridges
    xs = np.arange(N // 2)
    ridge = 0.82 + 0.25 * (0.5 + 0.5 * np.cos(xs / 7.0 * 2 * np.pi))
    a[:N // 2, :N // 2, :3] = g[None, None, :] * ridge[None, :, None]
    a[:14, :N // 2, :3] = gd; a[N // 2 - 14:N // 2, :N // 2, :3] = gd
    # gusset column: powder behind clear film with green bands matching the label (top 11 %, bottom 8 %)
    pw = rc.load_png(powder_png('misut_powder_side', N // 2, N, base='#c9b092', seed=9).path)
    col = pw.copy()
    col[:, :, :3] *= (0.92 + 0.08 * np.linspace(0, 1, N // 2)[None, :, None])
    t = int(N * 150 / 1360); b = int(N * 110 / 1360)
    col[:t, :, :3] = g; col[t - 6:t, :, :3] = gd
    col[N - b:, :, :3] = g; col[N - b:N - b + 6, :, :3] = gd
    a[:, N // 2:] = col
    # powder surface (open contents)
    p = rc.load_png(powder_png('misut_powder_top', N // 2, N // 2, base='#d8c2a3', seed=11).path)
    a[N // 2:, :N // 2] = p
    a[..., 3] = 1
    return a


def misut_write(name, arr, size):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    arr = rc.resample(arr, size[0], size[1])
    arr[..., 3] = 1
    png = OUTDIR / (name + '.png')
    rc.save_png(arr, str(png))
    if not NO_PAA:
        rc.png2paa(str(png), str(REPO / 'source' / 'KF_Pantry' / 'data' / (name + '.paa')))
    print('R049 wrote %-28s %dx%d' % (name, size[0], size[1]))


def build_misutgaru():
    f = misut_front(); rc.save_png(f, str(OUTDIR / 'misutgaru_front_design.png'))
    misut_write('r049_photos_misutgaru_front_co', f, (1024, 1024))
    b = misut_back(); rc.save_png(b, str(OUTDIR / 'misutgaru_back_design.png'))
    misut_write('r049_photos_misutgaru_back_co', b, (1024, 1024))
    misut_write('r049_photos_misutgaru_parts_co', misut_parts(), (512, 512))


# ---------------------------------------------------------------- fronts: remove studio background around the pack
def clean_full(key, texture, grow=2, band=0.09, **kw):
    """only background that reaches into a thin band along the mapped rectangle's edge is replaced
    (white crimp gaps / studio margins); white print inside the pack is left alone."""
    im = src(texture)
    a = rc.load_png(im.path)
    h, w = a.shape[:2]
    u0, v0, u1, v1 = LAYOUT[key]['rect']
    x0, x1, y0, y1 = u0 * w, u1 * w, v0 * h, v1 * h
    X = np.arange(w)[None, :] + 0.5; Y = np.arange(h)[:, None] + 0.5
    dx = np.minimum(X - x0, x1 - X) / max(1, x1 - x0)
    dy = np.minimum(Y - y0, y1 - Y) / max(1, y1 - y0)
    allowed = np.minimum(dx, dy) < band
    m = background_mask(a, **kw) & allowed
    for _ in range(grow):
        g = m.copy(); g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]; m = g & allowed
    c = fill_from_neighbours(a, m)
    print('R049 %s background px %.1f%%' % (key, 100 * m.mean()))
    return c


for _k, _t in (('homerunball_front', P('KF_Pantry', 'r043_homerunball_front_design_1_95c2037_co')),
               ('homerunballclassic_front', P('KF_Pantry', 'r043_homerunball_front_design_2_657fab1_co')),
               ('kkokkalcornroasted_front', P('KF_Pantry', 'r043_kkokkalcorn_four_flavors_beff63d_co')),
               ('ojingeopeanut_front', P('KF_Pantry', 'r043_ojingeopeanut_front_0f32656_co')),
               ('ansung_front', P('KF_Food', 'r044_ref_05_co')),
               ('chapagetti_front', P('KF_Food', 'r044_ref_07_co'))):
    DESIGNS[_k] = (lambda k, t=_t: ('full', clean_full(k, t)))


def main():
    import bpy
    if ONLY is None or 'misutgaru' in ONLY:
        build_misutgaru()
    keys = [k for k in DESIGNS if ONLY is None or k in ONLY]
    for k in keys:
        if k not in LAYOUT:
            print('R049 skip (no layout)', k)
            continue
        res = DESIGNS[k](k)
        if isinstance(res, tuple) and res[0] == 'full':
            write_full(k, res[1])
        elif res is not None:
            write(k, res)
    print('R049_TEXTURES_DONE', len(keys))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        raise SystemExit(1)
