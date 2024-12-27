from dotenv import load_dotenv
load_dotenv()
from server import redis_store
from section_creators import web_scraper
from embeddings_stores import redis_store as redis_embedding_store
from datetime import date
from server import settings
from server import query_handler
from util import get_embedding
from util import cosine_similarity
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
settings.check_required()   # .. or fail early!
settings.print_settings_with_defaults()

print("\ndeleting passive sections so that they can be recreated with new embeddings...\n")
redis = redis_store.RedisStore()
target_section_index = redis.get_passive_section_index()

try:
    redis.delete_all_sections(target_section_index)
    print("All sections deleted")
except Exception as e:
    print("Error deleting all sections: ", e)
    exit(1)

index_prefix = f"{target_section_index}:"
print("\nextracting sections from web page and creating embeddings...\n")
target_url = "https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/"
if settings.lang == "en":
    target_url = "https://internt.slu.se/en/support-services/education/education-at-bachelors-and-masters-level/local-statutes-and-organization/education-planning-and-administration-handbook/"
print(f'running with language {settings.lang} therefore setting target_url to {target_url}')

sections_generator = web_scraper.extract_content(target_url)
redis_embedding_store.create_embeddings(index_prefix, sections_generator)

print("\nrunning Quality Assurance tests...\n")
target_file = "./data/qa_qa.json"
if settings.lang == "en":
    target_file = "./data/qa_qa_en.json"
print(f'running with language {settings.lang} therefore setting target_file to {target_file}')

file_path = os.path.join(os.path.dirname(__file__), target_file)
quality_qas = json.load(open(file_path))
# disable semantic_cache when testing new embeddings
settings.semantic_cache_enabled = False
for qa in quality_qas:
    print(f"\n\nchecking question {qa['question']}")
    use_passive_index = True
    reply = query_handler.handle_query(qa['question'], redis, use_passive_index)
    answer = reply['message']
    answer_emb = get_embedding(answer)
    qa_answer_emb = get_embedding(qa['answer'])
    print("comparing qa answer with newly created embeddings answer")
    similarity = cosine_similarity(answer_emb, qa_answer_emb)
    print("Cosine similarity:", similarity)
    if similarity <= 0.90:
        print(f"Error: Cosine similarity too low for question {qa['question']} and answer:\n\n '{qa['answer']}' \n\nand answer from newly created embeddings:\n\n '{answer}'")
        exit(1)

print(f"\nall qa tests passed, setting active section index to {target_section_index}\n")

redis.set_active_section_index(target_section_index)

print('\ndeleting semantic cache since we now have new fresh embeddings...\n')
redis.delete_all_semantic_cache_entries()


try:
    print("\nsetting embeddings version to todays date\n")
    redis.set_embeddings_version(date.today())
except Exception as e:
    print("Error setting embeddings version to todays date", e)
    exit(1)
