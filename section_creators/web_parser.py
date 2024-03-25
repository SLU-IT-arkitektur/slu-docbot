import requests
from bs4 import BeautifulSoup
from typing import Tuple, Iterator
import re

'''
This module scrapes a website and extracts (headers, text) sections and yields one pair at a time through a generator function.
'''

def extract_content(url: str) -> Iterator[Tuple[str, str]]:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    for script in soup(['script', 'style']):
        script.decompose()

    all_h2_tags = soup.find_all('h2')

    # filter on h2 tags that start with a number(1-2 digits) followed by a dot and a space
    all_special_h2 = [tag for tag in all_h2_tags if re.match(r'^\d{1,2}\.\s', tag.get_text())]
    # strip put h2 tags that does not contain an anchor link
    # ie ... skip the index in the beggining of the page)
    all_special_h2 = [h2 for h2 in all_special_h2 if not h2.find('a', href=True)]
    print(f'Number of h2 tags: {len(all_special_h2)}')
    for h2_tag in all_special_h2:
        header = h2_tag.text
        text = ''
        for sibling in h2_tag.next_siblings:
            # if sibling in all_special_h2
            if sibling in all_special_h2:
                print(f'found next h2 tag: {sibling.text} breaking section {header} here...')
                break
            text += sibling.get_text()
        yield header, text
