import logging
import json
import os

logging.basicConfig(level=logging.INFO)
redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')

semantic_cache_enabled_default_value = True
semantic_cache_enabled = os.getenv('SEMANTIC_CACHE_ENABLED')
semantic_cache_enabled = semantic_cache_enabled_default_value if semantic_cache_enabled is None else semantic_cache_enabled.lower() == 'true'

lang_default = "sv"
lang = os.getenv("CHATBOT_LANG")
lang = lang_default if lang is None else lang.lower()

if lang != "sv" and lang != "en":
    logging.error(f"Error: Invalid language {lang}")
    exit(1)

prompt_instructions = os.getenv('PROMPT_INST')
if lang == "en":
    print(f'running with lang {lang} so i will use prompt PROMPT_INST_EN')
    prompt_instructions = os.getenv('PROMPT_INST_EN')


def load_locales():
    logging.info("loading locales")
    locales = {}
    current_dir = os.path.dirname(__file__)
    locales_dir = os.path.join(current_dir, 'locales')
    for filename in os.listdir(locales_dir):
        if filename.endswith('.json'):
            language = filename.split('.')[0]
            with open(os.path.join(locales_dir, filename), 'r', encoding='utf-8') as f:
                locales[language] = json.load(f)
    return locales


locales = load_locales()


def get_locale():
    return locales[lang]


semantic_cache_min_similarity_score_default_value = 0.97
semantic_cache_min_similarity_score = os.getenv('SEMANTIC_CACHE_MIN_SIMILARITY_SCORE')
semantic_cache_min_similarity_score = semantic_cache_min_similarity_score_default_value if semantic_cache_min_similarity_score is None else float(semantic_cache_min_similarity_score)

sections_min_similarity_score_default_value = 0.8
sections_min_similarity_score = os.getenv('SECTIONS_MIN_SIMILARITY_SCORE')
sections_min_similarity_score = sections_min_similarity_score_default_value if sections_min_similarity_score is None else float(sections_min_similarity_score)

openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    print("Warning: OPENAI_API_KEY not set, using dummy value for tests")
    openai_api_key = "dummy"


def check_required():
    if redis_host is None:
        logging.error("Error: REDIS_HOST is not set")
        exit(1)
    if prompt_instructions is None:
        logging.error("PROMPT_INST is not set")
        exit(1)
    if redis_port is None:
        logging.error("Error: REDIS_PORT is not set")
        exit(1)
    if redis_password is None:
        logging.error("Error: REDIS_PASSWORD is not set")
        exit(1)

    logging.info('Settings initialized successfully')


def print_settings_with_defaults():
    logging.info(f'semantic_cache_enabled is set to {semantic_cache_enabled} (default: {semantic_cache_enabled_default_value})')
    logging.info(f'semantic_cache_min_similarity_score is set to {semantic_cache_min_similarity_score} (default: {semantic_cache_min_similarity_score_default_value})')
    logging.info(f'sections_min_similarity_score is set to {sections_min_similarity_score} (default: {sections_min_similarity_score_default_value})')
    logging.info(f'lang is set to {lang} (default: {lang_default})')
