from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from app.creative.model_reference_depth import render_clay,render_depth,WIDTH,HEIGHT
from test_v2_static_glb_depth import scene,pixels


def test_clay_has_actual_flat_shading_and_unchanged_original_depth_bytes():
    value=scene();before=deepcopy(value);png,proof=render_clay(value,0,0);plane=pixels(png)
    assert set(plane)=={220,255} and plane[0]==255 and proof['covered_pixels']==sum(p!=255 for p in plane)
    assert proof['shading']=='TWO_SIDED_FLAT_HEADLIGHT' and proof['physical_lighting'] is False and proof['materials_rendered'] is False
    assert hashlib.sha256(png).hexdigest()==proof['png_sha256'] and value==before
    old=json.loads((Path(__file__).parents[1]/'frontend/src/creative/modelDepthWire.testFixture.json').read_text())
    assert render_depth(value,0,0)[1]['png_sha256']==old['result']['depth_export']['png_sha256']
    assert render_clay(value,0,45)[1]['png_sha256']!=proof['png_sha256']


def test_near_slanted_face_wins_with_order_independent_clay_pixels():
    value=scene();other=deepcopy(value['primitives'][0])
    for p in other['positions']:p[2]=1+(p[0]-100)
    other['node_index']=1;value['primitives'].append(other);value['bounds']['max'][2]=2
    png,_=render_clay(value,0,0);value['primitives'].reverse();reverse,_=render_clay(value,0,0)
    assert png==reverse and pixels(png)[(HEIGHT//2)*WIDTH+WIDTH//2]==179


def test_clay_budget_and_authority_abort_are_not_partial_png():
    value=scene();value['primitives'][0]['triangles']*=300
    with pytest.raises(ValueError,match='CLAY_LIMIT'):render_clay(value,0,0)
    def denied():raise PermissionError('revoked')
    with pytest.raises(PermissionError):render_clay(scene(),0,0,checkpoint=denied)
