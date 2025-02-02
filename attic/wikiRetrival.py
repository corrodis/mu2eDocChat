import numpy as np
import os
from scipy import spatial
from angle_emb import AnglE, Prompts
import mu2e

angle = AnglE.from_pretrained('WhereIsAI/UAE-Large-V1', pooling_strategy='cls').cuda()

import json
with open(mu2e.MU2E+'data/mu2e_wiki.json', 'r') as file:
    data = json.load(file)
emb = np.array([d['embedding'] for d in data])


def find(q):
    qv = angle.encode(Prompts.C.format(text=q))[0]
    dot_product = np.dot(emb/np.linalg.norm(emb, axis=1, keepdims=True), qv/np.linalg.norm(qv))
    distance = 1-dot_product
    sort = np.argsort(distance)
    return sort, distance

def getParagraph(idx, upper=False):
    url     = "https://mu2ewiki.fnal.gov"+data[idx]["url"]+"#"+data[idx]['title'][3:]
    heading = data[idx]['page'] + " - " + data[idx]['title'][3:]
    text = ""
    for idx_ in range(idx-data[idx]['split'], idx):
        text += data[idx_]['text']
    if upper:
        text += (data[idx]['text']).upper()
    else:
        text += "<b>"+(data[idx]['text'])+"</b>"
    idx_ = idx + 1
    while (idx_ in data) and (data[idx]['title'] == data[idx_]['title']):
       text  += data[idx_]['text']
       idx_  += 1

    return {"url":url, "heading":heading, "text":text}

def findAndGet(q, number=None, maxdist=None):
    if number is None:
        number=20
    if maxdist is None:
        maxdist=0.5
    sort, dist = find(q)
    pars = []
    pars_headings = []

    for s in sort:
        if (dist[s] < maxdist) and\
           (len(pars) <= number):
            par = getParagraph(s)
            if par['heading'] not in pars_headings:
               pars.append(par)
               pars_headings.append(par['heading']) # cache 
        else:
            return pars
        
