from data_retrievers import parse_docx
from embeddings_creators import to_redis

def run():
    print('''
    This script parses a word document and creates embeddings for each section.
    A section is a header and a text (can be multiple paragraphs).
    It pipes the data_retriever parse_docx to the embeddings_creator to_redis.
    ''')

    section_generator = parse_docx.parse_docx('data/cleaned-v1-Utbildningshandboken.docx')
    to_redis.create_embeddings(section_generator)
    print('done')

if __name__ == '__main__':
    run()