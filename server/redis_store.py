from datetime import datetime, timedelta
import logging
import time
import redis
from redis.commands.search.field import VectorField, TextField, NumericField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from server import settings

class RedisStore:
    SECTION_INDEX = "section"

    INTERACTION_INDEX = "interaction"
    INTERACTION_PREFIX = "interaction:"
    INTERACTION_SCHEMA = [
        TextField("query"),
        TextField("reply"),
        NumericField("request_duration_in_seconds"),
        NumericField("chat_completions_req_duration_in_seconds"),
        TextField("feedback")
    ]

    SEMANTIC_CACHE_INDEX = "semantic_cache"
    SEMANTIC_CACHE_PREFIX = "semantic_cache:"
    SEMANTIC_CACHE_SCHEMA = [
        TextField("query"),
        TextField("reply"),
        TextField("section_headers_as_json"),
        VectorField("embedding", "HNSW", {"TYPE": "FLOAT32", "DIM": 1536, "DISTANCE_METRIC": "COSINE"}),
    ]

    redis_host = settings.redis_host
    redis_port = settings.redis_port
    redis_password = settings.redis_password

    def __init__(self):
        self.conn = self._connect_redis()

    def _ensure_semantic_cache_search_index(self, conn: redis.Redis):
        try:
            conn.ft(self.SEMANTIC_CACHE_INDEX).create_index(fields=self.SEMANTIC_CACHE_SCHEMA, definition=IndexDefinition(
                prefix=[self.SEMANTIC_CACHE_PREFIX], index_type=IndexType.HASH))
            logging.info("Created semantic_cache index")
        except Exception as e:
            logging.info(e)
            pass

    def _ensure_interaction_feedback_search_index(self, conn: redis.Redis):
        try:
            conn.ft(self.INTERACTION_INDEX).create_index(
                self.INTERACTION_SCHEMA, definition=IndexDefinition(prefix=[self.INTERACTION_PREFIX],
                                                                    index_type=IndexType.HASH))
            logging.info("Created interaction index")
        except Exception as e:
            logging.info(e)
            pass  # assume the index already exists

    def _connect_redis(self, retries=5, delay=5):
        for i in range(retries):
            try:
                conn = redis.Redis(host=self.redis_host, port=self.redis_port,
                                   password=self.redis_password, encoding='utf-8', decode_responses=True)
                if conn.ping():
                    logging.info("Connected to Redis")
                    self._ensure_interaction_feedback_search_index(conn)
                    self._ensure_semantic_cache_search_index(conn)
                    return conn
            except redis.ConnectionError as e:
                if i < retries - 1:
                    logging.error(e)
                    logging.info(
                        f'Retry {i+1}/{retries} failed, retrying in {delay} seconds')
                    time.sleep(delay)
                    continue
                else:
                    raise

    def set_interaction(self, interaction_id: any, start_time: float, query: str, reply: str, cache_reply: dict, chat_completions_req_duration: float,
                        feedback: str = "not given", expiration=timedelta(minutes=10)):

        stop_time = time.time()
        request_duration = round(stop_time - start_time, 0)
        now = datetime.now()
        formatted_now = now.strftime("%Y-%m-%d %H:%M:%S")

        interaction = {
            "query": query,
            "reply": reply,  # contains section headers so we can infer the context
            "request_duration_in_seconds": float(request_duration),
            "chat_completions_req_duration_in_seconds": float(chat_completions_req_duration),
            "feedback": feedback,  # can be 'not given', 'thumbsUp' or 'thumbsDown',
            "timestamp": formatted_now
        }
        if cache_reply:
            interaction["from_cache"] = 'true'
            for key, value in cache_reply.items():
                interaction[key] = value

        key = f'{self.INTERACTION_PREFIX}{interaction_id}'
        try:
            logging.info(
                f'Saving interaction to Redis with id {interaction_id}')
            self.conn.hset(name=key, mapping=interaction)
            self.conn.expire(key, expiration)
        except Exception as e:
            logging.error("Error saving interaction to Redis: ", e)
            return None

    def update_interaction(self, interaction: any, interaction_id: str, expiration=timedelta(days=90)):
        key = f'{self.INTERACTION_PREFIX}{interaction_id}'
        try:
            logging.info(
                f'Updating interaction in Redis with id {interaction_id}')
            self.conn.hset(name=key, mapping=interaction)
            self.conn.expire(key, expiration)
        except Exception as e:
            logging.error("Error updating interaction in Redis: ", e)
            return None

    def get_interaction(self, interaction_id: str):
        try:
            logging.info('searching for ' + f'{self.INTERACTION_PREFIX}{interaction_id}')
            interaction = self.conn.hgetall(
                f'{self.INTERACTION_PREFIX}{interaction_id}')
            return interaction
        except Exception as e:
            logging.error("Error getting interaction from Redis: ", e)
            return None

    def search_semantic_cache(self, query_vector, top_k=1):
        base_query = f"*=>[KNN {top_k} @embedding $vector AS vector_score]"
        query = Query(base_query).return_fields("query", "reply", "section_headers_as_json", "vector_score").sort_by("vector_score").dialect(2)
        try:
            results = self.conn.ft(self.SEMANTIC_CACHE_INDEX).search(query, query_params={"vector": query_vector})
            return results
        except Exception as e:
            logging.error("Error searching semantic cache in Redis: ", e)
            return None

    def add_to_semantic_cache(self, query: str, reply: str, section_headers_as_json: str, query_embedding: bytes, expiration=timedelta(minutes=90)):
        key = f"semantic_cache:{query}"
        try:
            logging.info(
                f'Saving key {key} to cache')

            cache_entry_hash = {
                "query": query,
                "reply": reply,
                "section_headers_as_json": section_headers_as_json,
                "embedding": query_embedding
            }
            self.conn.hset(name=key, mapping=cache_entry_hash)
            self.conn.expire(key, expiration)

        except Exception as e:
            logging.error("Error saving semantic cache entry to Redis: ", e)
            return None

    def search_sections(self, query_vector, top_k=5):
        base_query = f"*=>[KNN {top_k} @embedding $vector AS vector_score]"
        query = Query(base_query).return_fields("header", "body",
                                                "num_of_tokens", "vector_score").sort_by("vector_score").dialect(2)

        try:
            results = self.conn.ft(self.SECTION_INDEX).search(
                query, query_params={"vector": query_vector})
        except Exception as e:
            logging.info("Error calling Redis search: ", e)
            return None

        return results
