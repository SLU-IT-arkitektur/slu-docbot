from section_creators import web_parser
from time import sleep
from embeddings_stores import redis_store

def run():
    print('''
    This script parses https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/ and creates embeddings for each section.
    A section is a header and a text (can be multiple paragraphs).
    It pipes the section_creator web_parser to the embeddings_store redis_store.
    ''')

    sections_generator = web_parser.extract_content('https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/')
    redis_store.create_embeddings(sections_generator)

    # for header, text in sections_generator:
    #     sleep(1)
    #     print(header)
    #     print(text)
    #
    # print('done')
    #


if __name__ == '__main__':
    run()
