from datetime import datetime, timedelta
import logging
import time
import redis
from redis.commands.search.field import VectorField, TextField, NumericField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from server import settings


class RedisStore:

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

    SECTION_SCHEMA = [
        TextField("header"),
        TextField("body"),
        TextField("num_of_tokens"),
        VectorField("embedding", "HNSW", {"TYPE": "FLOAT32", "DIM": 1536, "DISTANCE_METRIC": "COSINE"}),
    ]
    SECTION_BLUE = "section_blue"
    SECTION_GREEN = "section_green"

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

    def _ensure_section_index(self, section_idx, conn: redis.Redis):
        prefix = f"{section_idx}:"
        try:
            conn.ft(section_idx).create_index(fields=self.SECTION_SCHEMA, definition=IndexDefinition(prefix=[prefix], index_type=IndexType.HASH))
            logging.info(f"Created section index {section_idx} with prefix {prefix}")
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
                    self._ensure_section_index(self.SECTION_BLUE, conn)
                    self._ensure_section_index(self.SECTION_GREEN, conn)
                    # ensure the active section index is set
                    active_section_index = conn.get('active_section_index')
                    if active_section_index is None or active_section_index == "":
                        logging.info(f"active_section_index not set, setting to {self.SECTION_BLUE}")
                        active_section_index = self.SECTION_BLUE
                        conn.set('active_section_index', active_section_index)
                    return conn
            except redis.ConnectionError as e:
                if i < retries - 1:
                    logging.error(e)
                    logging.info(
                        f'Retry {i + 1}/{retries} failed, retrying in {delay} seconds')
                    time.sleep(delay)
                    continue
                else:
                    raise

    def set_embeddings_version(self, date_and_time: datetime):
        dt = date_and_time.strftime("%Y-%m-%d")
        logging.info(f'setting embeddings_version to {dt}')
        try:
            self.conn.set('embeddings_version', dt)
        except Exception as e:
            logging.error("Error setting embeddings version in Redis: ", e)
            raise

    def get_embeddings_version(self) -> datetime:
        try:
            version = self.conn.get('embeddings_version')
            return version
        except Exception as e:
            logging.error("Error getting embeddings version from Redis: ", e)
            return None

    def get_active_section_index(self) -> str:
        active_section_index = self.conn.get('active_section_index')
        return active_section_index

    def get_passive_section_index(self):
        active_section_index = self.get_active_section_index()
        if active_section_index == self.SECTION_BLUE:
            return self.SECTION_GREEN
        else:
            return self.SECTION_BLUE

    def set_active_section_index(self, section_idx: str):
        try:
            logging.info(f'setting active_section_index to {section_idx}')
            self.conn.set('active_section_index', section_idx)
        except Exception as e:
            logging.error("Error setting active_section_index in Redis: ", e)
            raise

    def delete_all_sections(self, section_idx):
        prefix = f"{section_idx}:*"
        try:
            logging.info(f'deleting all sections in index {section_idx}')
            keys = self.conn.keys(prefix)
            logging.info(f'deleting {len(keys)}')
            if keys is not None and len(keys) != 0:
                self.conn.delete(*keys)
        except Exception as e:
            logging.error("Error deleting all sections from Redis: ", e)
            raise

    def set_interaction(self, interaction_id: any, start_time: float, query: str, reply: str, cache_reply: dict, chat_completions_req_duration: float,
                        feedback: str = "not given", expiration=timedelta(days=4)):

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
            # save for (default=4) days (nightly datapump-cron-job gets 4 chances to copy to statsdb)
            # while still keeping the in-memory redis small
            self.conn.expire(key, expiration)
        except Exception as e:
            logging.error("Error saving interaction to Redis: ", e)
            return None

    def update_interaction(self, interaction: any, interaction_id: str):
        key = f'{self.INTERACTION_PREFIX}{interaction_id}'
        try:
            logging.info(
                f'Updating interaction in Redis with id {interaction_id}')
            self.conn.hset(name=key, mapping=interaction)
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

    def get_all_interactions_with_keys(self) -> dict:
        try:
            keys = self.conn.keys(f"{self.INTERACTION_PREFIX}*")
            key_interacton_dict = {}
            for key in keys:
                interaction = self.conn.hgetall(key)
                key_interacton_dict[key] = interaction
            return key_interacton_dict

        except Exception as e:
            logging.error("Error getting all interactions from Redis: ", e)
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

    def delete_all_semantic_cache_entries(self):
        try:
            keys = self.conn.keys(f"{self.SEMANTIC_CACHE_PREFIX}*")
            if keys is not None and len(keys) != 0:
                self.conn.delete(*keys)
        except Exception as e:
            logging.error("Error deleting semantic cache entries from Redis: ", e)
            return None

    def search_sections(self, query_vector, top_k=5, use_passive_index=False):
        section_index = self.get_active_section_index()
        if use_passive_index:
            logging.info("using passive index!")
            section_index = self.get_passive_section_index()

        logging.info(f"searching in active_section_index {section_index}")
        base_query = f"*=>[KNN {top_k} @embedding $vector AS vector_score]"
        query = Query(base_query).return_fields("header", "body", "anchor_url",
                                                "num_of_tokens", "vector_score").sort_by("vector_score").dialect(2)
        try:
            results = self.conn.ft(section_index).search(
                query, query_params={"vector": query_vector})
        except Exception as e:
            logging.info("Error calling Redis search: ", e)
            return None

        return results
