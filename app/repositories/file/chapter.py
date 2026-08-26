import json
from ...repository import FileRepository,read_json
from ...storage import atomic_write
from ..chapter_repository import ChapterRepository, VersionConflict

class FileChapterRepository(ChapterRepository):
    def __init__(self,backend:FileRepository):super().__init__(backend)
    def list(self,novel_id):return [{**c,"version":self.get(c["id"])["version"]} for c in self.backend.list_chapters(novel_id) if not c.get("is_archived",False)]
    def list_archived(self,novel_id):return [{**c,"version":self.get(c["id"])["version"]} for c in self.backend.list_archived_chapters(novel_id)]
    def archive(self,chapter_id,expected_version=None):
        try:return self.backend.set_chapter_archived(chapter_id,True,expected_version)
        except ValueError:
            raise VersionConflict(self.get(chapter_id),resource_id=chapter_id,expected_version=expected_version)
    def restore_archive(self,chapter_id,expected_version=None):
        try:return self.backend.set_chapter_archived(chapter_id,False,expected_version)
        except ValueError:
            raise VersionConflict(self.get(chapter_id),resource_id=chapter_id,expected_version=expected_version)
    def create(self,novel_id,payload):return self.backend.create_chapter(novel_id,payload)
    def save_summary(self,novel_id,chapter_number,summary):
        path=self.backend.novels/novel_id/"summaries/index.json";items=read_json(path,[]);item={"chapter":chapter_number,"summary":summary};items=[x for x in items if x.get("chapter")!=chapter_number]+[item];atomic_write(path,json.dumps(items,ensure_ascii=False,indent=2));return item
