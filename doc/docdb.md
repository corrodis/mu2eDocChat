# Docdb Interface

A Python client to interact with the Document Database (DocDB). This package allows authentication, document retrieval, and parsing capabilities for documents.
The cridentials to be used need to be set as environment variables:
- MU2E_DOCDB_USERNAME
- MU2E_DOCDB_PASSWORD

## Quick Start

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

## RAG & Local Database/Vector-Storage
In order to perform Retrieval-Augmented Generation (RAG) style searches, a local vector-storage needs to be generated.
The location if the this database can either be set by setting MU2E_DATA_DIR or, if that is not set, `~/.mu2e/data` is used.
The generation of the embedings needs access to a embeding-model (so far openAI or Argo [TODO]).

In order to use openAI OPENAI_API_KEY needs to be set.

### Example: generating local vector database
By default, it will be stored in `~/.mu2e/data`. The default location can be modifed by setting MU2E_DATA_DIR.
```python
from mu2e.docdb import docdb

db = docdb()

# Generate all the embedings from all documents of the last 1 day
db.generate(days=1)
```

### Example: RAG
Example how to perform RAG based on the local vector storage (see above).
The 

```python
from mu2e import rag

# To find relevant documents for a query
query = "your search query here"
scores, doc_ids = rag.find(query)

# Print top 5 most relevant documents
for score, doc_id in zip(scores[:5], doc_ids[:5]):
    print(f"Document: {doc_id}")
    print(f"Relevance Score: {score:.3f}")
    print("---")

# load the most relvant document
from mu2e import tools
doc = tools.load(doc_ids[0])
print(doc['docid_str'], doc['title'])
```
