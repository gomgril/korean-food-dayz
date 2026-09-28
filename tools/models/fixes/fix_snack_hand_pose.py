"""Hand pose for the upright opened snacks (0.4.9, fix group 1 "hand").

fix_snack_upright.py turned the opened Pepero x6 / yanggaeng x2 models back upright (file +Y = bite
end) by a pure 180-degree rotation about the file X axis through the model origin. With the vanilla
Zagorky in-hands IK pose the upright model is held "backwards" (bite end away from the mouth).

Instead of flipping the model again, this script derives a new IK pose from the vanilla one:

    source\\KF_Pantry\\anims\\kf_snack_inverted.anm = dz/anims/anm/player/ik/gear/zagorky.anm with the
    RightHand_Dummy bone (the bone the item in hand is attached to, origin to origin) rotated
    180 degrees about its OWN X axis: q' = q * (x=1, y=0, z=0, w=0).

Everything else in the file (all finger / hand / forearm tracks, FPS, bone list, key counts) is kept
byte-identical, so the hand looks exactly like the vanilla Zagorky grip and the item in the hand is
placed exactly as the old flipped models (v0.4.5..0.4.8) were with zagorky.anm: model point
(x, y, z) of the upright model lands where (x, -y, -z) of the old flipped model landed.

ANM ("FORM....ANIMSET6", Enfusion) layout, decoded here and checked on vanilla + JD demo files
(JD_SVD_IK.anm vs its .txa matches to 1e-5):
  chunks FPS (u32 LE), HEAD, DATA (chunk sizes big-endian)
  HEAD: per bone  f32 tMin,tRange,qMin,qRange,sMin,sRange (LE); u16 flag,nT,nQ,nS (LE);
        u16 BE name length; name
  DATA: per bone (HEAD order) u16 tFrame[nT], u16 t[3*nT], u16 sFrame[nS], u16 s[3*nS],
        u16 qFrame[nQ], u16 q[4*nQ] (x y z w); value = min + range * u / 65535

Run:  <python> tools/models/fixes/fix_snack_hand_pose.py [--src <zagorky.anm>] [--axis x|y|z]
      (default --src is the mounted work drive P:/DZ/anims/anm/player/ik/gear/zagorky.anm)
"""
import argparse, hashlib, json, math, struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
REPO = TOOLS.parents[1]
OUT = REPO / 'source' / 'KF_Pantry' / 'anims' / 'kf_snack_inverted.anm'
BONE = 'RightHand_Dummy'


def parse(b):
    assert b[:4] == b'FORM' and b[8:16] == b'ANIMSET6', 'not an ANIMSET6 file'
    assert struct.unpack('>I', b[4:8])[0] + 8 == len(b) and struct.unpack('>I', b[16:20])[0] + 20 == len(b)
    ch, off = {}, 20
    while off < len(b):
        cid, size = b[off:off + 4], struct.unpack('>I', b[off + 4:off + 8])[0]
        ch[cid] = (off + 8, size)
        off += 8 + size
    assert off == len(b) and set(ch) == {b'FPS\0', b'HEAD', b'DATA'}, ch.keys()
    ho, hs = ch[b'HEAD']
    do, ds = ch[b'DATA']
    bones, p, wp = [], ho, 0
    while p < ho + hs:
        hdr = p
        f = struct.unpack('<6f', b[p:p + 24]); p += 24
        flag, nt, nq, ns = struct.unpack('<4H', b[p:p + 8]); p += 8
        n = struct.unpack('>H', b[p:p + 2])[0]; p += 2
        name = b[p:p + n].decode('ascii'); p += n
        words = nt * 4 + ns * 4 + nq * 5
        qwords = do + 2 * (wp + nt * 4 + ns * 4 + nq)  # byte offset of the first q component
        bones.append(dict(name=name, hdr=hdr, f=f, flag=flag, nt=nt, nq=nq, ns=ns, qoff=qwords))
        wp += words
    assert p == ho + hs and 2 * wp == ds, 'HEAD/DATA size mismatch'
    fps = struct.unpack('<I', b[ch[b'FPS\0'][0]:ch[b'FPS\0'][0] + 4])[0]
    return fps, bones


def quats(b, bone):
    qmin, qr = bone['f'][2], bone['f'][3]
    w = struct.unpack('<%dH' % (4 * bone['nq']), b[bone['qoff']:bone['qoff'] + 8 * bone['nq']])
    return [[qmin + qr * u / 65535.0 for u in w[4 * i:4 * i + 4]] for i in range(bone['nq'])]


