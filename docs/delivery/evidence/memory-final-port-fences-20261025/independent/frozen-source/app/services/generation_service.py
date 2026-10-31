from ..repositories.interfaces import GenerationRepositoryProtocol
class GenerationService:
    def __init__(self,repository:GenerationRepositoryProtocol):self.repository=repository
    def save(self,item,*,_file_memory=None):
        if _file_memory is None:return self.repository.save(item)
        from ..lore.file_memory_ports import require_memory_ports
        expected=require_memory_ports(_file_memory,self)
        return self.repository.save(item,_file_memory=expected,_expected_root=expected.root/'runtime/jobs')
    def get(self,jid,*,_file_memory=None):
        if _file_memory is None:return self.repository.get(jid)
        from ..lore.file_memory_ports import require_memory_ports
        expected=require_memory_ports(_file_memory,self)
        return self.repository.get(jid,_file_memory=expected)
    def load_all(self):return self.repository.load_all()
