from docx import Document
from typing import Tuple, Iterator


'''
This module parses a word document and extracts (headers, text) sections and yields one pair at a time through a generator function.
'''

def parse_docx(path_to_doc) -> Iterator[Tuple[str, str]]:
    doc = Document(path_to_doc)
    print(f'parsing word document...')
    current_header = None
    sections = dict()
    
    for paragraph in doc.paragraphs:
        if paragraph.style.name.startswith('Heading'):
            if current_header is not None:
                yield current_header, sections[current_header]

            text = paragraph.text.replace('\n', ' ')
            current_header = text
            sections[current_header] = ''

        if paragraph.style.name == 'Normal' and current_header is not None:
            sections[current_header] += paragraph.text.replace('\n', ' ')

    # make sure to fire off the last section
    if current_header is not None:
        yield current_header, sections[current_header]
            
