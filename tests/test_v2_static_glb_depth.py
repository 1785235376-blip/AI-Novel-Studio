"""Actual CPU PNG pixels and read-only original asset source; no model/GPU."""
from copy import deepcopy
import base64
import hashlib
import struct
import zlib
import pytest
from app.creative.model_reference_depth import render_depth,WIDTH,HEIGHT
from app.creative.model_reference_glb import inspect_static_glb
from test_v2_static_glb_inspection import glb


def scene():return inspect_static_glb(glb(),include_geometry=True,include_scene=True)['scene_preview']


def pixels(png):
    assert png[:8]==b'\x89PNG\r\n\x1a\n';pos=8;compressed=b''
    while pos<len(png):
        size=struct.unpack_from('>I',png,pos)[0];kind=png[pos+4:pos+8];data=png[pos+8:pos+8+size]
        assert zlib.crc32(kind+data)&0xffffffff==struct.unpack_from('>I',png,pos+8+size)[0]
        if kind==b'IHDR':assert struct.unpack('>IIBBBBB',data)==(WIDTH,HEIGHT,8,0,0,0,0)
        if kind==b'IDAT':compressed+=data
        pos+=12+size
    raw=zlib.decompress(compressed);assert len(raw)==HEIGHT*(WIDTH+1)
    assert all(raw[y*(WIDTH+1)]==0 for y in range(HEIGHT))
    return b''.join(raw[y*(WIDTH+1)+1:(y+1)*(WIDTH+1)] for y in range(HEIGHT))


def test_flat_geometry_has_real_covered_pixels_and_deterministic_png():
    original=scene();before=deepcopy(original);png,proof=render_depth(original,0,0);plane=pixels(png)
    assert plane[0]==0 and plane[(HEIGHT//2)*WIDTH+WIDTH//2]==255
    assert proof['covered_pixels']==sum(v!=0 for v in plane)>0
    assert set(plane)=={0,255} and hashlib.sha256(png).hexdigest()==proof['png_sha256']
    assert render_depth(original,0,0)==(png,proof) and original==before
    assert proof['metric_depth'] is False and proof['asset_created'] is False


def test_nearer_triangle_occludes_farther_independent_of_face_order():
    value=scene();first=value['primitives'][0];other=deepcopy(first)
    for p in other['positions']:p[2]=1
    other['node_index']=1;value['primitives'].append(other);value['bounds']['max'][2]=1
    png,_=render_depth(value,0,0);value['primitives'].reverse();reverse,_=render_depth(value,0,0)
    assert png==reverse and pixels(png)[(HEIGHT//2)*WIDTH+WIDTH//2]==255


def test_slanted_plane_contains_depth_gradient_and_checkpoint_can_abort():
    png,proof=render_depth(scene(),0,30);assert len(set(pixels(png)))>20
    assert proof['covered_pixels']>0 and proof['pixel_tests']<=2_000_000
    calls=[]
    def denied():calls.append(1);raise PermissionError('revoked')
    with pytest.raises(PermissionError):render_depth(scene(),0,0,checkpoint=denied)
    assert calls


def test_rejects_work_budget_and_invalid_camera():
    value=scene();value['primitives'][0]['triangles']*=300
    with pytest.raises(ValueError,match='DEPTH_LIMIT'):render_depth(value,0,0)
    for yaw,pitch in [(True,0),(float('nan'),0),(10**500,0),(0,90)]:
        with pytest.raises(ValueError):render_depth(scene(),yaw,pitch)
