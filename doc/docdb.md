# Docdb Interface

A Python client to interact with the Document Database (DocDB). This package allows authentication, document retrieval, and parsing capabilities for documents.

## Authentication

The DocDB client uses secure credential storage via the system keyring. Credentials are automatically managed and you'll only need to enter them once per system.

### Setting up credentials

Use the CLI to securely store your DocDB password:

```bash
# Set password (will prompt for username and password)
mu2e-docdb set-password
DocDB username: your_username
Enter DocDB password for your_username: [hidden input]
Password saved for user 'your_username'
```

### Managing credentials

```bash
# Clear stored password
mu2e-docdb clear-password
Username to clear [your_username]: 
Cleared stored password for user 'your_username'
```

### Fallback to environment variables

If you prefer environment variables (less secure), you can still use:
- `MU2E_DOCDB_USERNAME`
- `MU2E_DOCDB_PASSWORD`

The system will automatically prompt for credentials if none are found in keyring or environment variables.

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

#### Password Management
```bash
# Set DocDB password securely in system keyring
mu2e-docdb set-password

# Clear stored password
mu2e-docdb clear-password
```

#### Generate from DocDB (downloads recent documents)
```bash
mu2e-docdb --collection=default generate --days=1
mu2e-docdb --collection=argo generate --days=1
mu2e-docdb --collection=multi-qa generate --days=1

# Force reload documents even if they exist locally
mu2e-docdb --collection=argo generate --days=7 --force-reload
```

#### Generate from Local Cache (faster, uses previously downloaded documents)
```bash
# Generate specific collection from local documents
mu2e-docdb --collection=argo generate-local
mu2e-docdb --collection=multi-qa generate-local

# Generate ALL non-default collections from local documents (convenience command)
mu2e-docdb generate-local-all
```

**Notes:** 
- `generate-local` commands use documents already downloaded and cached locally in `~/.mu2e/data`. This is much faster since it skips the DocDB download step and only regenerates embeddings with different models/settings.
- `--force-reload` option forces re-downloading documents from DocDB even if they already exist locally. Useful when documents have been updated or when local cache is corrupted.

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
