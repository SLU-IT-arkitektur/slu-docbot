from docx import Document
from typing import Tuple, Iterator


'''
This module parses a word document and extracts (headers, text, anchor_url) sections and yields one tuple at a time through a generator function.
'''


def parse_docx(path_to_doc) -> Iterator[Tuple[str, str]]:
    doc = Document(path_to_doc)
    current_header = None
    sections = dict()

    anchor_url = ""  # no anchor url's for docx files
    for paragraph in doc.paragraphs:
        if paragraph.style.name.startswith('Heading'):
            if current_header is not None:
                yield current_header, sections[current_header], anchor_url

            text = paragraph.text.replace('\n', ' ')
            current_header = text
            sections[current_header] = ''

        if paragraph.style.name == 'Normal' and current_header is not None:
            sections[current_header] += paragraph.text.replace('\n', ' ')

    # make sure to fire off the last section
    if current_header is not None:
        yield current_header, sections[current_header], anchor_url
