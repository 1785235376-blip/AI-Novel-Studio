from app import storage


def test_atomic_write_retries_transient_permission_error(tmp_path,monkeypatch):
    real=storage.os.replace; calls=[]
    def replace(source,target):
        calls.append((source,target))
        if len(calls)<3: raise PermissionError("transient")
        return real(source,target)
    monkeypatch.setattr(storage.os,"replace",replace)
    target=tmp_path/"result.txt"; storage.atomic_write(target,"complete")
    assert target.read_text(encoding="utf-8")=="complete"
    assert len(calls)==3


def test_atomic_write_raises_after_retry_exhaustion(tmp_path,monkeypatch):
    monkeypatch.setattr(storage.os,"replace",lambda *_: (_ for _ in ()).throw(PermissionError("locked")))
    try: storage.atomic_write(tmp_path/"result.txt","content")
    except PermissionError: pass
    else: raise AssertionError("PermissionError must not be swallowed")
    assert not list(tmp_path.glob("*.tmp"))
