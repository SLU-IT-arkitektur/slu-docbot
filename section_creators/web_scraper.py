'''
This module scrapes the target url (Utbildningshandboken sv or en version) and extracts (headers, text, anchor_url) sections and yields one tuple at a time through a generator function.
'''

import requests
from bs4 import BeautifulSoup
from typing import Tuple, Iterator
from util import num_tokens_from_string, truncate_text
import fitz  # imports the pymupdf library
import tempfile
from server import settings


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

    print('yielding header, text and pdfurl from all pdf attachments')
    annex_generator = subscribe_annex_generator(all_h2_tags)
    for header, text, pdfurl in annex_generator:
        yield header, text, pdfurl

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


def subscribe_annex_generator(all_h2_tags):
    page_label = 'sida'
    target_header = "Bilageförteckning"
    if settings.lang == "en":
        target_header = "Annexes"
        page_label = 'page'

    print(f'running with language {settings.lang} therefore looking for target_header {target_header}')
    # Bilagor (appendices)
    last_appendices_header = [h2 for h2 in all_h2_tags if h2.text == target_header][1]  # there are two of these headers, the second one is the one we want. it has the links
    if last_appendices_header is not None:
        print("found the appendices in the web document")
        if settings.lang == "sv":
            print("sv version has all pdf appendix links in one p tag seperated by br tags")
            closest_p = last_appendices_header.find_next('p')
            print(closest_p)
            pdf_section_gen = subscribe_pdf_attachments_generator(closest_p, page_label)
            for header, text, pdfurl in pdf_section_gen:
                yield header, text, pdfurl
        elif settings.lang == "en":
            print("en version has each pdf appendix in its own p tag")
            all_following_p = last_appendices_header.find_all_next('p')
            for p in all_following_p:
                print(p)
                pdf_section_gen = subscribe_pdf_attachments_generator(p, page_label)
                for header, text, pdfurl in pdf_section_gen:
                    yield header, text, pdfurl
        else:
            print("language not supported")
            return


def subscribe_pdf_attachments_generator(target_p, page_label):
    all_a_tags = target_p.find_all('a', href=True)
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
                yield f"{a_tag_text[:70]}... {page_label} {page_number}", text, pdf_url

            print(f"total tokens for pdf {total_tokens}")
            print("number of pages", len(pdf))
            print("moving on to web sections")
