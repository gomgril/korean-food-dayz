"""Reusable package-print layouts for r049 (runs inside Blender, uses r049_compose.Canvas).

All layouts draw on a Canvas that is 1000 units wide; heights follow the physical aspect of the surface.
A layout is re-tried with a smaller content scale until everything fits its panel.
"""
import math
import r049_compose as rc

INK = '#231f20'
GREY = '#55514e'


class Img:
    """Source image + pixel crop helper."""
    def __init__(self, path, w, h):
        self.path, self.w, self.h = path, w, h

    def crop(self, x0, y0, x1, y1):
        return (x0 / self.w, y0 / self.h, x1 / self.w, y1 / self.h)

    def aspect(self, x0, y0, x1, y1):
        return (x1 - x0) / (y1 - y0)


# ------------------------------------------------------------------ small drawing helpers
def outlined(cv, s, x, y, size, color, outline='#ffffff', t=None, bold=True, align='left', scale_x=1.0, shear=0.0,
             anchor='top'):
    t = size * 0.06 if t is None else t
    if t > 0:
        for k in range(16):
            a = 2 * math.pi * k / 16
            ob = cv.text(s, x + t * math.cos(a), y + t * math.sin(a), size, outline, bold=bold, align=align,
                         scale_x=scale_x, anchor=anchor)
            ob.data.shear = shear
    ob = cv.text(s, x, y, size, color, bold=bold, align=align, scale_x=scale_x, anchor=anchor)
    ob.data.shear = shear
    return ob


def measure(cv, ob):
    import bpy
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    if not me.vertices:
        ev.to_mesh_clear()
        return (ob.location.x, -ob.location.y, 0, 0)
    mw = ob.matrix_world
    xs = []; ys = []
    for v in me.vertices:
        p = mw @ v.co
        xs.append(p.x); ys.append(-p.y)
    ev.to_mesh_clear()
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def para(cv, s, x, y, w, size, color=INK, bold=False, spacing=1.12, align='left'):
    """Wrapped paragraph; returns height used (from y to bottom of last line + small gap)."""
    ob = cv.text(s, x, y, size, color, bold=bold, width=w, spacing=spacing, align=align)
    bx, by, bw, bh = measure(cv, ob)
    lines = max(1, round((by + bh - y) / (size * 1.25 * spacing)))
    return max(by + bh - y, size) + size * 0.25


def crimp_band(cv, y, h, color, line_color, step=9, top=True):
    cv.rect(0, y, cv.W, h, color)
    rects = []
    x = step / 2
    while x < cv.W:
        rects.append((x, y + h * 0.12, step * 0.35, h * 0.76))
        x += step
    cv.rects(rects, line_color)
    # thin seal edge line
    ey = y + h - 2 if top else y
    cv.rect(0, ey, cv.W, 2, line_color)


def side_seams(cv, y0, y1, color, w=26):
    """darker vertical strips at left/right edges (the bag's side folds)"""
    cv.rect(0, y0, w, y1 - y0, color, alpha=0.35)
    cv.rect(cv.W - w, y0, w, y1 - y0, color, alpha=0.35)


def pill(cv, text, x, y, size, bg, fg='#ffffff', padx=None, pady=None):
    padx = size * 0.55 if padx is None else padx
    pady = size * 0.22 if pady is None else pady
    tw = cv.text_width(text, size, bold=True)
    h = size * 1.25 + 2 * pady
    cv.rect(x, y, tw + 2 * padx, h, bg, r=h / 2)
    cv.text(text, x + padx, y + pady + size * 0.02, size, fg, bold=True)
    return tw + 2 * padx, h


