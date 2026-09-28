"""r049_compose - tiny 2D label composer that runs inside Blender (bpy + numpy, no Pillow).

A design is drawn in "design units" (top-left origin, x right, y down) on a W x H canvas whose
aspect equals the physical aspect of the printed surface. Elements are real Blender objects
(flat emission materials, orthographic camera, Standard view transform), so text is rendered
with a real font (Malgun Gothic from C:\\Windows\\Fonts; falls back to Blender's bundled CJK font).

    cv = Canvas(1000, 1230, bg='#f3f1ea')
    cv.rect(40, 40, 920, 300, '#e05a1a', r=18)
    cv.text('조리법', 60, 60, 40, '#ffffff', bold=True)
    cv.image(png, (l, t, r, b), 60, 120, 300, 200)      # crop in image fractions, top-left origin
    cv.barcode(600, 60, 300, 120, '8801043014731')
    arr = cv.render(1400)                               # float32 (h, w, 4), row 0 = top, sRGB

Helpers: place(arr, tex_w, tex_h, rect, fill) puts a design into a u/v rect of a texture;
save_png(arr, path); load_png(path) -> array (row 0 = top); paa2png / png2paa via ImageToPAA.
"""
import bpy, os, math, subprocess
import numpy as np

IMAGETOPAA = r"C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe"
FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
_fonts = {}


def font(bold=False):
    key = 'b' if bold else 'r'
    if key not in _fonts:
        path = os.path.join(FONT_DIR, 'malgunbd.ttf' if bold else 'malgun.ttf')
        if not os.path.isfile(path):
            path = os.path.join(os.path.dirname(bpy.app.binary_path), '%d.%d' % bpy.app.version[:2],
                                'datafiles', 'fonts', 'Noto Sans CJK Regular.woff2')
        _fonts[key] = bpy.data.fonts.load(path, check_existing=True)
    return _fonts[key]


def hex2rgb(c):
    if isinstance(c, (tuple, list)):
        return tuple(c[:3])
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# ---------------------------------------------------------------- image io
def load_png(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1].copy()


