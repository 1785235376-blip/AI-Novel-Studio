#!/usr/bin/env python3
# [HERMIA-FE-20261025 VERA-e471dc76 P2-1 / VERA-fbe029c4 P2] Read-only AST scan of backend app/: error code -> message provenance.
# Principle: anything not *provably* a hand-written literal is NOT literal (dynamic, or "unknown" when the code itself is not provable).
# Output JSON: {"literal": {CODE: [msg]}, "dynamic": {CODE: [where]}, "unknown": [site], "enums": {Class: [CODE]}}
#   literal  : message is a compile-time string, at a code dict / dict(code=..) / exception-like constructor.
#   dynamic  : any non-literal message, any textish-dynamic sibling value (reason/error/... = str(exc), f"{x}"),
#              dicts opened to mutation (name[...] = , name.update(...), {**name}, f(**name)), dicts/calls with ** spread,
#              class-attribute codes (class X: code = "C") constructed with non-literal args.
#   unknown  : a "code" whose value is not provable (exc.code, f-string, unresolved name) paired with a non-literal message,
#              or a spread dict with a non-literal message and no visible code. Contract: must be a subset of an audited list.
# Codes are resolved through literal constants (C = "X"), Enum/class attributes (Codes.X / Codes.X.value).
# Usage: scan_error_codes.py APP_DIR            -> one scan
#        scan_error_codes.py APP_DIR --mutants M.json  (list of {name,file,from,to}) -> {name: scan | {"error": ...}}
import ast, json, os, re, sys
CODE = re.compile(r'^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$')
MSG_KEYS = ("message", "detail")
def lit(n):
    if isinstance(n, ast.Constant): return isinstance(n.value, str)
    if isinstance(n, ast.JoinedStr): return all(isinstance(v, ast.Constant) for v in n.values)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add): return lit(n.left) and lit(n.right)
    return False
def litval(n):
    if isinstance(n, ast.Constant): return n.value
    if isinstance(n, ast.JoinedStr): return "".join(v.value for v in n.values)
    return litval(n.left) + litval(n.right)
def textish_dynamic(n):
    """A value that renders text from runtime data (str(exc), f"{x}", "..." % x, .format, repr, join, + with str)."""
    if isinstance(n, ast.JoinedStr): return not lit(n)
    if isinstance(n, ast.Call):
        f = n.func
        if isinstance(f, ast.Name) and f.id in ("str", "repr", "format"): return True
        if isinstance(f, ast.Attribute) and f.attr in ("format", "join", "format_map"): return True
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Mod, ast.Add)):
        return not lit(n) and (textish_dynamic(n.left) or textish_dynamic(n.right) or isinstance(n.left, (ast.Constant, ast.JoinedStr)))
    if isinstance(n, ast.IfExp): return textish_dynamic(n.body) or textish_dynamic(n.orelse)
    return False
def callee(n):
    f = n.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
def parse_all(files):
    out = {}
    for rel, src in files.items():
        try: out[rel] = ast.parse(src, rel)
        except SyntaxError as e: raise SystemExit(json.dumps({"error": f"{rel}: {e}"}))
    return out
