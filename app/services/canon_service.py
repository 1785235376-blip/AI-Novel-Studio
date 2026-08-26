from ..repositories.interfaces import CanonRepositoryProtocol
class CanonService:
    def __init__(self,repository:CanonRepositoryProtocol):self.repository=repository
    def list(self,nid):return self.repository.list(nid)
    def list_pending(self,nid):return self.repository.list_pending(nid)
    def save_pending(self,item):return self.repository.save_pending(item)
    def approve(self,pid,proposals=None):return self.repository.approve(pid,proposals)
    def reject(self,pid):return self.repository.reject(pid)
