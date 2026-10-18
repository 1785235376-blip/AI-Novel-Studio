"""Bounded CPU orthographic depth diagnostic from already verified scene geometry.

Not a physical camera, metric depth, material render, pose estimator or model.
The PNG is a download candidate only; no Asset/Job/Review owner is created here.
"""
from __future__ import annotations
from array import array
import hashlib
import math

CONTRACT = "studio-static-glb-depth-export/1"
WIDTH, HEIGHT = 256, 192
MAX_PIXEL_TESTS = 2_000_000


def render_depth(scene, yaw, pitch, *, checkpoint=lambda: None):
    if (type(yaw) not in (int, float) or type(pitch) not in (int, float)
            or abs(yaw) > 180 or abs(pitch) > 89
            or not math.isfinite(yaw) or not math.isfinite(pitch)
            or scene.get("contract") != "studio-static-glb-scene-preview/1"
            or scene.get("scene_transforms_applied") is not True):
        raise ValueError("MODEL_REFERENCE_GLB_DEPTH_INPUT_INVALID")
    bounds = scene['bounds']; center = [(a+b)/2 for a,b in zip(bounds['min'],bounds['max'])]
    extent = max(b-a for a,b in zip(bounds['min'],bounds['max'])) or 1
    cy,sy=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    cp,sp=math.cos(math.radians(pitch)),math.sin(math.radians(pitch))
    projected=[];minimum=math.inf;maximum=-math.inf;positions=triangles=0
    for primitive in scene['primitives']:
        checkpoint();points=[]
        positions+=len(primitive['positions']);triangles+=len(primitive['triangles'])
        if positions>4096 or triangles>2048:raise ValueError('MODEL_REFERENCE_GLB_DEPTH_LIMIT')
        for point in primitive['positions']:
            x,y,z=[(n-center[i])*2/extent for i,n in enumerate(point)]
            rx,rz=cy*x+sy*z,-sy*x+cy*z
            ry,depth=cp*y-sp*rz,sp*y+cp*rz
            if not all(math.isfinite(n) for n in (rx,ry,depth)):raise ValueError('MODEL_REFERENCE_GLB_DEPTH_INPUT_INVALID')
            points.append((WIDTH/2+rx*45,HEIGHT/2-ry*45,depth))
            minimum=min(minimum,depth);maximum=max(maximum,depth)
        projected.append((points,primitive['triangles']))
    if not positions or not triangles:raise ValueError('MODEL_REFERENCE_GLB_DEPTH_EMPTY')
    plane=bytearray(WIDTH*HEIGHT);zbuffer=array('d',[-math.inf])*(WIDTH*HEIGHT);tested=0;covered=0
    for points,faces in projected:
        for ids in faces:
            checkpoint();a,b,c=[points[i] for i in ids]
            denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denominator)<1e-12:continue
            x0=max(0,math.floor(min(a[0],b[0],c[0])));x1=min(WIDTH-1,math.ceil(max(a[0],b[0],c[0])))
            y0=max(0,math.floor(min(a[1],b[1],c[1])));y1=min(HEIGHT-1,math.ceil(max(a[1],b[1],c[1])))
            tested+=max(0,x1-x0+1)*max(0,y1-y0+1)
            if tested>MAX_PIXEL_TESTS:raise ValueError('MODEL_REFERENCE_GLB_DEPTH_LIMIT')
            for y in range(y0,y1+1):
                checkpoint()
                for x in range(x0,x1+1):
                    px,py=x+.5,y+.5
                    u=((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/denominator
                    v=((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/denominator
                    w=1-u-v
                    if min(u,v,w)<-1e-10:continue
                    depth=u*a[2]+v*b[2]+w*c[2];index=y*WIDTH+x
                    if depth<=zbuffer[index]:continue
                    if zbuffer[index]==-math.inf:covered+=1
                    zbuffer[index]=depth
                    fraction=(depth-minimum)/(maximum-minimum) if maximum>minimum else 1
                    plane[index]=max(1,min(255,1+round(254*fraction)))
    if not covered:raise ValueError('MODEL_REFERENCE_GLB_DEPTH_EMPTY')
    checkpoint()
    # Reuse the existing deterministic bounded grayscale PNG byte encoder only,
    # not binary-mask validation, meaning or persistence.
    from ..services.studio_image_mask_authoring import _png
    raw=b''.join(b'\0'+plane[y*WIDTH:(y+1)*WIDTH] for y in range(HEIGHT))
    png=_png(raw,WIDTH,HEIGHT);checkpoint()
    return png,{'contract':CONTRACT,'width':WIDTH,'height':HEIGHT,'yaw':float(yaw),'pitch':float(pitch),
        'projection':'ORTHOGRAPHIC_DIAGNOSTIC','depth_encoding':'BACKGROUND_0_FAR_1_NEAR_255',
        'metric_depth':False,'covered_pixels':covered,'pixel_tests':tested,'png_sha256':hashlib.sha256(png).hexdigest(),
        'scene_index':scene['scene_index'],'scene_selection':scene['selection'],'scene_transforms_applied':True,
        'materials_rendered':False,'animation_applied':False,'model_called':False,'asset_created':False}
