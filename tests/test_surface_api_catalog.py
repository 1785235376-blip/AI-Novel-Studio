"""The final source catalog must describe the shipped owners, never an old tree."""
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def catalog():
    index = json.loads((ROOT / "API_CATALOG.json").read_text())
    detail = (ROOT / index["detail"]["path"]).read_bytes()
    assert hashlib.sha256(detail).hexdigest() == index["detail"]["sha256"]
    value = json.loads(gzip.decompress(detail))
    for key in ("summary", "application_python_source_hashes", "application_source_fingerprint_sha256"):
        assert value[key] == index[key]
    assert [(row["method"], row["path"], row["operation_sha256"]) for row in index["operations"]] == [(row["method"], row["path"], row["operation_sha256"]) for row in value["operations"]]
    return value


def test_catalog_is_bound_to_every_current_application_source():
    value = catalog()
    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted((ROOT / "app").rglob("*.py"))}
    assert value["application_python_source_hashes"] == sources
    assert value["application_source_fingerprint_sha256"] == hashlib.sha256(encoded(sources)).hexdigest()
    assert value["status"] == "COMPLETE_MOUNTED_SOURCE_CATALOG_NOT_TEST_VERDICT"


def test_catalog_retains_complete_openapi_operations_and_schema_graphs():
    value = catalog()
    spec = json.loads(gzip.decompress((ROOT / "API_OPENAPI.json.gz").read_bytes()))
    operations = {method.upper() + " " + path: operation
                  for path, methods in spec["paths"].items()
                  for method, operation in methods.items() if method in METHODS}
    rows = {row["method"] + " " + row["path"]: row for row in value["operations"]}
    assert len(rows) == len(value["operations"]) == value["summary"]["current_method_paths"]
    assert set(rows) == set(operations)
    assert value["openapi_schemas"] == spec["components"]["schemas"]
    for key, row in rows.items():
        assert row["operation_sha256"] == hashlib.sha256(encoded(operations[key])).hexdigest()
        assert row["owner_ref"] in value["owners"]
        assert set(row["schema_refs"]) <= value["openapi_schemas"].keys()
        assert set(row["source_validation_model_refs"]) <= value["source_validation_models"].keys()
    assert value["summary"]["removed"] == 0
    assert value["removed_method_paths"] == []


def test_catalog_owners_remain_real_application_files():
    value = catalog()
    for owner in value["owners"].values():
        assert owner["source_file"] in value["application_python_source_hashes"]
        assert isinstance(owner["source_line"], int) and owner["source_line"] > 0
        assert owner["endpoint"].startswith("app.")
