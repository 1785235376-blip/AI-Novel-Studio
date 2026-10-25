#!/usr/bin/env python3
# [HERMIA-FE-20261025 VERA-e471dc76 P2-1] Read-only AST scan of backend app/ for error code -> message provenance.
# Output JSON: {"literal": {CODE: [messages]}, "dynamic": {CODE: [file:line]}}.
# literal  = message is a compile-time string (Constant, f-string without fields, literal "+" literal).
# dynamic  = anything else (str(exc), variables, f"{x}", implicit "x" f"{exc}", .format, %, calls, repr, ...).
# Covered constructs: {"code": C, "message"/"detail": M} dicts (any key order, multi-line), dict(code=C, message=M),
# any call with keyword code=C + message=/detail=, and custom exception/helper calls Foo(..., "C", M, ...)
# (positional code-like literal followed by the message argument, e.g. AudiobookError("X", text, 502), _error(403, "X", str(exc))).
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
def code_of(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) and CODE.match(n.value) else None
def main(app):
    literal, dynamic = {}, {}
    def rec(code, msg, where):
        if msg is None: return
        if lit(msg): literal.setdefault(code, []).append(litval(msg))
        else: dynamic.setdefault(code, []).append(where)
    for root, dirs, files in os.walk(app):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"): continue
            p = os.path.join(root, f)
            try: tree = ast.parse(open(p, encoding="utf8").read(), p)
            except SyntaxError as e: print(json.dumps({"error": f"{p}: {e}"})); sys.exit(2)
            rel = os.path.relpath(p, app)
            for n in ast.walk(tree):
                where = f"{rel}:{getattr(n, 'lineno', 0)}"
                if isinstance(n, ast.Dict):
                    kv = {k.value: v for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                    c = code_of(kv.get("code")) if "code" in kv else None
                    if c:
                        for mk in MSG_KEYS: rec(c, kv.get(mk), where)
                elif isinstance(n, ast.Call):
                    kw = {k.arg: k.value for k in n.keywords if k.arg}
                    c = code_of(kw.get("code")) if "code" in kw else None
                    if c:
                        for mk in MSG_KEYS: rec(c, kw.get(mk), where)
                    for i, a in enumerate(n.args):
                        c = code_of(a)
                        if c and i + 1 < len(n.args): rec(c, n.args[i + 1], where)
                        elif c and not n.args[i + 1:]:
                            for mk in MSG_KEYS: rec(c, kw.get(mk), where)
    print(json.dumps({"literal": literal, "dynamic": dynamic}, ensure_ascii=False))
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "../../app"))
