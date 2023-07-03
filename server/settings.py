import logging
import os

logging.basicConfig(level=logging.INFO)
prompt_instructions = os.getenv('PROMPT_INST')
redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')
correct_username = os.getenv('USERNAME')
correct_password = os.getenv('PASSWORD')
semantic_cache_enabled = os.getenv('SEMANTIC_CACHE_ENABLED')
if semantic_cache_enabled is None:
    semantic_cache_enabled = True; # defaults to true
    logging.warn(f"SEMANTIC_CACHE_ENABLED is not set, defaulting to {semantic_cache_enabled}")
else:
    semantic_cache_enabled = semantic_cache_enabled.lower() == 'true'
    logging.info(f"SEMANTIC_CACHE_ENABLED is set to {semantic_cache_enabled}")

semantic_cache_min_similarity_score = os.getenv('SEMANTIC_CACHE_MIN_SIMILARITY_SCORE')
if semantic_cache_min_similarity_score is None:
    semantic_cache_min_similarity_score = 0.97 # defaults to 0.97
    logging.warn(f"SEMANTIC_CACHE_MIN_SIMILARITY_SCORE is not set, defaulting to {semantic_cache_min_similarity_score}")
else:
    semantic_cache_min_similarity_score = float(semantic_cache_min_similarity_score)
    logging.info(f"SEMANTIC_CACHE_MIN_SIMILARITY_SCORE is set to {semantic_cache_min_similarity_score}")

sections_min_similarity_score = os.getenv('SECTIONS_MIN_SIMILARITY_SCORE')
if sections_min_similarity_score is None:
    sections_min_similarity_score = 0.8 # defaults to 0.8
    logging.warn(f"SECTIONS_MIN_SIMILARITY_SCORE is not set, defaulting to {sections_min_similarity_score}")

def check_required():
    if prompt_instructions is None:
        logging.error("PROMPT_INST is not set")
        exit(1)
    if redis_host is None:
        logging.error("Error: REDIS_HOST is not set")
        exit(1)
    if redis_port is None:
        logging.error("Error: REDIS_PORT is not set")
        exit(1)
    if redis_password is None:
        logging.error("Error: REDIS_PASSWORD is not set")
        exit(1)
    if correct_username is None:
        logging.error("Error: USERNAME is not set")
        exit(1)
    if correct_password is None:
        logging.error("Error: PASSWORD is not set")
        exit(1)
   
    logging.info('Settings initialized successfully')
    
