"""Exact bounded vector index adapter over the embedding owner's durable records.

Cosine math is real; a provider labelled MOCK_ONLY remains synthetic. This
adapter does not manufacture vectors, persist a second cache, or rename lexical
matches as semantic matches.
"""
from __future__ import annotations

import math
from typing import Protocol


class VectorIndex(Protocol):
    def search(self, query: list[float], records: list[dict], limit: int) -> list[dict]: ...


class ExactCosineVectorIndex:
    def search(self, query, records, limit):
        norm = math.sqrt(sum(value * value for value in query))
        if not norm: raise ValueError('EMBEDDING_ZERO_VECTOR')
        result = []
        for row in records:
            vector = row['vector']
            if len(vector) != len(query): raise ValueError('EMBEDDING_DIMENSION_MISMATCH')
            denominator = norm * math.sqrt(sum(value * value for value in vector))
            if not denominator: raise ValueError('EMBEDDING_ZERO_VECTOR')
            score = sum(a * b for a, b in zip(query, vector)) / denominator
            result.append({'record_id': row['id'], 'entity': row['entity'], 'score': max(-1.0, min(1.0, score)),
                           'source_digest': row['source_digest'], 'source_version': row['source_version'],
                           'verification': row['verification']})
        return sorted(result, key=lambda item: (-item['score'], item['record_id']))[:limit]


def hybrid_rank(semantic, lexical, weight):
    """Weighted reciprocal-rank fusion; both component ranks are inspectable."""
    semantic_ranks = {item['record_id']: rank for rank, item in enumerate(semantic, 1)}
    lexical_ranks = {rid: rank for rank, (rid, _) in enumerate(sorted(lexical.items(), key=lambda item: (-item[1], item[0])), 1)}
    output = []
    for item in semantic:
        rid = item['record_id']; lr = lexical_ranks.get(rid)
        score = (1 - weight) / (60 + semantic_ranks[rid]) + (weight / (60 + lr) if lr else 0)
        output.append({**item, 'semantic_score': item['score'], 'lexical_score': lexical.get(rid, 0),
                       'semantic_rank': semantic_ranks[rid], 'lexical_rank': lr, 'score': score})
    return sorted(output, key=lambda item: (-item['score'], item['record_id']))
