"""Explicit reviewed standard modules, preserving the original PUBLIC closure."""
import json
from test_public_build_profile import ROOT,build

def test_current_standard_feature_modules_are_explicitly_in_public_manifest():
    names={'app/bailian_text_preset.py','app/creative/model_reference_depth.py',
        'app/creative/model_reference_glb.py','app/creative/model_reference_materials.py',
        'app/creative/model_reference_scene.py','app/creative/screenplay_model.py',
        'app/services/studio_model_reference_origin.py'}
    manifest=build.load_manifest(ROOT/'packaging/public-build.json')
    assert manifest['profile']=='PUBLIC' and manifest['excluded_namespace']==build.PRIVATE=='studio_private_extensions'
    files=build.check_source(ROOT,manifest)
    assert names.issubset(files)
    assert not any(path.startswith('studio_private_extensions/') for path in files)
