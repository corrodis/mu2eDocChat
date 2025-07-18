import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re
import io
from urllib.parse import quote
from datetime import datetime
import os
from .parsers import parser
from .utils import get_data_dir

class docdb:
    """
    Client to retrive documents from FNAL docdb.

    Attributes:
        base_url (str): The base URL of the docdb server.
        cookies (dict): if you already have an active session and want to use a cooke-string from that. No longer needed. Defaults to None.
        bool (bool): if True a new session is started with the credentials from the environment variables MU2E_DOCDB_USERNAME, MU2E_DOCDB_PASSWORD. Defaulkts to True.

    Example:
	```python
	from mu2e.docdb import docdb

	# Initialize client
	db = docdb() # defaults to mu2e
	# db = docdb() for g-2 docdb

	# List documents from last 3 days
	db.list_latest(days=3)

	# Get a document by ID
	doc = db.get(51472)

	# The document contains:
	print(doc['title'])        # Document title
	print(doc['abstract'])     # Document abstract
	print(doc['files'])        # List of files with content
	print(doc['topics'])       # List of topics
	```
    """
    def __init__(self, base_url : str = None, login : bool = True, collection = None):
        """
        Args:
            base_url (str, optional): The base URL of the docdb server. Defaults to https://mu2e-docdb.fnal.gov/cgi-bin/sso/.
            collection (chromadb Collection, optinal): Collection that is used
        """
        self.cookies = None #{"mellon-sso_mu2e-docdb.fnal.gov": cookie}
        self.base_url = base_url if base_url else "https://mu2e-docdb.fnal.gov/cgi-bin/sso/"
        self.session = None
        self.collection = collection # chromadb
        if login:
            missing = []
            if not os.getenv('MU2E_DOCDB_USERNAME'):
                missing.append('MU2E_DOCDB_USERNAME')
            if not os.getenv('MU2E_DOCDB_PASSWORD'):
                missing.append('MU2E_DOCDB_PASSWORD')
            if missing:
                raise ValueError(
                    f"Missing required environment variables: {', '.join(missing)}. "
                    "Please set these environment variables."
                )
            self.login()

    def __del__(self):
        if self.session:
            self.session.close()

    def login(self):
        session = requests.Session() # we could change to use session.get instead of requests.get
        
        # Step 1: Initial request to docdb
        response = session.get(self.base_url)

        # Step 2: Submit the authentication method choice, use username/password
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        auth_url = urljoin('https://pingprod.fnal.gov', form['action'])
        auth_data = {
            'pfidpadapterid': 'ad..FormBased',  # Services Username and Password
            'rememberChoice': 'false'
        }
        response = session.get(auth_url, params=auth_data)

        # Step 3: Submit login credentials
        #print("Step 3: Submitting credentials...")
        oup = BeautifulSoup(response.text, 'html.parser')
        login_form = soup.find('form')
        if not login_form:
            session.close()
            raise ValueError("Could not find login form")
        login_url = urljoin('https://pingprod.fnal.gov', login_form['action'])
    
        import mu2e # for docdb_credentials
        login_data = {
            'pf.username': os.getenv('MU2E_DOCDB_USERNAME'),
            'pf.pass': os.getenv('MU2E_DOCDB_PASSWORD'),
            'pf.ok': 'clicked',
            'pf.adapterId': 'FormBased',
            'pf.cancel': ''
        }
        response = session.post(login_url, data=login_data)

        # at this point we should be logged in in this session
        # we could use response to forward to our original request if needed
        # below I just look for its present to indicate a bad login
        #print("Step 4: Getting target URL...")
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        if form:
            saml_url = form['action']
            saml_response = form.find('input', {'name': 'SAMLResponse'})['value']
            relay_state = form.find('input', {'name': 'RelayState'})['value']
        
            saml_data = {
                'RelayState': relay_state,
                'SAMLResponse': saml_response
            }
            # Submit SAML response and get redirected to the final URL
            response = session.post(saml_url, data=saml_data)
        else:
            print("No SAML form found in response")
        self.response = response.text



        self.cookies = {"mellon-sso_mu2e-docdb.fnal.gov": session.cookies.get('mellon-sso_mu2e-docdb.fnal.gov')}
        self.session = session

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
        
    def _parse_list(self, text):
        soup = BeautifulSoup(text, 'html.parser')
        table = soup.find('table', {'id': 'DocumentTable'})
        if not table:
            return []
        documents = []
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            doc_id = cells[0].find('a').text.split("-")[0].strip()
            title = cells[1].find('a').text.strip()
            link = cells[1].find('a').get('href')
            author_cell = cells[2]
            authors = []
            for author in author_cell.find_all('a'):
                authors.append(author.text.strip())
            if author_cell.find('i'):  # Handle "et al." case
                authors.append("et al.")
            topic_cell = cells[3]
            topics = []
            for topic in topic_cell.find_all('a'):
                topics.append(topic.text.strip())
            date_str = cells[4].text.strip()
            try:
                last_updated = datetime.strptime(date_str, '%d %b %Y')
            except ValueError:
                last_updated = date_str
            doc = {"id":doc_id,
                   "doc_id":"mu2e-docdb-"+str(doc_id),
                   "tite":title,
                   "authors":authors,
                   "topics":topics,
                   "last_updated":last_updated,
                   "link:":link}
            documents.append(doc)
        return documents


    def list_latest(self, days : int = 30):
        """
        Get a list of the latest documents.

        Args:
            days: Number of days to list documents.

        Returns:
            A list with documents objects containing docdbid, Title, Authors, topics, last update.
        """
        from datetime import datetime
        url_ = f"{self.base_url}ListBy?days={days}"
        response = requests.get(url_, cookies=self.cookies)
        #print(response.text)
        return self._parse_list(response.text)

    def search(self, text : str = None, before : datetime = None, after : datetime = None):
        data = {
            "outerlogic": "AND",
            "innerlogic": "OR",
            "mode": "date",
            "titlesearchmode": "allword",
            "abstractsearchmode": "allword",
            "keywordsearchmode": "allword",
            "revisionnotesearchmode": "allword",
            "pubinfosearchmode": "allword",
            "filesearchmode": "allword",
            "filedescsearchmode": "allword",
            "includesubtopics": "on"
        }
        if text:
            data["titlesearch"] = text
            data["abstractsearch"] = text
            data["keywordsearch"] = text
        if before:
            data["beforeday"] = str(before.day)
            data["beforemonth"] = before.strftime("%b")
            data["beforeyear"] = str(before.year)
        else:
            data["beforeday"] = "--"
            data["beforemonth"] = "---"
            data["beforeyear"] = "----"

        if after:
            data["afterday"] = str(after.day)
            data["aftermonth"] = after.strftime("%b")
            data["afteryear"] = str(after.year)
        else:
            data["afterday"] = "--"
            data["aftermonth"] = "---"
            data["afteryear"] = "----"
        #print(data)
        response = self.session.post(self.base_url+"/Search", data=data, )
        return self._parse_list(response.text)


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
                  "authors":  {"search":"Authors:",          "list":True},
                  "keyword": {"search":"Keywords:",          "list":True}
                 }
        for field in fields:
            key = soup.find('dt', class_='InfoHeader', string=fields[field]["search"])
            if key:
                if field in ["topics","authors"]:
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
        
        if "docid_str" not in result:
            return None
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
            #print(response.text)
            try:
                soup = BeautifulSoup(response.text, 'html.parser')
                page_title = soup.title.string if soup.title else None
                if page_title:
                    if page_title == "Select Authentication System":
                        raise RuntimeError(f"New login required. Log in to {self.base_url} in your browser, use the new cookie (mellon-sso_mu2e-docdb.fnal.gov) in the docdb constructor.")
            except:
                pass
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
        
        Argsself.:
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
        if out is None:
            return out
        if 'files' in out:
            for i, file in enumerate(out['files']):
                doc = self.get_document_url(file['link'])
                out['files'][i] = out['files'][i] | doc 
        return out

    def parse_files(self, doc, add_image_descriptions=None):
        """
        Runs all implemented parsings.
        
        Args:
            doc: Document dictionary with files
            add_image_descriptions (bool): Whether to generate AI descriptions for images
                                         If None, uses environment variable settings
        """
        from .utils import should_add_image_descriptions
        
        if add_image_descriptions is None:
            add_image_descriptions = should_add_image_descriptions()
        
        for i, file in enumerate(doc['files']):
            try:
                p = parser(file['document'], file['type'])
                text_out, images = p.get_text()
                if add_image_descriptions and images:
                    text_out = p.add_image_descriptions(text_out, images)
                doc['files'][i]['text'] = text_out
            except Exception as e:
                print(e)
                continue
        return doc
  
    def saveFiles(self, doc):
        import os
        path = get_data_dir()
        docid = f"mu2e-docdb-{doc['docid']}"
        dir_path = path / docid
        os.makedirs(dir_path, exist_ok=True)
        if 'files' in doc:
            for f in doc['files']:
                with open(dir_path / f['filename'], 'wb') as f_:
                    f_.write(f['document'].getvalue())

    
    def saveMetaJson(self, doc, path=None):
        #from mu2e import rag
        """
        Utility to save a docdb to disk.

        Args:
            doc (dict): out put from get (or get_meta)
            path (str, optional): direcotry path to store the data. 
                                  If None, uses MU2E_DATA_DIR or ~/.mu2e/data
        """
        import json
        import os
        doc_filtered = doc.copy()
        doc_filtered['files'] = [{k: v for k, v in f.items() if k != "document"} for f in doc_filtered['files']]
        
        if path is None:
            path = get_data_dir()
        base_path = path
        docid = f"mu2e-docdb-{doc['docid']}" 
        doc_filtered['doc_type'] = "mu2e-docdb"
        doc_filtered['doc_id']   = docid
        json_string = json.dumps(doc_filtered, indent=4)
        dir_path = base_path / docid
        os.makedirs(dir_path, exist_ok=True)
        full_path = dir_path / "meta.json"
        with open(full_path, 'w') as f:
                f.write(json_string)
        # also generate the embedding
        #rag.doc_generate_embedding(docid)
        #print(f"Data saved to {full_path}")
    
    def get_and_parse(self, docid, add_image_descriptions=False):
        doc_full = self.get(docid)
        if doc_full is None:
            return None
        self.parse_files(doc_full, add_image_descriptions=add_image_descriptions)
        return doc_full

    def get_parse_store(self, docid, save_raw=False, add_image_descriptions=False):
        from mu2e import tools
        doc_full = self.get_and_parse(docid, add_image_descriptions=add_image_descriptions)
        if doc_full is None:
            return None
        tools.saveInCollection(doc_full, self.collection)
        if save_raw:
            self.saveMetaJson(doc_full)
            self.saveFiles(doc_full)
        return doc_full

    def generate(self, days=10, force_reload=False, save_raw=True, add_image_descriptions=False):
        from mu2e import tools
        latest = self.list_latest(days)
        for doc in latest:
            if doc['id'] in []:
                continue
            doc_ = None
            if not force_reload:
                doc_ = tools.load2("mu2e-docdb-"+str(doc['id']), nodb=True, collection=self.collection) # check if we already have this cached
                if not doc_ is None:
                    print("mu2e-docdb-"+str(doc['id'])+" - present")
                else:
                    print("mu2e-docdb-"+str(doc['id'])+" - get, parse, store...")
            if doc_ is None:
                self.get_parse_store(doc['id'], save_raw=save_raw, add_image_descriptions=add_image_descriptions)
            
    
