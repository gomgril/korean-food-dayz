# Vendored copy of work\kf-fix045\mlod045.py from the original (pre-repository) KoreanFood workspace
# (copied unchanged on 2026-09-28, sha256 D673997F31A2287446DFAD193578D90228E0C71F00E033467A112948A9C37895). Do not edit; extend in modelfix.py.
"""Lossless MLOD access. Geometry helpers use Blender Z-up coordinates."""
import struct, math
from pathlib import Path

def unpack(data, fmt, pos):
    return struct.unpack_from('<'+fmt, data, pos)

def read(path):
    d=Path(path).read_bytes(); assert d[:4]==b'MLOD'
    version,count=unpack(d,'II',4);p=12;lods=[]
    def string():
        nonlocal p
        end=d.index(b'\0',p);v=d[p:end];p=end+1;return v.decode('utf8')
    for _ in range(count):
        assert d[p:p+4]==b'P3DM';hs,mn,nv,nn,nf,flags=unpack(d,'6I',p+4);p+=28
        assert hs==28 and mn==256
        vertices=[unpack(d,'3fI',p+i*16) for i in range(nv)];p+=nv*16
        normals=[unpack(d,'3f',p+i*12) for i in range(nn)];p+=nn*12
        faces=[]
        for _ in range(nf):
            n=unpack(d,'I',p)[0];assert n in (3,4)
            corners=[unpack(d,'IIff',p+4+i*16) for i in range(n)]
            ff=unpack(d,'I',p+68)[0];p+=72
            faces.append(dict(corners=corners,flags=ff,texture=string(),material=string()))
        assert d[p:p+4]==b'TAGG';p+=4;tags=[]
        while True:
            active=d[p];p+=1;name=string();size=unpack(d,'I',p)[0];p+=4
            tags.append(dict(active=active,name=name,data=d[p:p+size]));p+=size
            if name=='#EndOfFile#':break
        resolution=unpack(d,'f',p)[0];p+=4
        lods.append(dict(vertices=vertices,normals=normals,faces=faces,tags=tags,resolution=resolution,flags=flags,original_nv=nv,original_nf=nf))
    assert p==len(d)
    return dict(version=version,lods=lods)

def write(path,doc):
    out=bytearray(b'MLOD'+struct.pack('<II',doc['version'],len(doc['lods'])))
    for l in doc['lods']:
        nv,nn,nf=len(l['vertices']),len(l['normals']),len(l['faces'])
        out+=b'P3DM'+struct.pack('<6I',28,256,nv,nn,nf,l['flags'])
        for v in l['vertices']:out+=struct.pack('<3fI',*v)
        for n in l['normals']:out+=struct.pack('<3f',*n)
        for f in l['faces']:
            out+=struct.pack('<I',len(f['corners']))
            for c in f['corners']:out+=struct.pack('<IIff',*c)
            out+=bytes(16*(4-len(f['corners'])))+struct.pack('<I',f['flags'])
            out+=f['texture'].encode()+b'\0'+f['material'].encode()+b'\0'
        out+=b'TAGG'
        for t in l['tags']:
            data=t['data']
            if not t['name'].startswith('#'):
                oldnv,oldnf=l['original_nv'],l['original_nf']
                assert len(data)==oldnv+oldnf
                data=data[:oldnv]+bytes(nv-oldnv)+data[oldnv:]+bytes(nf-oldnf)
            out+=bytes([t['active']])+t['name'].encode()+b'\0'+struct.pack('<I',len(data))+data
        out+=struct.pack('<f',l['resolution'])
    Path(path).write_bytes(out)

def xyz(v):return (v[0],v[2],v[1])
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def length(a):return math.sqrt(dot(a,a))
def face_normal(l,f):
    vs=[xyz(l['vertices'][c[0]]) for c in f['corners']]
    n=cross(sub(vs[1],vs[0]),sub(vs[2],vs[0]));le=length(n)
    return tuple(v/le for v in n) if le else (0,0,0)
def bounds(l):
    vs=[xyz(v) for v in l['vertices']]
    return [(min(v[a] for v in vs),max(v[a] for v in vs)) for a in range(3)]
def add_face(l,points,texture,material,uv=None):
    n=cross(sub(points[1],points[0]),sub(points[2],points[0]));le=length(n)
    assert le>1e-15
    n=tuple(v/le for v in n);ni=len(l['normals'])
    l['normals'].append((-n[0],-n[2],-n[1]));cs=[]
    for i,(x,y,z) in enumerate(points):
        vi=len(l['vertices']);l['vertices'].append((x,z,y,0));u,v=uv[i] if uv else (0,0)
        cs.append((vi,ni,u,v))
    l['faces'].append(dict(corners=cs,flags=0,texture=texture,material=material))
def reverse_face(l,f):
    cs=[]
    for vi,ni,u,v in reversed(f['corners']):
        newni=len(l['normals']);l['normals'].append(tuple(-v for v in l['normals'][ni]));cs.append((vi,newni,u,v))
    f['corners']=cs

def boundary_loops(l,tolerance=1e-6):
    """Positional weld for audit only; returns simple loops plus nonmanifold stats."""
    weld={};pts=[];ids=[]
    for v in l['vertices']:
        q=xyz(v);key=tuple(round(x/tolerance) for x in q)
        if key not in weld:weld[key]=len(pts);pts.append(q)
        ids.append(weld[key])
    edges={}
    for fi,f in enumerate(l['faces']):
        vs=[ids[c[0]] for c in f['corners']]
        for a,b in zip(vs,vs[1:]+vs[:1]):
            if a==b:continue
            edges.setdefault(tuple(sorted((a,b))),[]).append((a,b,fi))
    boundary=[x[0] for x in edges.values() if len(x)==1]
    adjacency={}
    for ei,(a,b,fi) in enumerate(boundary):
        adjacency.setdefault(a,[]).append(ei);adjacency.setdefault(b,[]).append(ei)
    seen=set();loops=[]
    for ei,(a,b,_) in enumerate(boundary):
        if ei in seen:continue
        path=[a];fs=[];current=a;edge=ei
        for _ in range(len(boundary)+1):
            if edge in seen:break
            seen.add(edge);a,b,fi=boundary[edge];fs.append(fi);current=b if a==current else a;path.append(current)
            if current==path[0]:
                loops.append(dict(points=[pts[i] for i in path[:-1]],faces=fs));break
            choices=[e for e in adjacency.get(current,[]) if e not in seen]
            if len(choices)!=1:break
            edge=choices[0]
    return loops,dict(boundary_edges=len(boundary),nonmanifold_edges=sum(len(x)>2 for x in edges.values()))

def loop_area_xy(points):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))*.5
