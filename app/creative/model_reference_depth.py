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


def _render(scene, yaw, pitch, *, clay=False, checkpoint=lambda: None):
    kind = "CLAY" if clay else "DEPTH"
    if (type(yaw) not in (int, float) or type(pitch) not in (int, float)
            or abs(yaw) > 180 or abs(pitch) > 89
            or not math.isfinite(yaw) or not math.isfinite(pitch)
            or scene.get("contract") != "studio-static-glb-scene-preview/1"
            or scene.get("scene_transforms_applied") is not True):
        raise ValueError(f"MODEL_REFERENCE_GLB_{kind}_INPUT_INVALID")
    bounds = scene['bounds']; center = [(a+b)/2 for a,b in zip(bounds['min'],bounds['max'])]
    extent = max(b-a for a,b in zip(bounds['min'],bounds['max'])) or 1
    cy,sy=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    cp,sp=math.cos(math.radians(pitch)),math.sin(math.radians(pitch))
    projected=[];minimum=math.inf;maximum=-math.inf;positions=triangles=0
    for primitive in scene['primitives']:
        checkpoint();points=[]
        positions+=len(primitive['positions']);triangles+=len(primitive['triangles'])
        if positions>4096 or triangles>2048:raise ValueError(f'MODEL_REFERENCE_GLB_{kind}_LIMIT')
        for point in primitive['positions']:
            x,y,z=[(n-center[i])*2/extent for i,n in enumerate(point)]
            rx,rz=cy*x+sy*z,-sy*x+cy*z
            ry,depth=cp*y-sp*rz,sp*y+cp*rz
            if not all(math.isfinite(n) for n in (rx,ry,depth)):raise ValueError(f'MODEL_REFERENCE_GLB_{kind}_INPUT_INVALID')
            points.append((WIDTH/2+rx*45,HEIGHT/2-ry*45,depth))
            minimum=min(minimum,depth);maximum=max(maximum,depth)
        projected.append((points,primitive['triangles']))
    if not positions or not triangles:raise ValueError(f'MODEL_REFERENCE_GLB_{kind}_EMPTY')
    plane=bytearray([255 if clay else 0])*(WIDTH*HEIGHT);zbuffer=array('d',[-math.inf])*(WIDTH*HEIGHT);tested=0;covered=0
    for points,faces in projected:
        for ids in faces:
            checkpoint();a,b,c=[points[i] for i in ids]
            denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denominator)<1e-12:continue
            shade=0
            if clay:
                # Use view-space face normals, not pixel coordinates as a
                # physical normal. Same two-sided headlight as the SVG view.
                u=((b[0]-a[0])/45,-(b[1]-a[1])/45,b[2]-a[2])
                v=((c[0]-a[0])/45,-(c[1]-a[1])/45,c[2]-a[2])
                normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                length=math.sqrt(sum(n*n for n in normal))
                shade=round(80+140*(abs(normal[2])/length if length else 0))
            x0=max(0,math.floor(min(a[0],b[0],c[0])));x1=min(WIDTH-1,math.ceil(max(a[0],b[0],c[0])))
            y0=max(0,math.floor(min(a[1],b[1],c[1])));y1=min(HEIGHT-1,math.ceil(max(a[1],b[1],c[1])))
            tested+=max(0,x1-x0+1)*max(0,y1-y0+1)
            if tested>MAX_PIXEL_TESTS:raise ValueError(f'MODEL_REFERENCE_GLB_{kind}_LIMIT')
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
                    plane[index]=shade if clay else max(1,min(255,1+round(254*fraction)))
    if not covered:raise ValueError(f'MODEL_REFERENCE_GLB_{kind}_EMPTY')
    checkpoint()
    # Reuse the existing deterministic bounded grayscale PNG byte encoder only,
    # not binary-mask validation, meaning or persistence.
    from ..services.studio_image_mask_authoring import _png
    raw=b''.join(b'\0'+plane[y*WIDTH:(y+1)*WIDTH] for y in range(HEIGHT))
    png=_png(raw,WIDTH,HEIGHT);checkpoint()
    proof={'contract':'studio-static-glb-clay-export/1' if clay else CONTRACT,'width':WIDTH,'height':HEIGHT,'yaw':float(yaw),'pitch':float(pitch),
        'projection':'ORTHOGRAPHIC_DIAGNOSTIC','depth_encoding':'BACKGROUND_0_FAR_1_NEAR_255',
        'metric_depth':False,'covered_pixels':covered,'pixel_tests':tested,'png_sha256':hashlib.sha256(png).hexdigest(),
        'scene_index':scene['scene_index'],'scene_selection':scene['selection'],'scene_transforms_applied':True,
        'materials_rendered':False,'animation_applied':False,'model_called':False,'asset_created':False}

    if clay:
        proof.pop('depth_encoding');proof.pop('metric_depth')
        proof.update(shading='TWO_SIDED_FLAT_HEADLIGHT',background=255,physical_lighting=False)
    return png,proof


def render_depth(scene, yaw, pitch, *, checkpoint=lambda: None):
    return _render(scene,yaw,pitch,checkpoint=checkpoint)


def render_clay(scene, yaw, pitch, *, checkpoint=lambda: None):
    return _render(scene,yaw,pitch,clay=True,checkpoint=checkpoint)
