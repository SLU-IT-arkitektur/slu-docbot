from section_creators import docx_parser
from embeddings_stores import redis_store


def run():
    print('''
    This script parses a word document and creates embeddings for each section.
    A section is a header and a text (can be multiple paragraphs) and an anchor_url (if available).
    It pipes the section_creator docx_parser to the embeddings_store redis_store.
    ''')

    section_generator = docx_parser.parse_docx('data/cleaned-v1-Utbildningshandboken.docx')
    redis_store.create_embeddings(section_generator)
    print('done')


if __name__ == '__main__':
    run()
