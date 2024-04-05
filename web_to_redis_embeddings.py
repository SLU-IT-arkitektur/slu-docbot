from section_creators import web_scraper
from embeddings_stores import redis_store


def run():
    print('''
    This script parses https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/ and creates embeddings for each section.
    A section is a header and a text (can be multiple paragraphs) and an anchor_url (if available).
    It pipes the section_creator web_parser to the embeddings_store redis_store.
    ''')

    sections_generator = web_scraper.extract_content('https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/')
    redis_store.create_embeddings(sections_generator)


if __name__ == '__main__':
    run()
