"""Legacy functional fixtures read the visible version before editorial writes.

These tests exercise existing content/state behavior. Dedicated CAS tests use
the ordinary TestClient to assert missing-precondition and stale-write errors.
No failure, conflict, or existing assertion is bypassed here.
"""
import re
from urllib.parse import urlsplit
from fastapi.testclient import TestClient


class VersionedScreenplayClient(TestClient):
    def request(self,method,url,*args,**kwargs):
        path=urlsplit(str(url)).path
        match=re.fullmatch(r"(/api/novels/[^/]+/screenplays)/([^/]+)/(.*)",path)
        if match:
            collection,screenplay_id,suffix=match.groups()
            editorial=(method.upper()=="PUT" and re.fullmatch(r"(?:scenes|shots|storyboard|transitions|assets)/[^/]+",suffix)) or (method.upper()=="POST" and suffix in {"approve","revise","shots/approve","storyboard/approve","transitions/approve","assets/approve"})
            body=kwargs.get("json")
            if editorial and (body is None or isinstance(body,dict) and "expected_version" not in body):
                visible=self.get(collection,headers=kwargs.get("headers"))
                if visible.status_code==200:
                    current=next((row for row in visible.json() if row["id"]==screenplay_id),None)
                    if current is not None:
                        kwargs["json"]={**(body or {}),"expected_version":current.get("edit_version",0)}
        return super().request(method,url,*args,**kwargs)
