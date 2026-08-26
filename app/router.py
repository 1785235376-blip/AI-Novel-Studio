from __future__ import annotations
from dataclasses import dataclass
from .providers import LLMProvider, Generation, ProviderError

@dataclass
class Route:
    provider: str
    model: str

class ModelRouter:
    def __init__(self, providers:dict[str,LLMProvider], routes:dict[str,list[Route]]): self.providers=providers; self.routes=routes
    def generate(self, role:str, prompt:str)->Generation:
        errors=[]
        for route in self.routes.get(role,[]):
            provider=self.providers.get(route.provider)
            if not provider: continue
            try: return provider.generate(prompt,route.model)
            except ProviderError as exc: errors.append(str(exc))
        raise ProviderError(f"No route succeeded for {role}: {'; '.join(errors) or 'not configured'}")

