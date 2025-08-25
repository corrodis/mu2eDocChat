# Collections - Embedding Integration

The `collections.py` module provides unified access to different embedding services including Argonne National Laboratory's Argo API. Multiple collection types are supported with different embedding strategies.

## Available Collections

```python
from mu2e.collections import get_collection, collection_names

print(collection_names)  # ['default', 'argo', 'multi-qa', 'custom', 'ATLAS']
```

## Basic Usage

```python
from mu2e.collections import get_collection

# Get default collection (local embeddings)
c = get_collection()
c = get_collection('default')

# Get Argo collection (ANL API, 8000+ token context)  
c = get_collection('argo')

# Get multi-qa collection (SentenceTransformer)
c = get_collection('multi-qa')
```

## CLI Usage

All CLI tools now use the unified `--collection` parameter:

```bash
# Generate embeddings with different collections
mu2e-docdb --collection=default generate --days=7
mu2e-docdb --collection=argo generate --days=7
mu2e-docdb --collection=multi-qa generate --days=7

# Search with different collections
mu2e-docdb --collection=argo search "physics analysis"

# MCP server with specific collection
mu2e-mcp-server --collection=argo --dbname=Mu2e
```

## Argo Collection Details

The Argo collection provides OpenAI-compatible embeddings with larger context windows (8000+) compared to default local embeddings (256).

### Custom Model and Proxy

```python
# Use specific Argo model
c = get_collection('argo', model='v3large')

# Connect through local proxy (e.g., SSH tunnel on port 55019)
c = get_collection('argo', url="http://localhost:55019/v1/embed")

# Custom user and model
c = get_collection('argo', 
    user="your_username",
    model="v3large", 
    url="http://localhost:55019/v1/embed"
)
```

## Available Models
See the Argo API for details: https://anl.app.box.com/notes/1444961193376?s=ubtrsefonqeo9xppdzcurezy8rzsbs96

| Model | Dimensions | Use Case |
|-------|------------|----------|
| v3small | 1536 | Balanced performance/speed |
| v3large | 3072 | Higher quality embeddings |
| ada002 | 1536 | OpenAI compatibility |