def qmul(a, c):  # Hamilton product, (x, y, z, w)
    ax, ay, az, aw = a; cx, cy, cz, cw = c
    return [aw * cx + ax * cw + ay * cz - az * cy,
            aw * cy - ax * cz + ay * cw + az * cx,
            aw * cz + ax * cy - ay * cx + az * cw,
            aw * cw - ax * cx - ay * cy - az * cz]


def qrot(q, v):
    r = qmul(qmul(q, [v[0], v[1], v[2], 0.0]), [-q[0], -q[1], -q[2], q[3]])
    return r[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default='P:/DZ/anims/anm/player/ik/gear/zagorky.anm')
    ap.add_argument('--axis', default='x', choices='xyz', help='item axis for the 180 degree turn (default x = same as fix_snack_upright)')
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    src = Path(a.src).read_bytes()
    fps, bones = parse(src)
    d = next(x for x in bones if x['name'] == BONE)
    old = quats(src, d)
    turn = {'x': [1.0, 0, 0, 0], 'y': [0, 1.0, 0, 0], 'z': [0, 0, 1.0, 0]}[a.axis]
    new = [qmul(q, turn) for q in old]
    flat = [c for q in new for c in q]
    qmin, qmax = min(flat), max(flat)
    qr = qmax - qmin
    words = [max(0, min(65535, int(round((c - qmin) / qr * 65535)))) for c in flat]
    out = bytearray(src)
    struct.pack_into('<2f', out, d['hdr'] + 8, qmin, qr)
    struct.pack_into('<%dH' % len(words), out, d['qoff'], *words)
    out = bytes(out)

    # ---- verification
    fps2, bones2 = parse(out)
    assert fps2 == fps and [(x['name'], x['flag'], x['nt'], x['nq'], x['ns']) for x in bones2] == \
        [(x['name'], x['flag'], x['nt'], x['nq'], x['ns']) for x in bones]
    d2 = next(x for x in bones2 if x['name'] == BONE)
    changed = [i for i in range(len(src)) if src[i] != out[i]]
    allowed = set(range(d['hdr'] + 8, d['hdr'] + 16)) | set(range(d['qoff'], d['qoff'] + 8 * d['nq']))
    assert len(out) == len(src) and set(changed) <= allowed, 'bytes outside the RightHand_Dummy rotation changed'
    for x, y in zip(bones, bones2):
        if x['name'] != BONE:
            assert quats(src, x) == quats(out, y)
    got = quats(out, d2)
    err_q = max(abs(g - n) for gq, nq in zip(got, new) for g, n in zip(gq, nq))
    norms = [math.sqrt(sum(c * c for c in q)) for q in got]
    # upright model point p with the new pose == flipped-model point R_axis(p) with the vanilla pose
    probe = {'kf_bite_end': (0.000443, 0.062, 0.0), 'kf_grip_center': (0.000443, -0.025, 0.0), 'top_107mm': (0.0, 0.107, 0.012)}
    flip = {'x': lambda v: (v[0], -v[1], -v[2]), 'y': lambda v: (-v[0], v[1], -v[2]), 'z': lambda v: (-v[0], -v[1], v[2])}[a.axis]
    err_p = max(abs(u - w) for p in probe.values() for u, w in zip(qrot(got[0], p), qrot(old[0], flip(p))))
    assert err_q < 2e-4 and all(abs(n - 1) < 1e-3 for n in norms) and err_p < 5e-5, (err_q, norms, err_p)

    Path(a.out).write_bytes(out)
    rep = dict(source=Path(a.src).name, source_sha256=hashlib.sha256(src).hexdigest(), source_bytes=len(src),
               output=str(Path(a.out).relative_to(REPO)) if Path(a.out).is_relative_to(REPO) else Path(a.out).name,
               output_sha256=hashlib.sha256(out).hexdigest(), output_bytes=len(out), fps=fps, bones=len(bones),
               bone=BONE, axis=a.axis, dummy_q_old_xyzw=old[0], dummy_q_new_xyzw=got[0],
               q_quantization_error=err_q, q_norms=norms, changed_bytes=len(changed),
               item_point_match_error_m=err_p,
               in_hand_equivalent='upright model with this pose == v0.4.8 flipped model with zagorky.anm')
    (TOOLS / 'reports').mkdir(exist_ok=True)
    (TOOLS / 'reports' / 'fix_snack_hand_pose.json').write_text(json.dumps(rep, indent=1), encoding='utf8')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
