import logging
import numpy as np
from server import settings
from util import get_embedding
from .redis_store import RedisStore


def try_get_reply_from_cache(query: str, redis_store: RedisStore):
    query_embedding = _get_embedding_for_query(query)
    result = redis_store.search_semantic_cache(query_embedding, 1)
    if result.total == 0:
        logging.info(f"No reply found in cache for query {query}")
        return None

    hit = result.docs[0]  # because we only ask for 1 result
    score = 1 - float(hit.vector_score)
    min_score = settings.semantic_cache_min_similarity_score
    if score >= min_score:
        logging.info(f"Found reply in cache for query {query} (query similarity score: {score}))")
        return {"reply": hit.reply, "section_headers_as_json": hit.section_headers_as_json, "original_query": hit.query}
    else:
        logging.info(f"Found reply in cache for query {query} (query similarity score: {score}), but score is too low (min score: {min_score})")
        return None


def add_to_cache(query: str, reply: str, section_headers_as_json: str, redis_store: RedisStore):
    query_embedding = _get_embedding_for_query(query)
    redis_store.add_to_semantic_cache(query, reply, section_headers_as_json, query_embedding)
    logging.info(f"Added query {query} to cache")


def _get_embedding_for_query(query: str) -> bytes:
    emb = get_embedding(query)  # max tokens 8191!
    # convert to numpy array
    query_embedding = np.array(emb).astype(np.float32).tobytes()
    return query_embedding
