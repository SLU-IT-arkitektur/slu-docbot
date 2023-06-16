from datetime import timedelta, datetime
import time
from typing import Tuple
import uuid
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import openai
import numpy as np
import openai
import threading
import os
from util import get_embedding, truncate_text, num_tokens_from_string
from pydantic import BaseModel
import redis
import logging
from redis.commands.json.path import Path as JSONPath
from redis.commands.search.query import Query
from redis.commands.search.field import TextField, NumericField, TagField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv

load_dotenv()

# setup basic http auth
security = HTTPBasic()
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv('USERNAME')
    correct_password = os.getenv('PASSWORD')
    if (correct_username is None) or (correct_password is None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Environment variables for authentication are not set",
        )
    if not (credentials.username == correct_username and credentials.password == correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# Set up logging
logging.basicConfig(level=logging.INFO)

INTERACTION_PREFIX = "interaction:"
THUMBSUP = "thumbsup"
THUMBSDOWN = "thumbsdown"

INTERACTION_SCHEMA = [
    TextField("query"),
    TextField("reply"),
    NumericField("request_duration_in_seconds"),
    NumericField("chat_completions_req_duration_in_seconds"),
    TextField("feedback")
]

redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')

def connect_redis(retries=5, delay=5):
    for i in range(retries):
        try:
            conn = redis.Redis(host=redis_host, port=redis_port,
                            password=redis_password, encoding='utf-8', decode_responses=True)    
            if conn.ping():
                logging.info("Connected to Redis")
                return conn
        except redis.ConnectionError as e:
            if i < retries - 1: 
                logging.error(e)
                logging.info(f'Retry {i+1}/{retries} failed, retrying in {delay} seconds')
                time.sleep(delay)
                continue
            else:
                raise

conn = connect_redis()

def ensure_interaction_feedback_search_index():
    try:
        conn.ft("interaction").create_index(
            INTERACTION_SCHEMA, definition=IndexDefinition(prefix=[INTERACTION_PREFIX],
                                                           index_type=IndexType.HASH))
    except Exception as e:
        logging.info(e)
        pass  # assume the index already exists

if conn.ping():
    logging.info("Connected to Redis")
    ensure_interaction_feedback_search_index()


prompt_instructions = os.getenv('PROMPT_INST')
if prompt_instructions is None:
    logging.info("Error: PROMPT_INST is not set")
    exit(1)

app = FastAPI()

static_folder = Path(__file__).parent / "static"

app.add_middleware( 
    CORSMiddleware,
    allow_origins=["*"], # TODO add an ALLOWED_ORIGINS env variable 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root(credentials: HTTPBasicCredentials = Depends(authenticate)):
    return FileResponse(static_folder / "index.html")


@app.get("/static/{file_name}")
async def static(file_name: str, credentials: HTTPBasicCredentials = Depends(authenticate)):
    return FileResponse(static_folder / file_name)


def search_vectors(query_vector, client, top_k=5):
    base_query = f"*=>[KNN {top_k} @embedding $vector AS vector_score]"
    query = Query(base_query).return_fields("header", "body",
                                            "num_of_tokens", "vector_score").sort_by("vector_score").dialect(2)

    try:
        results = client.ft("section").search(
            query, query_params={"vector": query_vector})
    except Exception as e:
        logging.info("Error calling Redis search: ", e)
        return None

    return results


def create_context(similar_sections, total_tokens_allowed_for_request) -> Tuple[str, int]:
    context = ''
    tokens_in_context = 0
    if similar_sections:
        logging.info(f"Found {similar_sections.total} similar sections:")
        for i, section in enumerate(similar_sections.docs):
            score = 1 - float(section.vector_score)
            min_score = 0.8
            if score < min_score:
                logging.info(
                    f'ignoring section {section.header} with score {score} (lower than {min_score})')
                continue
            context += section.body  # add this section to the context
            tokens_in_context += float(section.num_of_tokens)
            logging.info(
                f'adding section {section.header} with score {score} (higher than {min_score})')
            if tokens_in_context > total_tokens_allowed_for_request:
                logging.info(
                    f'context is too long: {tokens_in_context} truncating to {total_tokens_allowed_for_request}')
                # truncate the context
                context = truncate_text(
                    context, total_tokens_allowed_for_request)
                tokens_in_context = total_tokens_allowed_for_request
                logging.info(f'context is now {tokens_in_context} tokens long')
                break

    return context, tokens_in_context


def get_num_tokens_for_req(numb_tokens_in_prompt_instructions: int, numb_tokens_in_query: int) -> int:
    max_tokens_for_gpt35_turbo = 4096
    tokens_margin_for_prompt = 100
    # "Note too that very long conversations are more likely
    # to receive incomplete replies. For example, a gpt-3.5-turbo conversation
    # that is 4090 tokens long will have its reply cut off after just 6 tokens."
    tokens_saved_for_response = 1000

    total_tokens_allowed_for_request = (
        max_tokens_for_gpt35_turbo
        - tokens_saved_for_response
        - numb_tokens_in_prompt_instructions
        - numb_tokens_in_query
        - tokens_margin_for_prompt
    )
    return total_tokens_allowed_for_request


def set_interaction(interaction_id: any, start_time: float, query: str, reply: str, chat_completions_req_duration: float,
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

    key = f'{INTERACTION_PREFIX}{interaction_id}'
    try:
        logging.info(f'Saving interaction to Redis with id {interaction_id}')
        conn.hset(name=key, mapping=interaction)
        conn.expire(key, expiration)
    except Exception as e:
        logging.error("Error saving interaction to Redis: ", e)
        return None

def update_interaction(interaction: any, interaction_id: str, expiration=timedelta(days=90)):
    key = f'{INTERACTION_PREFIX}{interaction_id}'
    try:
        logging.info(f'Updating interaction in Redis with id {interaction_id}')
        conn.hset(name=key, mapping=interaction)
        conn.expire(key, expiration)
    except Exception as e:
        logging.error("Error updating interaction in Redis: ", e)
        return None

def get_interaction(interaction_id: str):
    try:
        logging.info('searching for ' +
                     f'{INTERACTION_PREFIX}{interaction_id}')
        interaction = conn.hgetall(f'{INTERACTION_PREFIX}{interaction_id}')
        return interaction
    except Exception as e:
        logging.error("Error getting interaction from Redis: ", e)
        return None

class QAPayload(BaseModel):
    query: str


@app.post("/qa", status_code=200)
async def qa(payload: QAPayload, credentials: HTTPBasicCredentials = Depends(authenticate)):
    interaction_id = uuid.uuid4()
    start_time = time.time()
    query = payload.query
    if len(query) < 1:
        return JSONResponse(content={"message": "Please enter a query"}, status_code=400)
    # prompt injection mitigation tecnique: not allowing too long queries
    if len(query) > 80:
        logging.info(f'query is too long (max 80 characters): {len(query)}')
        logging.info(query)
        return JSONResponse(content={"message": "Max 80 tecken"}, status_code=400)

    numb_tokens_in_prompt_instructions = num_tokens_from_string(
        prompt_instructions, "cl100k_base")
    numb_tokens_in_query = num_tokens_from_string(query, "cl100k_base")
    total_tokens_allowed_for_request = get_num_tokens_for_req(
        numb_tokens_in_prompt_instructions, numb_tokens_in_query)

    query_embedding = get_embedding(query)
    query_vector = np.array(query_embedding).astype(np.float32).tobytes()

    logging.info("Searching for similar sections...")
    similar_sections = search_vectors(query_vector, conn, 3)
    context, tokens_in_context = create_context(
        similar_sections, total_tokens_allowed_for_request)

    # prompt injection mitigation tecnique: not sending the query if it is not similar enough (min_score above) to the context
    # if less than 1000 tokens in the context it's probably not enough to give a good answer
    if context is None or len(context) == 0 or tokens_in_context < 1000:
        set_interaction(interaction_id, start_time, query, '', 0)
        logging.info('query is not similar enough to the context')
        return {"interaction_id": str(interaction_id), "message": "Jag hittar inget svar på din fråga i Utbildningshandboken"}

    # prompt injection mitigation tecnique: having the last word..
    prompt = f'''context: """{context}""" question: """{query}"""
    prompt: """{prompt_instructions}""" 
    answer: '''

    logging.info("sending a total of " + str(num_tokens_from_string(prompt,
                                                                    "cl100k_base")) + " tokens to the API")

    chat_completions_req_start = time.time()
    try:
        response = call_open_ai_chat_completions(prompt)
    except openai.error.APIError as e:
        # Handle API error here, e.g. retry or log
        logging.error("APIError")
        logging.error(f"OpenAI API returned an API Error: {e}")
        return {"message": "Något gick fel :("}
    except openai.error.APIConnectionError as e:
        # Handle connection error here
        logging.error("APIConnectionError")
        logging.error(f"Failed to connect to OpenAI API: {e}")
        return {"message": "Något gick fel :("}
    except openai.error.RateLimitError as e:
        # Handle rate limit error (we recommend using exponential backoff)
        logging.error("RateLimitError")
        logging.error(f"OpenAI API request exceeded rate limit: {e}")
        return {"message": "Något gick fel :("}
    except TimeoutError as e:
        logging.error("TimeoutError")
        logging.error(f"OpenAI API request timed out: {e}")
        return JSONResponse(content={"message": "OpenAI har väldigt långa svarstider just nu, var god försök igen senare."}, status_code=200) # because cloud flare handles 504 differently and serves a html page instead?
    except Exception as e:
        logging.error("Unknown error:")
        logging.error(e)
        return {"message": "Något gick fel :("}

    chat_completions_req_stop = time.time()
    chat_completions_req_duration = round(
        chat_completions_req_stop-chat_completions_req_start, 0)

    logging.info(f'chat_completions_req_duration: {chat_completions_req_duration} seconds')

    message = response["choices"][0]["message"]["content"]
    reply = {
        "message": message,
        "interaction_id": str(interaction_id),
        "sectionHeaders": [section.header for section in similar_sections.docs],
    }

    set_interaction(interaction_id, start_time, query,
                    str(reply["message"]), chat_completions_req_duration)
    return reply


class FeedbackPayload(BaseModel):
    feedback: str
    interaction_id: str


@app.post("/feedback", status_code=200)
async def qa(payload: FeedbackPayload, credentials: HTTPBasicCredentials = Depends(authenticate)):
    feedback = payload.feedback
    interaction_id = payload.interaction_id
    if feedback != THUMBSUP and feedback != THUMBSDOWN:
        return JSONResponse(content={"message": f'Please enter {THUMBSUP} or {THUMBSDOWN}'}, status_code=400)

    interaction = get_interaction(interaction_id)
    if interaction is None:
        return JSONResponse(content={"message": "Interaction not found"}, status_code=404)

    # update interaction with feedback and new expiration of 90 days
    interaction["feedback"] = feedback
    update_interaction(interaction, interaction_id, timedelta(days=90))

    return {"message": "Tack för din feedback!"}


def call_open_ai_chat_completions(prompt: str):
    response = None
    def worker():
        nonlocal response
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            temperature=0.0,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=25) # give open ai 25 seconds to respond

    if thread.is_alive():
        raise TimeoutError("OpenAI API call took to long")
    else:
        return response
