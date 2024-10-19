import requests
from bs4 import BeautifulSoup
import re
import io
from urllib.parse import quote
import mu2e

class docdb:
    """
    Client to retrive documents from FNAL docdb.

    Attributes:
        base_url (str): The base URL of the docdb server.
        cookies (dict): the cookies needed for authentification
    """
    def __init__(self, cookie : str, base_url : str = None):
        """
        Args:
            cookie (str): The cookie value (of mellon-sso_mu2e-docdb.fnal.gov) needed for authentifiaction. Get it from login through the browser.
            base_url (str, optional): The base URL of the docdb server. Defaults to https://mu2e-docdb.fnal.gov/cgi-bin/sso/.
        """
        self.cookies = {"mellon-sso_mu2e-docdb.fnal.gov": cookie}
        self.base_url = base_url if base_url else "https://mu2e-docdb.fnal.gov/cgi-bin/sso/"

    def login(self):
        pass

    def _get_html(self, doc_id : int):
        """
        Gets the html page of a document. Used to then parse in get_meta.
        
        Args:
            doc_id: The docdb number.

        Returns:
            html (string): html of the docdb html page.

        Raises:
            RuntimeError: if no response, see _check_respose
        """
        url_ = f"{self.base_url}ShowDocument?docid={doc_id}"
        response = requests.get(url_, cookies=self.cookies)
        self._check_respose(response)
        return response.text
        
    
    def get_meta(self, doc_id : int):
        """
        Retrieve the meta data of document

        Args:
            doc_id: The docdb number.

        Returns:
            A dictionary containing the document's meta data. Containing docid_str, type, created, revised_content, revised_meta, title, abstract, files, topics, keyword, docid, version. Returns None if the document doesn't exist.

        Raises:
            RuntimeError: if no response, see _check_respose
        """
        html = self._get_html(doc_id)
        soup = BeautifulSoup(html, 'html.parser')
        page_title = soup.title.string if soup.title else None
        if (not page_title) or (page_title == f"Mu2e-doc-{doc_id}-v: Not authorized"):
            return None
        
        result = {}

        #left side statistics
        fields = {"docid_str":"Document #:",
                 "type":"Document type:",
                 "created":"Document Created:",
                 "revised_content":"Contents Revised:",
                 "revised_meta":"Metadata Revised:"}
        for field in fields:
            key = soup.find('dt', string=fields[field])
            if key:
                tag = key.find_next('dd')
                if tag:
                    result[field] = tag.text.strip()
        
        #body
        docTitle = soup.find('div', id='DocTitle')
        if docTitle:
            title = docTitle.find('h1')
            if title:
                result['title'] = title.text.strip()
        
        
        #InfoHeader
        fields = {"abstract":{"search":"Abstract:",          "list":False},
                  "files":   {"search":"Files in Document:", "list":True},
                  "topics":  {"search":"Topics:",            "list":True},
                  "keyword": {"search":"Keywords:",          "list":True}
                 }
        for field in fields:
            key = soup.find('dt', class_='InfoHeader', string=fields[field]["search"])
            if key:
                if field == "topics":
                    tag = key.find_next('ul')
                else:
                    tag = key.find_next('dd')
                if tag:
                    
                    if not fields[field]["list"]:
                        result[field] = tag.text
                    else: 
                        if field == "files":
                            result[field] = [{"link":item.find('a').get("href"), 
                                              "filename":item.find('a').get("title"),
                                              "text":re.sub(r'\s*\(.*\)\s*$', '', item.text)} for item in tag.find_all('li')]
                        else:
                            result[field] = [item.text for item in tag.find_all('a')]
        
        docid_str_split = result["docid_str"].split("-")
        result["docid"]  = int(docid_str_split[2])
        result["version"] = int(docid_str_split[3][1:])

        return result

    def _check_respose(self, response):
        """
        Checks the response from docdb, raises an exception if the response it not good.

        Args:
            response (requests.Response): response to be checked
        
        Raises:
            RuntimeError: if the server response it not valid
            RuntimeError: if login might be requeired
            
        """
        if(response.ok):
            soup = BeautifulSoup(response.text, 'html.parser')
            page_title = soup.title.string if soup.title else None
            if page_title:
                if page_title == "Select Authentication System":
                    raise RuntimeError(f"New login required. Log in to {self.base_url} in your browser, use the new cookie (mellon-sso_mu2e-docdb.fnal.gov) in the docdb constructor.")
        else:
            raise RuntimeError(f"The connection to {response.url} failed with status {response.status_code}:"+response.json())
    
    def get_document_url(self, docurl : str):
        """
        Get document from a docdb link.

        Args:
            docurl (str): url to the document, this is the same that is also used in the browser.

        Returns:
            dict: with {type, document (io.BytesI)} of the retrived document 

        Raises:
            RuntimeError in case of connection issues.
        """
        response = requests.get(docurl, stream=True, cookies=self.cookies)
        self._check_respose(response)
        if response.headers['Content-Type'] == 'text/html;charset=utf-8':
            raise RuntimeError(f"New login required. Log in to {self.base_url} in your browser, use the new cookie (mellon-sso_mu2e-docdb.fnal.gov) in the docdb constructor.")
        else:
            doc = io.BytesIO(response.content)
        return {"type":response.headers['Content-Type'].split("/")[1], "document":doc}

    def get_document(self, doc_id, file_name, version=1):
        """
        Wrapper for get_document_url allowing to access document via doc_id, filename, version.
        
        Args:
            doc_id (int)
            file_name(str)
            version(int,optional): defaults to 1

        Returns:
            see get_document_url
        """
        url_ = f"{self.base_url}RetrieveFile?docid={doc_id}&filename={quote(file_name)}&version={version}"
        return self.get_document_url(url_)

    def get(self, doc_id):
        """
        Get the metadata and all documents of from a docdb id.
        
        Args:
            doc_id: The docdb number.

        Returns:
            A dictionary containing the document's meta data as well as the associated documents. Containing docid_str, type, created, revised_content, revised_meta, title, abstract, files, topics, keyword, docid, version. Returns None if the document doesn't exist.

        Raises:
            RuntimeError: if no response, see _check_respose
        """
        out = self.get_meta(doc_id)
        if 'files' in out:
            for i, file in enumerate(out['files']):
                doc = self.get_document_url(file['link'])
                out['files'][i] = out['files'][i] | doc 
        return out

    def parse_pdf_slides(self, doc, add_image_descriptions=None):
        """
        Uses mu2e.paersers.pdf to parse all pdf documents of a docdb. Adds the parsed text to the doc dict. 

        Args:
            doc (dict): out put from get
            add_image_descriptions(str, optional): if set to a method [claude-sonnet, claude-haiku, openAI-o4Minin] the corresponding LLM is used to generate image descriptions.
        """
        for i, file in enumerate(doc['files']):
            if file['type'] == "pdf":
                p = mu2e.parser.pdf(file['document'])
                p.get_sldies_text()
                text_out = p.add_image_descriptions()
                doc['files'][i]['text'] = text_out
        return doc
    
    def save(self, doc, path="data/docs"):
        """
        Utility to save a docdb to disk.

        Args:
            doc (dict): out put from get (or get_meta)
            path (str, optional): direcotry path to store the data. Default is data/docs.
        """
        import json
        import os
        doc_filtered = doc.copy()
        doc_filtered['files'] = [{k: v for k, v in f.items() if k != "document"} for f in doc_filtered['files']]
        json_string = json.dumps(doc_filtered, indent=4)
        
        base_path = path+"/"
        docid = f"mu2e-docdb-{doc['docid']}" 
        dir_path = base_path+docid
        os.makedirs(dir_path, exist_ok=True)
        full_path = dir_path+"/meta.json"
        with open(full_path, 'w') as f:
                f.write(json_string)
        print(f"Data saved to {full_path}")

                
        
    