from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.packaging.versioning import load_release_version, validate_repository_versions


def main() -> int:
    release = load_release_version()
    consumers = validate_repository_versions()
    print(json.dumps({"release": release.__dict__, "consumers": consumers}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
