from ..repositories.interfaces import GenerationRepositoryProtocol
class GenerationService:
    def __init__(self,repository:GenerationRepositoryProtocol):self.repository=repository
    def save(self,item):return self.repository.save(item)
    def get(self,jid):return self.repository.get(jid)
    def load_all(self):return self.repository.load_all()
