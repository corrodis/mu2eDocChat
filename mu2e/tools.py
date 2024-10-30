import json
import os

def load(docid, base_path="data/docs/"):
    """
    Loads a document from the local storage/cache.

    Args:
        docid(str): unique docid, this is the name of the folder
        base_path(str, optional): base path of the documents. Defaults to data/docs/.

    Returns:
        dic: doc meta data and list with files
    """
    # load a document from store
    dir_path = base_path+docid
    # check if the document already exists, if not, lets try to get it
    if not os.path.exists(dir_path):
        if docid.startswith("mu2e-docdb"):
            import mu2e
            from mu2e import docdb
            id_ = int(docid.split("-")[-1])
            try:
                db = docdb(mu2e.docdb_cookie)
            except:
                print("docdb connection failed")
                return {'id':id_, 'revised_content':'n/a', 'title':'Document retrival failed', 'files':[]}
            try:
                doc = db.get(id_)
                doc = db.parse_pdf_slides(doc, False)
                db.save(doc, base_path)
            except:
                print("Something went wrong in the document retrival")
                return {'id':id_, 'revised_content':'n/a', 'title':'Document not found', 'files':[]}
    with open(dir_path+"/meta.json", 'r') as file:
        doc = json.load(file)
    return doc

def get_summary(doc, method="claude-sonnet"):
    """
    Generate a summary for each file on a document. The summaries are added to the copy of doc which is returned.

    Args:
        doc(dict): doc object loaded with load. Cotnaining a key files with a list of documents. The text of each document is used to generate the summaries.
        method(str, optional): method/module used to generate the summaries. One of claude-haiku, claude-sonnet, openAi-4oMini. Defaults to claude-sonnet.

    Returns:
        doc(dict): modified doc including the summaries. 
    """
    method_ = method.split("-")[0]
    model_  = method.split("-")[1]

    if method_ == "claude":
        return _get_summary_claude(doc, model=model_)
    #elif implement more
    else:
        raise NameError("The method '{method}' is not implemented. Needs to be one of claude-haiku, claude-sonnet, openAi-4oMini.")

def _get_summary_claude(doc, model):
    import mu2e # for the api key
    import requests
    
    models = {"haiku":"claude-3-haiku-20240307",
              "sonnet":"claude-3-5-sonnet-20240620"}
    if model not in models:
        raise NameError(f"Model '{model}' is not implemented. Model needs to be one of {models.keys()}")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": mu2e.api_keys['antropic'],
        "anthropic-version": "2023-06-01"
    }
    for i, file in enumerate(doc['files']):
        prompt = "Please summarize the attached document."
        prompt += f"<document>{file['text']}</document>"
        print(prompt)
    
        payload = {
            "model": models[model],
            "messages": [{"role": "user",
                        "content": [{"type": "text", "text": prompt}]
                        }],
            "max_tokens": 400
        }
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Somethign went wrong with the request to anthropic: {response.json}")
        answer = response.json()
        print(answer)
        doc['files'][i]['summary'] = answer['content'][0]['text']
    return doc