def save_png(arr, path):
    h, w = arr.shape[:2]
    im = bpy.data.images.new('out', w, h, alpha=True)
    im.pixels.foreach_set(np.clip(arr[::-1], 0, 1).astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save()
    bpy.data.images.remove(im)


def paa2png(paa, png):
    if not os.path.isfile(png) or os.path.getmtime(png) < os.path.getmtime(paa):
        os.makedirs(os.path.dirname(png), exist_ok=True)
        subprocess.run([IMAGETOPAA, paa, png], check=True, capture_output=True)
    return png


def png2paa(png, paa):
    if os.path.exists(paa):
        os.remove(paa)
    subprocess.run([IMAGETOPAA, png, paa], check=True, capture_output=True)
    assert os.path.isfile(paa), paa
    return paa


def resample(arr, w, h):
    """Bilinear (area-ish for downscale via pre-box) resize, row 0 = top."""
    sh, sw = arr.shape[:2]
    # box pre-filter when shrinking a lot
    while sw >= 2 * w and sh >= 2 * h:
        arr = arr[:sh // 2 * 2, :sw // 2 * 2]
        arr = (arr[0::2, 0::2] + arr[1::2, 0::2] + arr[0::2, 1::2] + arr[1::2, 1::2]) / 4
        sh, sw = arr.shape[:2]
    ys = (np.arange(h) + .5) * sh / h - .5
    xs = (np.arange(w) + .5) * sw / w - .5
    y0 = np.clip(np.floor(ys).astype(int), 0, sh - 1); y1 = np.clip(y0 + 1, 0, sh - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, sw - 1); x1 = np.clip(x0 + 1, 0, sw - 1)
    fy = np.clip(ys - y0, 0, 1)[:, None, None]; fx = np.clip(xs - x0, 0, 1)[None, :, None]
    a = arr[y0][:, x0]; b = arr[y0][:, x1]; c = arr[y1][:, x0]; d = arr[y1][:, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def place(design, tex_w, tex_h, rect, fill=None):
    """Put `design` into texture pixels covering uv rect (u0, v0, u1, v1) (v=0 top, DayZ convention).
    Outside the rect the design's edge pixels are extended (or `fill` colour)."""
    u0, v0, u1, v1 = rect
    x0, x1 = int(round(u0 * tex_w)), int(round(u1 * tex_w))
    y0, y1 = int(round(v0 * tex_h)), int(round(v1 * tex_h))
    d = resample(design, x1 - x0, y1 - y0)
    out = np.zeros((tex_h, tex_w, 4), np.float32)
    if fill is None:
        # edge extension
        ys = np.clip(np.arange(tex_h) - y0, 0, y1 - y0 - 1)
        xs = np.clip(np.arange(tex_w) - x0, 0, x1 - x0 - 1)
        out[:] = d[ys][:, xs]
    else:
        out[:] = list(hex2rgb(fill)) + [1]
        out[y0:y1, x0:x1] = d
    out[..., 3] = 1
    return out


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, W, H, bg='#ffffff'):
        self.W, self.H = float(W), float(H)
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras):
            for x in list(coll):
                coll.remove(x)
        for im in list(bpy.data.images):
            if im.users == 0:
                bpy.data.images.remove(im)
        self.z = 0.0
        self._mats = {}
        self._imgs = {}
        sc = bpy.context.scene
        self.scene = sc
        sc.render.engine = 'BLENDER_EEVEE'
        try:
            sc.eevee.taa_render_samples = 24
        except Exception:
            pass
        sc.render.film_transparent = False
        sc.render.filter_size = 0.9
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.look = 'None'
        sc.view_settings.exposure = 0
        sc.view_settings.gamma = 1
        sc.display_settings.display_device = 'sRGB'
        if sc.world is None:
            sc.world = bpy.data.worlds.new('w')
        sc.world.use_nodes = True
        bgc = hex2rgb(bg)
        sc.world.node_tree.nodes['Background'].inputs[0].default_value = (*[s2l(c) for c in bgc], 1)
        sc.world.node_tree.nodes['Background'].inputs[1].default_value = 1
        self.rect(0, 0, W, H, bg)

    # -- materials
    def _mat(self, color, alpha=1.0):
        key = (hex2rgb(color), alpha)
        if key in self._mats:
            return self._mats[key]
        m = bpy.data.materials.new('c%d' % len(self._mats))
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs[0].default_value = (*[s2l(c) for c in key[0]], 1)
        em.inputs[1].default_value = 1
        if alpha < 1:
            tr = nt.nodes.new('ShaderNodeBsdfTransparent')
            mix = nt.nodes.new('ShaderNodeMixShader')
            mix.inputs[0].default_value = alpha
            nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs[0])
            self._blend(m)
        else:
            nt.links.new(em.outputs[0], out.inputs[0])
        self._mats[key] = m
        return m

    @staticmethod
    def _blend(m):
        for attr, val in (('surface_render_method', 'BLENDED'), ('blend_method', 'BLEND')):
            try:
                setattr(m, attr, val)
            except Exception:
                pass

    def _img_mat(self, path, alpha=True, tint=None, opacity=1.0):
        key = (path, alpha, tint, opacity)
        if key in self._mats:
            return self._mats[key]
        im = self._imgs.get(path) or bpy.data.images.load(path, check_existing=True)
        self._imgs[path] = im
        m = bpy.data.materials.new('i%d' % len(self._mats))
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = im; tx.interpolation = 'Cubic'
        tx.extension = 'EXTEND'
        em = nt.nodes.new('ShaderNodeEmission')
        col = tx.outputs[0]
        if tint is not None:
            mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
            mul.inputs[0].default_value = 1
            nt.links.new(tx.outputs[0], mul.inputs[6])
            mul.inputs[7].default_value = (*[s2l(c) for c in hex2rgb(tint)], 1)
            col = mul.outputs[2]
        nt.links.new(col, em.inputs[0])
        if alpha or opacity < 1:
            tr = nt.nodes.new('ShaderNodeBsdfTransparent')
            mix = nt.nodes.new('ShaderNodeMixShader')
            if alpha and opacity < 1:
                mt = nt.nodes.new('ShaderNodeMath'); mt.operation = 'MULTIPLY'
                nt.links.new(tx.outputs[1], mt.inputs[0]); mt.inputs[1].default_value = opacity
                nt.links.new(mt.outputs[0], mix.inputs[0])
            elif alpha:
                nt.links.new(tx.outputs[1], mix.inputs[0])
            else:
                mix.inputs[0].default_value = opacity
            nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs[0])
            self._blend(m)
        else:
            nt.links.new(em.outputs[0], out.inputs[0])
        self._mats[key] = m
        return m

    def _next_z(self):
        self.z += 0.01
        return self.z

    def _mesh(self, polys, mat, uvs=None, name='m'):
        """polys: list of lists of (x, y) design coords (y down)."""
        z = self._next_z()
        verts, faces = [], []
        for p in polys:
            idx = []
            for x, y in p:
                idx.append(len(verts)); verts.append((x, -y, z))
            faces.append(idx)
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        if uvs is not None:
            uvl = me.uv_layers.new()
            k = 0
            for poly in me.polygons:
                for li in poly.loop_indices:
                    uvl.data[li].uv = uvs[me.loops[li].vertex_index]
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    # -- primitives
    @staticmethod
    def _rrect_pts(x, y, w, h, r, seg=8):
        r = max(0.0, min(r, w / 2, h / 2))
        if r <= 0:
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        pts = []
        for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
            for i in range(seg + 1):
                a = math.radians(a0 + 90 * i / seg)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    def rect(self, x, y, w, h, color, r=0, alpha=1.0):
        pts = self._rrect_pts(x, y, w, h, r)
        # counter-clockwise when seen from +Z (camera): design y is flipped, so reverse
        return self._mesh([pts[::-1]], self._mat(color, alpha))

    def frame(self, x, y, w, h, color, t=2, r=0):
        """Outline of a (rounded) rectangle, thickness t."""
        o = self._rrect_pts(x, y, w, h, r)
        i = self._rrect_pts(x + t, y + t, w - 2 * t, h - 2 * t, max(0, r - t))
        n = len(o)
        if len(i) != n:
            i = self._rrect_pts(x + t, y + t, w - 2 * t, h - 2 * t, max(0.01, r - t))
        polys = [[o[k], i[k], i[(k + 1) % n], o[(k + 1) % n]][::-1] for k in range(n)]
        return self._mesh(polys, self._mat(color))

    def line(self, x0, y0, x1, y1, color, t=2):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L * t / 2, dx / L * t / 2
        p = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
        return self._mesh([p[::-1]], self._mat(color))

    def poly(self, pts, color, alpha=1.0):
        # ensure CCW in view (design y down -> clockwise in design coords)
        area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
        if area > 0:
            pts = pts[::-1]
        return self._mesh([pts], self._mat(color, alpha))

    def circle(self, cx, cy, r, color, seg=48):
        pts = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        return self.poly(pts, color)

    def rects(self, rects, color):
        polys = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)][::-1] for x, y, w, h in rects]
        return self._mesh(polys, self._mat(color))

    def image(self, path, crop, x, y, w, h, alpha=True, tint=None, opacity=1.0):
        """crop = (l, t, r, b) fractions of the image, top-left origin."""
        l, t, r, b = crop
        pts = [(x, y + h), (x + w, y + h), (x + w, y), (x, y)]
        uvs = [(l, 1 - b), (r, 1 - b), (r, 1 - t), (l, 1 - t)]
        return self._mesh([pts], self._img_mat(path, alpha, tint, opacity), uvs=uvs, name='img')

    def image_fit(self, path, crop, x, y, w=None, h=None, align='left', alpha=True):
        """Keep pixel aspect: give w or h (or both = box, fitted inside)."""
        im = self._imgs.get(path) or bpy.data.images.load(path, check_existing=True)
        self._imgs[path] = im
        iw, ih = im.size
        l, t, r, b = crop
        asp = (r - l) * iw / ((b - t) * ih)
        if w is not None and h is not None:
            bw, bh = w, h
            if bw / bh > asp:
                w = bh * asp
            else:
                h = bw / asp
            if align == 'center':
                x += (bw - w) / 2
            elif align == 'right':
                x += bw - w
            y += (bh - h) / 2
        elif w is not None:
            h = w / asp
        else:
            w = h * asp
            if align == 'center':
                x -= w / 2
            elif align == 'right':
                x -= w
        self.image(path, crop, x, y, w, h, alpha=alpha)
        return x, y, w, h

    def text(self, s, x, y, size, color, bold=False, align='left', width=None, spacing=1.0, char_spacing=1.0,
             anchor='top', scale_x=1.0):
        """Draw text; (x, y) = top-left (align left), top-centre (center), top-right (right).
        width: wrap width in design units. Returns the object."""
        cu = bpy.data.curves.new('t', 'FONT')
        cu.body = s
        cu.font = font(bold)
        cu.size = 1.0
        cu.align_x = {'left': 'LEFT', 'center': 'CENTER', 'right': 'RIGHT', 'justify': 'JUSTIFY'}[align]
        cu.align_y = {'top': 'TOP', 'center': 'CENTER', 'bottom': 'BOTTOM', 'baseline': 'TOP_BASELINE'}[anchor]
        cu.space_line = spacing
        cu.space_character = char_spacing
        if width is not None:
            cu.text_boxes[0].width = width / size / scale_x
            if align == 'center':
                cu.text_boxes[0].x = -width / size / scale_x / 2
            elif align == 'right':
                cu.text_boxes[0].x = -width / size / scale_x
        cu.materials.append(self._mat(color))
        ob = bpy.data.objects.new('t', cu)
        ob.scale = (size * scale_x, size, 1)
        ob.location = (x, -y, self._next_z())
        bpy.context.scene.collection.objects.link(ob)
        return ob

    def text_width(self, s, size, bold=False, scale_x=1.0):
        ob = self.text(s, 0, 0, size, '#000000', bold=bold, scale_x=scale_x)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        xs = [v.co.x for v in me.vertices]
        w = (max(xs) - min(xs)) * size * scale_x if xs else 0
        ob.evaluated_get(dg).to_mesh_clear()
        bpy.data.objects.remove(ob, do_unlink=True)
        return w

    def text_fit(self, s, x, y, maxw, size, color, bold=False, align='left', anchor='top'):
        """Single line, horizontally squeezed if wider than maxw."""
        w = self.text_width(s, size, bold)
        sx = min(1.0, maxw / w) if w > 0 else 1.0
        return self.text(s, x, y, size, color, bold=bold, align=align, anchor=anchor, scale_x=sx)

    def barcode(self, x, y, w, h, digits, color='#111111', bg='#ffffff', text=True):
        """EAN-13 style bars (drawn, not validated)."""
        L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011']
        G = ['0100111', '0110011', '0011011', '0100001', '0011101', '0111001', '0000101', '0010001', '0001001', '0010111']
        R = [''.join('1' if c == '0' else '0' for c in p) for p in L]
        par = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL']
        d = [int(c) for c in digits[:13].ljust(13, '0')]
        bits = '101'
        for i, c in enumerate(d[1:7]):
            bits += (L if par[d[0]][i] == 'L' else G)[c]
        bits += '01010'
        for c in d[7:13]:
            bits += R[c]
        bits += '101'
        pad = w * 0.06
        th = h * 0.2 if text else 0
        self.rect(x - pad, y - pad * 0.5, w + 2 * pad, h + pad, bg)
        m = w / len(bits)
        rects = []
        i = 0
        while i < len(bits):
            if bits[i] == '1':
                j = i
                while j < len(bits) and bits[j] == '1':
                    j += 1
                guard = i < 3 or 45 <= i < 50 or i >= 92
                rects.append((x + i * m, y, (j - i) * m, h - th + (th * 0.5 if guard else 0)))
                i = j
            else:
                i += 1
        self.rects(rects, color)
        if text:
            s = digits[0] + '  ' + digits[1:7] + '  ' + digits[7:13]
            self.text_fit(s, x + w / 2, y + h - th * 0.95, w * 1.05, th * 0.95, color, align='center')

    def render(self, px_long=1400):
        sc = self.scene
        cam_data = bpy.data.cameras.new('cam')
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = max(self.W, self.H)
        cam_data.clip_start = 0.01
        cam_data.clip_end = 1000
        cam = bpy.data.objects.new('cam', cam_data)
        cam.location = (self.W / 2, -self.H / 2, self.z + 10)
        sc.collection.objects.link(cam)
        sc.camera = cam
        if self.W >= self.H:
            rw, rh = px_long, int(round(px_long * self.H / self.W))
        else:
            rw, rh = int(round(px_long * self.W / self.H)), px_long
        sc.render.resolution_x, sc.render.resolution_y = rw, rh
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = 'PNG'
        sc.render.image_settings.color_mode = 'RGBA'
        tmp = os.path.join(bpy.app.tempdir or os.environ.get('TEMP', '.'), 'r049_compose_tmp.png')
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        arr = load_png(tmp)
        arr[..., 3] = 1
        return arr
