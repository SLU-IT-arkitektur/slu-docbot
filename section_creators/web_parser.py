import requests
from bs4 import BeautifulSoup
from typing import Tuple, Iterator
import re
from util import num_tokens_from_string, truncate_text
'''
This module scrapes https://internt.slu.se/stod-service/utbildning/grund--och-avancerad-utbildning/utbildningens-ramar/utbildningshandboken/ and extracts (headers, text, anchor_url) sections and yields one tuple at a time through a generator function.
'''


def extract_content(url: str) -> Iterator[Tuple[str, str]]:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    for script in soup(['script', 'style']):
        script.decompose()

    all_h2_tags = soup.find_all('h2')

    # filter on h2 tags that start with a number(1-2 digits) followed by a dot and a space
    all_special_h2 = [tag for tag in all_h2_tags if re.match(r'^\d{1,2}\.\s', tag.get_text())]
    # strip out h2 tags that does not contain an anchor link
    # ie ... skip the index in the beginning of the page)
    all_special_h2 = [h2 for h2 in all_special_h2 if not h2.find('a', href=True)]
    print(f'Number of h2 tags of interest: {len(all_special_h2)}')
    for h2_tag in all_special_h2:
        header = h2_tag.text
        anchor = h2_tag.find('a')
        anchor_url = ""
        if anchor:
            anchor_url = f"{url}#{anchor['id']}"
            print(f'Found anchor link: {anchor_url}')

        text = ''
        for sibling in h2_tag.next_siblings:
            # if sibling in all_special_h2
            if sibling in all_special_h2:
                print(f'found next h2 tag: {sibling.text} breaking section {header} here...')
                break
            text += sibling.get_text()
            num_tokens = num_tokens_from_string(text, "cl100k_base")
            if num_tokens > 8192:
                print(f'Breaking section {header} here... due to token limit')
                text = truncate_text(text, 8000)
                break
        yield header, text, anchor_url
