# ANL Argo API Integration

The `anl.py` module provides integration with Argonne National Laboratory's Argo API. If used for the embeddings, Argo offerst the openAI embeddings which have much larger context windows (8000+) than the default local one (256).

## Basic Usage

```python
import mu2e.anl as anl

# Get a collection with default settings (v3small model)
c = anl.get_collection()
```

## Custom Model Selection

```python
# Use different embedding models
c_large = anl.get_collection(model="v3large")  # 3072 dimensions
c_small = anl.get_collection(model="v3small")  # 1536 dimensions  
c_ada = anl.get_collection(model="ada002")     # 1536 dimensions
```

## Using with Argo-Proxy

For off-site use, running [argo-openai-proxy](https://github.com/Oaklight/argo-openai-proxy) on-site with SSH tunnel allows to run off-site like (assuming argo-proxy runs on port 55019):

```python
# Connect through local proxy (e.g., SSH tunnel on port 55019)
c = anl.get_collection(url="http://localhost:55019/v1/embed")

# Or specify custom user and model
c = anl.get_collection(
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