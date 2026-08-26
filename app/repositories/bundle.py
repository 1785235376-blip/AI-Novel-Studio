from dataclasses import dataclass
from typing import Any
from .interfaces import NovelRepositoryProtocol,ChapterRepositoryProtocol,CanonRepositoryProtocol,GenerationRepositoryProtocol
from .lore_interfaces import LoreRepositoryProtocol
from .authorization_interfaces import AuthorizationRepositoryProtocol
from .identity_interfaces import IdentityRepositoryProtocol

@dataclass(frozen=True)
class RepositoryBundle:
    novels:NovelRepositoryProtocol
    chapters:ChapterRepositoryProtocol
    canon:CanonRepositoryProtocol
    generations:GenerationRepositoryProtocol
    lore:LoreRepositoryProtocol|None=None
    continuity:Any|None=None
    narrative:Any|None=None
    scope:Any|None=None
    authorization:AuthorizationRepositoryProtocol|None=None
    identity:IdentityRepositoryProtocol|None=None