def scan(trees):
    consts, attrs, class_code, enums, exc_classes = {}, {}, {}, {}, set()
    for tree in trees.values():
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) and CODE.match(n.value.value):
                for t in n.targets:
                    if isinstance(t, ast.Name): consts.setdefault(t.id, set()).add(n.value.value)
            if isinstance(n, ast.ClassDef):
                bases = [b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else "" for b in n.bases]
                if any(re.search(r"(Error|Exception)$", b) for b in bases) or re.search(r"(Error|Exception)$", n.name): exc_classes.add(n.name)
                for s in n.body:
                    if isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str) and CODE.match(s.value.value):
                        for t in s.targets:
                            if not isinstance(t, ast.Name): continue
                            attrs.setdefault(t.id, set()).add(s.value.value)
                            if t.id in ("code", "error_code"): class_code[n.name] = s.value.value
                            if any(b.endswith("Enum") for b in bases): enums.setdefault(n.name, []).append(s.value.value)
    def resolve(n):
        """Return (code|None, provable: bool)."""
        if n is None: return None, True
        if isinstance(n, ast.Constant): return (n.value, True) if isinstance(n.value, str) and CODE.match(n.value) else (None, True)
        if isinstance(n, ast.Name):
            v = consts.get(n.id); return (next(iter(v)), True) if v and len(v) == 1 else (None, False)
        if isinstance(n, ast.Attribute):
            if n.attr in ("value", "name"): return resolve(n.value)
            v = attrs.get(n.attr)
            if v and len(v) == 1 and not (isinstance(n.value, ast.Name) and n.value.id in ("exc", "e", "err", "error", "self")): return next(iter(v)), True
            return None, False
        return None, False
    literal, dynamic, unknown = {}, {}, set()
    def dyn(c, where): dynamic.setdefault(c, []).append(where)
    def rec(c, msg, where, literal_ok=True):
        if msg is None: return
        if lit(msg) and CODE.match(litval(msg)): dyn(c, where + " internal-token-message")  # e.g. "MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED": not author copy
        elif lit(msg):
            if literal_ok: literal.setdefault(c, []).append(litval(msg))
        else: dyn(c, where)
    for rel, tree in trees.items():
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))] + [tree]
        owner = {}
        for fn in funcs:
            for n in ast.walk(fn):
                owner.setdefault(id(n), fn)
        def fname(n):
            fn = owner.get(id(n)); return getattr(fn, "name", "<module>")
        # dict literals bound to names, and the mutations / spreads applied to those names
        bound = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
                kv = {k.value: v for k, v in zip(n.value.keys, n.value.values) if isinstance(k, ast.Constant)}
                c, _ = resolve(kv.get("code"))
                if c:
                    for t in n.targets:
                        if isinstance(t, ast.Name): bound.setdefault((id(owner.get(id(n))), t.id), set()).add(c)
        def bound_codes(n, name):
            return bound.get((id(owner.get(id(n))), name), set())
        for n in ast.walk(tree):
            where = f"{rel}:{getattr(n, 'lineno', 0)}"
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        for c in bound_codes(n, t.value.id): dyn(c, where + " subscript-assign")
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("update", "setdefault", "__setitem__") and isinstance(n.func.value, ast.Name):
                for c in bound_codes(n, n.func.value.id): dyn(c, where + " dict-mutation")
            if isinstance(n, ast.Dict):
                spreads = [v for k, v in zip(n.keys, n.values) if k is None]
                for s in spreads:
                    if isinstance(s, ast.Name):
                        for c in bound_codes(n, s.id): dyn(c, where + " spread-of-code-dict")
                kv = {k.value: v for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                if "code" in kv:
                    c, provable = resolve(kv["code"])
                    if c:
                        for mk in MSG_KEYS: rec(c, kv.get(mk), where)
                        for k, v in kv.items():
                            if k not in MSG_KEYS and k != "code" and textish_dynamic(v): dyn(c, f"{where} key={k}")
                        if spreads: dyn(c, where + " spread")
                    elif not provable and (any(mk in kv and not lit(kv[mk]) for mk in MSG_KEYS) or spreads):
                        unknown.add(f"{rel}::{fname(n)}::{ast.unparse(kv['code'])}")
                elif spreads and any(mk in kv and not lit(kv[mk]) for mk in MSG_KEYS):
                    unknown.add(f"{rel}::{fname(n)}::**" + ",".join(ast.unparse(s) for s in spreads))
            elif isinstance(n, ast.Call):
                name = callee(n)
                exc_like = name in exc_classes or bool(re.search(r"(Error|Exception)$|error", name, re.I)) or name == "__init__"
                kw = {k.arg: k.value for k in n.keywords if k.arg}
                star = [k.value for k in n.keywords if k.arg is None]
                for s in star:
                    if isinstance(s, ast.Name):
                        for c in bound_codes(n, s.id): dyn(c, where + " call-spread-of-code-dict")
                if "code" in kw:
                    c, provable = resolve(kw["code"])
                    if c:
                        for mk in MSG_KEYS: rec(c, kw.get(mk), where, exc_like or name == "dict")
                        if star: dyn(c, where + " call-spread")
                    elif not provable and any(mk in kw and not lit(kw[mk]) for mk in MSG_KEYS):
                        unknown.add(f"{rel}::{fname(n)}::{ast.unparse(kw['code'])}")
                if name in class_code and (any(not lit(a) for a in n.args) or any(not lit(v) for v in kw.values()) or star):
                    dyn(class_code[name], where + " class-attr-code")
                for i, a in enumerate(n.args):
                    c, _ = resolve(a)
                    if not c: continue
                    if i + 1 < len(n.args): rec(c, n.args[i + 1], where, exc_like)
                    elif not n.args[i + 1:]:
                        for mk in MSG_KEYS: rec(c, kw.get(mk), where, exc_like)
                        if star: dyn(c, where + " call-spread")
    return {"literal": literal, "dynamic": dynamic, "unknown": sorted(unknown), "enums": enums}
def read_app(app):
    files = {}
    for root, dirs, fs in os.walk(app):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in fs:
            if f.endswith(".py"):
                p = os.path.join(root, f); files[os.path.relpath(p, app)] = open(p, encoding="utf8").read()
    return files
def main(argv):
    app = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), "../../app")
    files = read_app(app)
    if len(argv) > 3 and argv[2] == "--mutants":
        trees = parse_all(files); out = {}
        for m in json.load(open(argv[3], encoding="utf8")):
            src = files.get(m["file"])
            if src is None or m["from"] not in src: out[m["name"]] = {"error": "PATTERN NOT FOUND"}; continue
            t2 = dict(trees)
            try: t2[m["file"]] = ast.parse(src.replace(m["from"], m["to"], 1), m["file"])
            except SyntaxError as e: out[m["name"]] = {"error": f"syntax: {e}"}; continue
            out[m["name"]] = scan(t2)
        print(json.dumps(out, ensure_ascii=False)); return
    print(json.dumps(scan(parse_all(files)), ensure_ascii=False))
if __name__ == "__main__": main(sys.argv)
