"""Prepare the pinned official OFL font for an isolated build or acceptance run.

No system fonts are copied. Downloads and existing files are verified before
use; the font stays unmodified and the complete OFL accompanies it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import io
import os
from pathlib import Path
import struct
import tempfile
from urllib.request import urlopen

REVISION = "2894aab31764f10f29c421bdfd2340d3b382d384"
BASE = f"https://raw.githubusercontent.com/google/fonts/{REVISION}/ofl/notosanssc/"
FILES = {
    "NotoSansSC-Variable.ttf": (BASE + "NotoSansSC%5Bwght%5D.ttf", "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da"),
    "OFL.txt": (BASE + "OFL.txt", "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9"),
}
MAX_BYTES = 24 * 1024 * 1024


def verify_font(data: bytes):
    if data[:4] != b"\x00\x01\x00\x00" or len(data) < 12:
        raise ValueError("expected TrueType sfnt font")
    count = struct.unpack_from(">H", data, 4)[0]
    tags = set()
    for index in range(count):
        tag, _, offset, size = struct.unpack_from(">4sIII", data, 12 + index * 16)
        if offset + size > len(data):
            raise ValueError("font table outside file")
        tags.add(tag)
    if not {b"glyf", b"loca", b"cmap", b"head", b"name"} <= tags:
        raise ValueError("font lacks embeddable TrueType glyph/cmap tables")


def prepare(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"upstream_revision": REVISION, "license": "SIL OFL 1.1", "modified": True, "derivation": {"tool": "fonttools 4.59.1", "axes": {"wght": 400}, "subset": False}, "files": []}
    for name, (url, digest) in FILES.items():
        target = output / name
        if target.is_symlink():
            raise ValueError("font output must not be a symlink")
        if target.exists():
            data = target.read_bytes()
        else:
            with urlopen(url, timeout=90) as response:
                data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("pinned font/license integrity check failed")
        if name.endswith(".ttf"):
            verify_font(data)
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=output, delete=False) as f:
                temporary = Path(f.name)
                f.write(data)
            try:
                # Refuse to overwrite a file created after validation.
                with target.open("xb") as f:
                    f.write(temporary.read_bytes())
            finally:
                temporary.unlink(missing_ok=True)
        manifest["files"].append({"path": name, "source": url, "sha256": digest, "size": len(data)})
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    import fontTools
    if fontTools.__version__ != "4.59.1":
        raise ValueError("font derivation requires pinned fonttools 4.59.1")
    variable = TTFont(output / "NotoSansSC-Variable.ttf", recalcTimestamp=False)
    regular = instantiateVariableFont(variable, {"wght": 400}, inplace=False, updateFontNames=True)
    regular.recalcTimestamp = False
    stream = io.BytesIO()
    regular.save(stream)
    derived = stream.getvalue()
    verify_font(derived)
    target = output / "NotoSansSC-Regular.ttf"
    if target.exists():
        if target.is_symlink() or target.read_bytes() != derived:
            raise ValueError("existing derived font differs; use a fresh output directory")
    else:
        with target.open("xb") as f:
            f.write(derived)
    manifest["files"].append({"path": target.name, "sha256": hashlib.sha256(derived).hexdigest(), "size": len(derived), "derived_from": "NotoSansSC-Variable.ttf", "bundled": True})
    (output / "font-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))
