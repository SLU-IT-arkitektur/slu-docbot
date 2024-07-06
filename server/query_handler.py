import json
import time
import logging
from typing import Tuple
import uuid
from fastapi.responses import JSONResponse
import numpy as np
import openai
from server import settings
from .semantic_cache import try_get_reply_from_cache, add_to_cache
from .open_ai_client import call_chat_completions
from .redis_store import RedisStore
from util import get_embedding, num_tokens_from_string, truncate_text


def handle_query(query: str, redis_store: RedisStore, use_passive_index=False):
    interaction_id = uuid.uuid4()
    start_time = time.time()
    is_valid, validation_message = validate(query)
    if not is_valid:
        return JSONResponse(content={"message": validation_message}, status_code=400)

    cache_reply = try_semantic_cache(query, redis_store, interaction_id, start_time)
    if cache_reply is not None:
        return cache_reply

    total_tokens_allowed_for_request = total_tokens_allowed_for_req(query)

    query_embedding = get_embedding(query)
    query_vector = np.array(query_embedding).astype(np.float32).tobytes()

    logging.info("Searching for similar sections...")
    similar_sections = redis_store.search_sections(query_vector, 3, use_passive_index)
    context, tokens_in_context = create_context(
        similar_sections, total_tokens_allowed_for_request)

    # prompt injection mitigation technique: not sending the query if it is not similar enough to the context
    # if less than 100 tokens in the context it's probably not enough to give a good answer
    if context is None or len(context) == 0 or tokens_in_context < 100:
        redis_store.set_interaction(
            interaction_id, start_time, query, '', cache_reply=None, chat_completions_req_duration=0)
        logging.info('query is not similar enough to the context')
        return {"interaction_id": str(interaction_id), "message": settings.get_locale()["server_texts"]["not_similar_enough_to_context"]}

    # prompt injection mitigation technique: having the last word..
    prompt = f'''context: """{context}""" question: """{query}"""
    prompt: """{settings.prompt_instructions}"""
    answer: '''

    logging.info("sending a total of " + str(num_tokens_from_string(prompt,
                                                                    "cl100k_base")) + " tokens to the API")

    chat_completions_req_start = time.time()
    catch_all_error_msg = settings.get_locale()["server_texts"]["errors"]["something_went_wrong"]
    try:
        response = call_chat_completions(prompt)
    except openai.error.APIError as e:
        logging.error(f"OpenAI API returned an API Error: {e}")
        return {"message": catch_all_error_msg}
    except openai.error.APIConnectionError as e:
        logging.error(f"Failed to connect to OpenAI API: {e}")
        return {"message": catch_all_error_msg}
    except openai.error.RateLimitError as e:
        logging.error(f"OpenAI API request exceeded rate limit: {e}")
        return {"message": catch_all_error_msg}
    except TimeoutError as e:
        logging.error(f"OpenAI API request timed out: {e}")
        return JSONResponse(content={"message": settings.get_locale()["server_texts"]["errors"]["openai_timeout"]}, status_code=200)
    except Exception as e:
        logging.error("unknown error", e)
        return {"message": catch_all_error_msg}

    chat_completions_req_stop = time.time()
    chat_completions_req_duration = round(
        chat_completions_req_stop - chat_completions_req_start, 0)

    logging.info(
        f'chat_completions_req_duration: {chat_completions_req_duration} seconds')

    read_more_headers = create_read_more_content(similar_sections)
    message = response["choices"][0]["message"]["content"]
    # if message wrapped in """ remove the """ wrapping
    if message.startswith('"""') and message.endswith('"""'):
        message = message[3:-3]

    embeddings_version = redis_store.get_embeddings_version()
    reply = {
        "message": message,
        "interaction_id": str(interaction_id),
        "sectionHeaders": read_more_headers,
        "embeddings_version": embeddings_version
    }

    redis_store.set_interaction(interaction_id, start_time, query,
                                str(reply["message"]), None, chat_completions_req_duration)

    try_add_to_semantic_cache(query, redis_store, reply)

    return reply


def get_num_tokens_for_req(numb_tokens_in_prompt_instructions: int, numb_tokens_in_query: int) -> int:
    max_tokens_for_gpt_model = 16000
    tokens_margin_for_prompt = 100
    tokens_saved_for_response = 1000
    total_tokens_allowed_for_request = (
        max_tokens_for_gpt_model
        - tokens_saved_for_response
        - numb_tokens_in_prompt_instructions
        - numb_tokens_in_query
        - tokens_margin_for_prompt
    )
    return total_tokens_allowed_for_request


def create_context(similar_sections, total_tokens_allowed_for_request) -> Tuple[str, int]:
    context = ''
    tokens_in_context = 0
    if similar_sections:
        logging.info(f"Found {similar_sections.total} similar sections:")
        for i, section in enumerate(similar_sections.docs):
            score = 1 - float(section.vector_score)
            min_score = settings.sections_min_similarity_score
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


def create_read_more_content(similar_sections) -> str:
    read_more_headers = []
    if similar_sections:
        for section in similar_sections.docs:
            if section.anchor_url and section.anchor_url != "":
                read_more_headers.append(f'<a target="_blank" href="{section.anchor_url}">{section.header}</a>')
            else:
                read_more_headers.append(section.header)
    return read_more_headers


def validate(query: str) -> Tuple[bool, str]:
    if len(query) < 1:
        return False, settings.get_locale()["server_texts"]["validation"]["min_length"]

    if len(query) > 80:
        logging.info(f'query is too long (max 80 characters): {len(query)}')
        logging.info(query)
        return False, settings.get_locale()["server_texts"]["validation"]["max_length"]

    return True, ""


def try_semantic_cache(query: str, redis_store: RedisStore, interaction_id, start_time):
    if settings.semantic_cache_enabled:
        logging.info("semantic cache enabled, checking cache...")
        hit = try_get_reply_from_cache(query, redis_store)
        if hit is not None:
            logging.info(f"Found reply in cache for query {query}")
            cache_reply = {
                "message": hit["reply"],
                "interaction_id": str(interaction_id),
                "from_cache": "true",
                "sectionHeaders": json.loads(hit["section_headers_as_json"]),
                "original_query": hit["original_query"],
            }
            redis_store.set_interaction(interaction_id, start_time, query, '', {"cached_reply": hit["reply"], "original_query": hit["original_query"]}, 0)
            return cache_reply
    else:
        logging.info("semantic cache disabled, continuing..")
        return None


def total_tokens_allowed_for_req(query: str) -> int:
    numb_tokens_in_prompt_instructions = num_tokens_from_string(settings.prompt_instructions, "cl100k_base")
    numb_tokens_in_query = num_tokens_from_string(query, "cl100k_base")
    total_tokens_allowed_for_request = get_num_tokens_for_req(
        numb_tokens_in_prompt_instructions, numb_tokens_in_query)
    return total_tokens_allowed_for_request


def try_add_to_semantic_cache(query: str, redis_store: RedisStore, reply):
    if settings.semantic_cache_enabled:
        section_headers_as_json = json.dumps(reply["sectionHeaders"])
        logging.info("semantic cache enabled, adding reply to cache...")
        add_to_cache(query, str(reply["message"]),
                     section_headers_as_json, redis_store)
