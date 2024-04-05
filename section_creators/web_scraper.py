'''
This module scrapes https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/ and extracts (headers, text, anchor_url) sections and yields one tuple at a time through a generator function.
'''

import requests
from bs4 import BeautifulSoup
from typing import Tuple, Iterator
from util import num_tokens_from_string, truncate_text
import fitz  # imports the pymupdf library
import tempfile

def extract_content(url: str) -> Iterator[Tuple[str, str]]:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    for script in soup(['script', 'style']):
        script.decompose()

    all_h2_tags = soup.find_all('h2')

    print('all special h2')
    for x in all_h2_tags:
        print(x)
    # strip out h2 tags that does not contain an anchor link
    all_special_h2 = [h2 for h2 in all_h2_tags if not h2.find('a', href=True)]

    # Bilagor (appendices)
    last_appendices_header = [h2 for h2 in all_h2_tags if h2.text == "Bilageförteckning"][1]  # there are two of these headers, the second one is the one we want. it has the links
    if last_appendices_header is not None:
        print("found the appendices in the web document")
        # foreach a href in the paragraph directly below the Bilageföreckning header (all in one p right now..)
        closest_p = last_appendices_header.find_next('p')
        print(closest_p)
        all_a_tags = closest_p.find_all('a', href=True)
        for a_tag in all_a_tags:
            print(a_tag)
            pdf_url = f"https://internt.slu.se{a_tag['href']}"
            print("pdf_url", pdf_url)
            if not pdf_url.endswith(".pdf"):
                print("not a pdf, skipping")
                continue
            pdf_resp = requests.get(pdf_url)
            print("pdf_resp", pdf_resp)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_resp.content)  # write to the temporary file
                pdf = fitz.open(tmp_file.name)  # open a document
                total_tokens = 0
                page_number = 0
                for page in pdf:
                    page_number += 1
                    text = page.get_text().replace('\n', ' ')  # get plain text encoded as UTF-8 (and replace newlines with empty space
                    print(text)
                    tokens_for_page = num_tokens_from_string(text, "cl100k_base")
                    print(f"number of tokens for page {tokens_for_page}")
                    total_tokens += tokens_for_page
                    a_tag_text = a_tag.get_text()
                    yield f"{a_tag_text[:70]}... sida {page_number}", text, pdf_url

                print(f"total tokens for pdf {total_tokens}")
                print("number of pages", len(pdf))
                print("moving on to web sections")

    print('all special h2 after filter out missing anchor link')
    for x in all_special_h2:
        print(x)
    print(f'Number of h2 tags of interest: {len(all_special_h2)}')

    # all normal web sections..
    for h2_tag in all_special_h2:
        header = h2_tag.text
        anchor = h2_tag.find('a')
        anchor_url = ""
        if anchor:
            anchor_url = f"{url}#{anchor['id']}"
            print(f'Found anchor link: {anchor_url}')

        text = ''
        for sibling in h2_tag.next_siblings:
            if sibling in all_special_h2:
                print(f'found next h2 tag: {sibling.text} breaking section {header} here...')
                break
            text += sibling.get_text().replace('\n', ' ')
            num_tokens = num_tokens_from_string(text, "cl100k_base")
            if num_tokens > 8192:
                print(f'Breaking section {header} here... due to token limit')
                text = truncate_text(text, 8192)
                break
        yield header, text, anchor_url