def recycle_mark(cv, x, y, s, color=INK, label='비닐류'):
    """simplified recycling triangle + OTHER label, box size ~ 110*s"""
    r = 42 * s
    cx, cy = x + 55 * s, y + 50 * s
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (-90, 30, 150)]
    for i in range(3):
        a, b = pts[i], pts[(i + 1) % 3]
        # leave gaps near the corners so it reads as three arrows
        ax, ay = a[0] + (b[0] - a[0]) * 0.18, a[1] + (b[1] - a[1]) * 0.18
        bx, by = a[0] + (b[0] - a[0]) * 0.78, a[1] + (b[1] - a[1]) * 0.78
        cv.line(ax, ay, bx, by, color, t=7 * s)
        # arrow head
        dx, dy = (b[0] - a[0]), (b[1] - a[1]); L = math.hypot(dx, dy); dx /= L; dy /= L
        hx, hy = bx + dx * 10 * s, by + dy * 10 * s
        cv.poly([(hx, hy), (bx - dy * 9 * s, by + dx * 9 * s), (bx + dy * 9 * s, by - dx * 9 * s)], color)
    cv.text(label, cx, cy - 8 * s, 17 * s, color, bold=True, align='center')
    cv.text('OTHER', cx, y + 100 * s, 22 * s, color, bold=True, align='center')
    return 110 * s, 128 * s


def haccp_mark(cv, x, y, s, color='#1b5aa6'):
    w, h = 130 * s, 110 * s
    cv.rect(x, y, w, h, color, r=h / 2.2)
    cv.rect(x + 5 * s, y + 5 * s, w - 10 * s, h - 10 * s, '#ffffff', r=h / 2.4)
    cv.text('식품안전관리인증', x + w / 2, y + 16 * s, 12 * s, color, bold=True, align='center')
    cv.text('HACCP', x + w / 2, y + 36 * s, 30 * s, color, bold=True, align='center')
    cv.rect(x + 12 * s, y + 76 * s, w - 24 * s, 20 * s, color, r=6 * s)
    cv.text('식품의약품안전처', x + w / 2, y + 78 * s, 11 * s, '#ffffff', bold=True, align='center')
    return w, h


# ------------------------------------------------------------------ blocks (return height used)
def block_steps(cv, x, y, w, s, P):
    acc = P['accent']
    title = P.get('steps_title', '조리방법')
    _, ph = pill(cv, title, x, y, 30 * s, acc)
    y2 = y + ph + 14 * s
    steps = P['steps']
    n = len(steps)
    gap = 18 * s
    cw = (w - gap * (n - 1)) / n
    hmax = 0
    for i, st in enumerate(steps):
        cx = x + i * (cw + gap)
        r = 19 * s
        cv.circle(cx + r, y2 + r, r, acc)
        cv.text(str(i + 1), cx + r, y2 + r * 0.2, 27 * s, '#ffffff', bold=True, align='center')
        hh = para(cv, st['text'] if isinstance(st, dict) else st, cx + 2 * r + 8 * s, y2, cw - 2 * r - 8 * s, 21 * s, INK)
        h = max(hh, 2 * r + 4 * s)
        if isinstance(st, dict) and st.get('img'):
            im, crop = st['img']
            ih = st.get('img_h', 110) * s
            fx, fy, fw, fh = cv.image_fit(im.path, im.crop(*crop), cx + 4 * s, y2 + h + 6 * s, cw - 8 * s, ih, align='center')
            h += ih + 10 * s
        hmax = max(hmax, h)
    return (y2 - y) + hmax + 10 * s


def block_codes(cv, x, y, w, s, P):
    """date box + barcode + marks in one row"""
    h = 150 * s
    bw = w * 0.30
    cv.frame(x, y, bw, h, GREY, t=2.5 * s, r=16 * s)
    cv.text(P.get('date_label', '유통기한'), x + 16 * s, y + 12 * s, 20 * s, GREY, bold=True)
    cv.text_fit(P.get('date', '측면 표기일까지'), x + bw / 2, y + 62 * s, bw - 24 * s, 30 * s, INK, bold=True, align='center')
    bx = x + bw + 40 * s
    bcw = min(w * 0.33, 300 * s)
    cv.barcode(bx, y + 8 * s, bcw, h - 16 * s, P['barcode'], color=P.get('barcode_color', '#111111'))
    mx = bx + bcw + 40 * s
    marks = P.get('marks', ['recycle', 'haccp'])
    for m in marks:
        if mx > x + w - 100 * s:
            break
        if m == 'recycle':
            mw, _ = recycle_mark(cv, mx, y + 8 * s, s)
        elif m == 'haccp':
            mw, _ = haccp_mark(cv, mx, y + 18 * s, s)
        else:
            im, crop, mh = m
            _, _, mw, _ = cv.image_fit(im.path, im.crop(*crop), mx, y + (h - mh * s) / 2, h=mh * s)
        mx += mw + 24 * s
    return h + 18 * s


