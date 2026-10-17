"""The inert standard module is included by actual offline PUBLIC artifacts."""
import hashlib

import pytest

from test_public_wheel_artifact import build_distribution

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_actual_public_artifact_includes_passive_binding_module(tmp_path_factory, kind):
    _, stage, _, _, _, verified = build_distribution(tmp_path_factory, kind)
    path = "app/creative/director_binding.py"
    included = {item["source_path"]: item["sha256"] for item in verified["files"]}
    assert included[path] == hashlib.sha256((stage / path).read_bytes()).hexdigest()
