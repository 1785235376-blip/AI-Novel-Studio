from ..repository import FileRepository
class NovelRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    def list(self):return self.backend.list_novels()
    def get(self,nid):return self.backend.get_novel(nid)
    def create(self,payload):return self.backend.create_novel(payload)
    def update(self,nid,payload):return self.backend.update_novel(nid,payload)
    def delete(self,nid):return self.backend.delete_novel(nid)
