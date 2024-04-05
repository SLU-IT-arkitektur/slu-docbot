'''
This module exposes a create_embeddings function that takes an index_prefix and a sections generator and creates embeddings for each section and stores them in redis
'''

import os
import redis
from redis.commands.search.field import VectorField, TextField
import numpy as np
from util import get_embedding, num_tokens_from_string
from dotenv import load_dotenv
load_dotenv()

redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')
conn = redis.Redis(host=redis_host, port=redis_port, password=redis_password, encoding='utf-8', decode_responses=True)
if conn.ping():
    print("Connected to Redis")

SCHEMA = [
    TextField("header"),
    TextField("body"),
    TextField("num_of_tokens"),
    VectorField("embedding", "HNSW", {"TYPE": "FLOAT32", "DIM": 1536, "DISTANCE_METRIC": "COSINE"}),
]


p = conn.pipeline(transaction=False)


def create_embeddings(index_prefix: str, sections_generator):
    total_number_of_tokens = 0
    print('subscribing to sections_generator function and creating embeddings one (header, text, anchor_url) tuple at a time and saving them in redis')
    for header, text, anchor_url in sections_generator:
        num_of_tokens_in_section = num_tokens_from_string(text, "cl100k_base")
        total_number_of_tokens += num_of_tokens_in_section
        # TODO handle case where num_of_tokens_in_section > allowed 8191...
        # not an issue for Utbildningshandboken, but might be for other datasets

        print(f'creating embeddings for section {header} with {num_of_tokens_in_section} tokens')
        print(f'total number of tokens so far: {total_number_of_tokens}')
        embedding = get_embedding(text)  # max tokens 8191!
        # convert to numpy array
        vector = np.array(embedding).astype(np.float32).tobytes()
        section_hash = {
            "header": header,
            "body": text,
            "anchor_url": anchor_url,
            "num_of_tokens": num_of_tokens_in_section,
            "embedding": vector
        }
        conn.hset(name=f"{index_prefix}{header}", mapping=section_hash)

    p.execute()
    print(f"Total number of tokens for this embeddings run: {total_number_of_tokens}")