def block_table(cv, x, y, w, s, P, rows=None, label_w=None, size=19):
    rows = rows if rows is not None else P['table']
    line = P.get('line', P['accent'])
    lw = (label_w or 150) * s
    size = size * s
    yy = y
    cv.rect(x, y, w, 2.5 * s, line)
    for label, value in rows:
        hl = para(cv, label, x + 10 * s, yy + 8 * s, lw - 16 * s, size, INK, bold=True)
        hv = para(cv, value, x + lw + 10 * s, yy + 8 * s, w - lw - 20 * s, size, INK)
        rh = max(hl, hv) + 10 * s
        cv.rect(x, yy + rh, w, 2 * s, line)
        cv.rect(x + lw, yy, 2 * s, rh, line)
        yy += rh
    cv.rect(x, y, 2.5 * s, yy - y + 2 * s, line)
    cv.rect(x + w - 2.5 * s, y, 2.5 * s, yy - y + 2 * s, line)
    return yy - y + 16 * s


def block_nutrition(cv, x, y, w, s, P, cols=3):
    N = P['nutrition']
    dark = P.get('nut_color', '#1d2d6b')
    hh = 64 * s
    cv.rect(x, y, w, hh, dark)
    cv.text('영양정보', x + 18 * s, y + 8 * s, 38 * s, '#ffffff', bold=True)
    cv.text(N['total'], x + w - 16 * s, y + 6 * s, 20 * s, '#ffffff', bold=True, align='right')
    cv.text(N['kcal'], x + w - 16 * s, y + 33 * s, 22 * s, '#ffffff', bold=True, align='right')
    items = N['items']
    rows = math.ceil(len(items) / cols)
    rh = 42 * s
    cw = w / cols
    y0 = y + hh
    cv.frame(x, y0 - 2 * s, w, rows * rh + 4 * s, dark, t=2.5 * s)
    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        cx, cy = x + c * cw, y0 + r * rh
        name, val, pct = (list(it) + [''])[:3]
        cv.text(name, cx + 12 * s, cy + 9 * s, 20 * s, INK, bold=True)
        nw = cv.text_width(name, 20 * s, bold=True)
        cv.text(val, cx + 18 * s + nw, cy + 10 * s, 19 * s, INK)
        if pct:
            cv.text(pct, cx + cw - 12 * s, cy + 9 * s, 20 * s, INK, bold=True, align='right')
        if c:
            cv.rect(cx, cy, 2 * s, rh, dark)
        if r:
            cv.rect(cx, cy, cw, 1.5 * s, dark)
    y1 = y0 + rows * rh + 4 * s
    cv.rect(x, y1, w, 44 * s, '#ffffff')
    cv.frame(x, y1 - 2 * s, w, 44 * s, dark, t=2.5 * s)
    cv.text_fit('1일 영양성분 기준치에 대한 비율(%)은 2,000 kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.',
                x + 12 * s, y1 + 10 * s, w - 24 * s, 17 * s, INK)
    return y1 + 44 * s - y + 14 * s


def block_notes(cv, x, y, w, s, P, notes=None, title='※ 주의사항', color=None):
    notes = notes if notes is not None else P['notes']
    color = color or P.get('notes_color', '#d4202a')
    yy = y + 12 * s
    cv.text(title, x + 14 * s, yy, 24 * s, color, bold=True)
    yy += 36 * s
    for n in notes:
        cv.circle(x + 22 * s, yy + 12 * s, 5 * s, color)
        yy += para(cv, n, x + 36 * s, yy, w - 50 * s, 19 * s, color if P.get('notes_red', True) else INK)
    cv.frame(x, y, w, yy - y + 6 * s, '#c9c6c2', t=2 * s, r=8 * s)
    return yy - y + 20 * s


