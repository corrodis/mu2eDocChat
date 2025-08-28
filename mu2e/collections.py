import sqlite3
from packaging import version
if version.parse(sqlite3.sqlite_version) < version.parse("3.35.0"):
    # hack from https://gist.github.com/defulmere/8b9695e415a44271061cc8e272f3c300
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents
from chromadb.utils import embedding_functions
import requests
import json
from typing import List
import os
from sentence_transformers import SentenceTransformer
import chromadb.utils.embedding_functions as embedding_functions
from huggingface_hub import HfFolder




_client = None
def _get_client():
    global _client
    if _client is None:
        from .utils import get_chroma_path
        _client = chromadb.PersistentClient(path=get_chroma_path())
    return _client

collection_names = ["default",
                    "argo",
                    "multi-qa", 
                    "custom", 
                    "ATLAS"]


def get_collection(collection_name=None, user=None, model=None, url=None):
    """Get a ChromaDB collection by name or type"""
    client = _get_client()
    
    if collection_name is None: # load from settings
        collection_name = name=os.getenv('MU2E_CHROMA_DEFAULT_COLLECTION') or "mu2e_default" 

    if collection_name in ['argo']:
        # Return Argo collection with custom embedding function
        model_ = model or "v3small"
        collection_name = f"mu2e_argo_{model_}"
        embedding_func = ArgoEmbeddingFunction(user=user or os.environ.get('USER'), model=model_, url=url)
        c = client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_func
            )
        c.max_input = 8190
        return c
    elif collection_name in ['multi-qa']:
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="multi-qa-mpnet-base-dot-v1"
        )
        collection_name = f"mu2e_multi-qa-mpnet"
        c = client.get_or_create_collection(
                name=collection_name,
                embedding_function=sentence_transformer_ef
            )
        c.max_input = 512
        return c

    elif collection_name in ['custom']:
        embedding_func = FinetunedEmbeddingFunction()
        collection_name = f"mu2e_multi-qa-mpnet-custom"
        c = client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_func
            )
        c.max_input = 512
        return c
    elif collection_name in ['ATLAS']:
        embedding_func = ATLASEmbeddingFunction()
        collection_name = f"mu2e_multi-qa-mpnet-ATLAS"
        c = client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_func
            )
        c.max_input = 512
        return c
        
    if collection_name in ['default']:
        c = client.get_or_create_collection(name="mu2e_default")
        c.max_input = 256
        return c
    else:
        # Return default collection
        return get_collection(collection_name=None, user=user, model=model, url=url)

class ArgoEmbeddingFunction(EmbeddingFunction):
    def __init__(self, user: str, model: str = "v3small", url=None):
        """
        Custom embedding function for Argo API
        
        Args:
            user (str, optional): Username for the API
            model (str, optional): One of 'ada002', 'v3large', 'v3small'
            url (str, optional): Argo URL, defaults to MU2E_ARGO_EMBED_URL or https://apps-dev.inside.anl.gov/argoapi/api/v1/resource/embed/
        """
        self.user = user
        self.model = model
        self.url = url or os.getenv('MU2E_ARGO_EMBED_URL',"https://apps-dev.inside.anl.gov/argoapi/api/v1/resource/embed/")
        self.headers = {"Content-Type": "application/json"}
        
        # Set dimensions based on model
        self.dimensions = {
            "ada002": 1536,
            "v3large": 3072, 
            "v3small": 1536
        }
        
        #self.max_input = 8191
    
    def __call__(self, input: Documents) -> List[List[float]]:
        """
        Generate embeddings for the input documents
        
        Args:
            input: List of documents to embed
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        # Prepare the payload
        data = {
            "user": self.user,
            "prompt": input,
            "model": self.model  # Add model if your API supports it
        }
        print("DEBUG DEBUG DEBUG") 
        import tiktoken
        for inp in input:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            print("TOKENS", len(encoding.encode(inp)))
        
        payload = json.dumps(data)
        print(payload)
        
        try:
            # Send POST request
            print("DEBUG DEBUG DEBUG", self.url)
            response = requests.post(self.url, data=payload, headers=self.headers)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            # Extract embeddings from response
            result = response.json()
            embeddings = result["embedding"]
            
            return embeddings
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")
        except KeyError as e:
            raise Exception(f"Unexpected API response format: {e}")

class FinetunedEmbeddingFunction(EmbeddingFunction):
    
    def __init__(self):
        self.model = SentenceTransformer("aeboots/multi-qa-mpnet-base-dot-v1-mu2e")

    def __call__(self, input: Documents) -> List[List[float]]:
        data = []
        for inp in input:
            vec = self.model.encode(inp)
            data.append(vec)

        return data

class ATLASEmbeddingFunction(EmbeddingFunction):
    
    def __init__(self):
        self.model = SentenceTransformer('../multi-qa-mpnet-base-dot-v1-ATLAS-TALK')

    def __call__(self, input: Documents) -> List[List[float]]:
        data = []
        for inp in input:
            vec = self.model.encode(inp)
            data.append(vec)

        return data



