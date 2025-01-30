import tiktoken
from openai import OpenAI
import numpy as np
from numpy.linalg import norm
from dotenv import load_dotenv
load_dotenv()
from server import settings

client = OpenAI(
    api_key=settings.openai_api_key
)

def truncate_text(text: str, max_tokens: int) -> str:
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    truncated_text = encoding.decode(tokens[:max_tokens])
    return truncated_text


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def get_embedding(text, model="text-embedding-ada-002"):  # max tokens 8191
    resp = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return resp.data[0].embedding

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (norm(vec1) * norm(vec2))
