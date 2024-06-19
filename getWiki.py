import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

from transformers import AutoTokenizer
from angle_emb import AnglE

tokenizer = AutoTokenizer.from_pretrained("WhereIsAI/UAE-Large-V1")

def page2chunks(url):
    chunks = []
    url_ = "https://mu2ewiki.fnal.gov/"+url
    page_txt = requests.get(url_).text
    soup = BeautifulSoup(page_txt, 'html.parser')
    content = soup.find(id='mw-content-text')

    def add(text):
        tokens_ = len(tokenizer.tokenize(text))
        if(chunks[-1]['tokens']+tokens_ >= 512):
            chunks.append({"id":chunks[-1]["id"],
                           "url": chunks[-1]["url"],
                           "page": chunks[-1]["page"],
                           "title":chunks[-1]["title"], 
                           "text":"", 
                           "tokens":0, 
                           "split":chunks[-1]['split']+1})
        chunks[-1]['text'] = chunks[-1]['text'] + text
        chunks[-1]['tokens'] = chunks[-1]['tokens'] + tokens_

    page_title = soup.find("h1").text.strip()

    for h2 in content.find_all("h2"):
        if h2.text == "Contents":
            continue
        chunks.append({"id": len(chunks),
                       "url": url,
                       "page": page_title,
                       "title":"## "+h2.text, 
                       "text":"", 
                       "tokens":0, 
                       "split":0})
        print(len(chunks), h2.text) 
        for sibling in h2.find_next_siblings():
            #print(sibling.name)
            if sibling.name == 'h2':
                 break
            elif sibling.name == 'p':
                 add(sibling.text.strip())
            elif (sibling.name == 'pre') or \
                 (sibling.name == 'table') or \
                 (sibling.name == 'ul') or \
                 (sibling.name == 'ol'): # keep the tags
                 add(str(sibling))
            elif sibling.name == 'h3':
                 add("### "+sibling.text.strip()+"\n")
            else:
                print(sibling.name, sibling)
                #chunks[-1] = chunks[-1] + sibling.text.strip()
    return chunks


def getWikiUrls():
    index_page = "https://mu2ewiki.fnal.gov/wiki/Category:Computing"
    sitemap_res = requests.get(index_page).text
    soup = BeautifulSoup(sitemap_res, 'lxml-xml')
    links = soup.find_all("a")
    wiki_urls = [link.get("href") for link in links if re.match(r'^/wiki/', link.get("href", ""))]
    wiki_urls = sorted(list(set(wiki_urls)))
    return wiki_urls




page_data = []
i = 0
for url in getWikiUrls():
    i = i + 1
    if i in []:
       break
    print("#####" + url + "#####")
    chunks = page2chunks(url)
    page_data.extend(chunks)

##### adding embeddings #####
print(" ")
print("Create embeddings")
angle = AnglE.from_pretrained('WhereIsAI/UAE-Large-V1', pooling_strategy='cls').cuda()
for chunk in page_data:
    print(chunk['page'] + " - "+chunk['title'], end="\r")
    text = "# "+chunk['page']+"\n"+\
                chunk['title']+"\n"+\
                chunk['text']
    chunk["embedding"] = angle.encode([text])[0].tolist()

    
with open('mu2e_wiki_v2.json', 'w') as file:
     json.dump(page_data, file, indent=4)
    
