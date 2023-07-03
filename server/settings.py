import logging
import os

logging.basicConfig(level=logging.INFO)
prompt_instructions = os.getenv('PROMPT_INST')
redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')
correct_username = os.getenv('USERNAME')
correct_password = os.getenv('PASSWORD')

semantic_cache_enabled_default_value = True;
semantic_cache_enabled = os.getenv('SEMANTIC_CACHE_ENABLED')
semantic_cache_enabled = semantic_cache_enabled_default_value if semantic_cache_enabled is None else semantic_cache_enabled.lower() == 'true'

semantic_cache_min_similarity_score_default_value = 0.97
semantic_cache_min_similarity_score = os.getenv('SEMANTIC_CACHE_MIN_SIMILARITY_SCORE')
semantic_cache_min_similarity_score = semantic_cache_min_similarity_score_default_value if semantic_cache_min_similarity_score is None else float(semantic_cache_min_similarity_score)

sections_min_similarity_score_default_value = 0.8
sections_min_similarity_score = os.getenv('SECTIONS_MIN_SIMILARITY_SCORE')
sections_min_similarity_score = sections_min_similarity_score_default_value if sections_min_similarity_score is None else float(sections_min_similarity_score)

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
    
def print_settings_with_defaults():
    logging.info(f'semantic_cache_enabled is set to {semantic_cache_enabled} (default: {semantic_cache_enabled_default_value})')
    logging.info(f'semantic_cache_min_similarity_score is set to {semantic_cache_min_similarity_score} (default: {semantic_cache_min_similarity_score_default_value})')
    logging.info(f'sections_min_similarity_score is set to {sections_min_similarity_score} (default: {sections_min_similarity_score_default_value})')