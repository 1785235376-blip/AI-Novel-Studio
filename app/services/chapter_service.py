from ..document import markdown_to_document
from ..repositories.interfaces import ChapterRepositoryProtocol
class ChapterService:
    def __init__(self,repository:ChapterRepositoryProtocol):self.repository=repository
    def list(self,nid):return self.repository.list(nid)
    def list_archived(self,nid):return self.repository.list_archived(nid)
    def archive(self,cid,expected_version=None):return self.repository.archive(cid,expected_version)
    def restore_archive(self,cid,expected_version=None):return self.repository.restore_archive(cid,expected_version)
    def create(self,nid,payload):return self.repository.create(nid,payload)
    def get(self,cid):return self.repository.get(cid)
    def save(self,cid,payload):
        current=self.get(cid);document=payload.get("document") or markdown_to_document(payload.get("content",current["content"]));return self.repository.save(cid,document,payload.get("version",current["version"]),payload.get("source","USER"))
    def delete(self,cid):return self.repository.delete(cid)
    def duplicate(self,cid):return self.repository.duplicate(cid)
    def rename(self,cid,title,version):return self.repository.rename(cid,title,version)
    def move(self,cid,direction):return self.repository.move(cid,direction)
    def history(self,cid):return self.repository.history(cid)
    def restore(self,cid,version,expected):return self.repository.restore(cid,version,expected)
    def save_summary(self,nid,number,summary):return self.repository.save_summary(nid,number,summary)