def block_maker(cv, x, y, w, s, P):
    h = 0
    lx = x
    if P.get('maker_logo'):
        im, crop, lh = P['maker_logo']
        _, _, lw, _ = cv.image_fit(im.path, im.crop(*crop), x, y, h=lh * s)
        lx = x + lw + 20 * s
        h = lh * s
    hh = para(cv, P['maker'], lx, y + 4 * s, x + w - lx, 19 * s, INK)
    return max(h, hh) + 12 * s


def block_image(cv, x, y, w, s, P, spec):
    im, crop, ih = spec
    fx, fy, fw, fh = cv.image_fit(im.path, im.crop(*crop), x, y, w, ih * s, align='center')
    return ih * s + 12 * s


def block_text(cv, x, y, w, s, P, text, size=20, color=INK, bold=False):
    return para(cv, text, x, y, w, size * s, color, bold=bold)


def run_blocks(cv, x, y, w, s, P, blocks):
    """blocks: list of ('name', kwargs) or ('cols', [(frac, [blocks]), ...])"""
    for b in blocks:
        kind = b[0]
        if kind == 'cols':
            gap = 24 * s
            cols = b[1]
            tot = sum(f for f, _ in cols)
            cx = x
            hmax = 0
            for f, sub in cols:
                cw = (w - gap * (len(cols) - 1)) * f / tot
                hmax = max(hmax, run_blocks(cv, cx, y, cw, s, P, sub) - y)
                cx += cw + gap
            y += hmax
        elif kind == 'gap':
            y += b[1] * s
        else:
            fn = BLOCKS[kind]
            kw = b[1] if len(b) > 1 else {}
            y += fn(cv, x, y, w, s, P, **kw)
    return y


BLOCKS = dict(steps=block_steps, codes=block_codes, table=block_table, nutrition=block_nutrition, notes=block_notes,
              maker=block_maker, image=lambda cv, x, y, w, s, P, spec: block_image(cv, x, y, w, s, P, spec),
              text=block_text)


# ------------------------------------------------------------------ the generic bag back
def bag_back(P, aspect, px=1500):
    """P: spec dict. aspect = physical height / width. Returns rendered design array."""
    W = 1000.0
    H = W * aspect
    lo, hi = 0.3, P.get('max_scale', 1.5)
    s = None
    for attempt in range(10):
        last = attempt == 9
        s = lo if last else (lo + hi) / 2
        cv = rc.Canvas(W, H, bg=P['bg'])
        bt = P.get('band_h', 0) * H
        if P.get('bg_draw'):
            P['bg_draw'](cv, W, H)
        if bt:
            crimp_band(cv, 0, bt, P.get('band', P['bg']), P.get('band_line', '#000000'), top=True)
            crimp_band(cv, H - bt, bt, P.get('band', P['bg']), P.get('band_line', '#000000'), top=False)
        if P.get('seams', True):
            side_seams(cv, bt, H - bt, P.get('band_line', '#000000'))
        y = bt + P.get('head_pad', 16)
        if P.get('header'):
            y = P['header'](cv, W, H, y)
        m = P.get('margin', 40)
        top = y
        bottom = H - bt - P.get('bottom_pad', 22)
        cv.rect(m, top, W - 2 * m, bottom - top, P.get('panel', '#ffffff'), r=26)
        inner = 24
        yend = run_blocks(cv, m + inner, top + inner, W - 2 * m - 2 * inner, s, P, P['blocks'])
        if last:
            if P.get('footer'):
                P['footer'](cv, W, H, yend, bottom)
            print('R049 layout %s scale %.3f fill %.2f' % (P.get('name', '?'), s, (yend - top) / (bottom - top)))
            return cv.render(px)
        if yend <= bottom - 10:
            lo = s
        else:
            hi = s
