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
The location can be set by setting MU2E_DATA_DIR or, if not set, `~/.mu2e/data` is used.

Multiple embedding collections are supported:
- **default**: Local embeddings (256 token context)
- **argo**: ANL Argo API (8000+ token context, requires credentials)
- **multi-qa**: SentenceTransformer embeddings (512 token context)

### Example: generating local vector database
```python
from mu2e.docdb import docdb
from mu2e.collections import get_collection

# Generate with default collection
db = docdb()
db.generate(days=1)

# Generate with Argo collection (requires ANL access)
db_argo = docdb(collection=get_collection('argo'))
db_argo.generate(days=1)

# Generate with multi-qa collection
db_multiqa = docdb(collection=get_collection('multi-qa'))
db_multiqa.generate(days=1)
```

### CLI Usage
```bash
# Generate with different collections
mu2e-docdb --collection=default generate --days=1
mu2e-docdb --collection=argo generate --days=1
mu2e-docdb --collection=multi-qa generate --days=1
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
