import numpy as np
from mu2e import tools
import os
from .utils import get_data_dir
from pathlib import Path


def get_embedding(text, model="text-embedding-3-small"):
    """
    Generates embedings for a given text.
    
    If the text is longer than the max allowed token, it is split and multiple embedings are returned.

    Args:
        text(str): text to be embeded
        model(optional): openAI model to be used, defaults to 'text-embedding-3-small'

    Returns:
        embedings(vector(
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError(
            "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."
        )

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "The 'openAI' package is required for embedding generation. "
            "Please install it with: pip install openai"
        )    
    import tiktoken
    client = OpenAI(api_key=api_key)
    encoding = tiktoken.encoding_for_model(model)
    num_tokens = len(encoding.encode(text))
    # max token is 8191
    if num_tokens > 8191:
        n = int(np.ceil(num_tokens/8191))
        input = [text[i:i+8000] for i in range(0, n, 8000)]
    else:
        input = [text]
    emb = client.embeddings.create(
        model=model,
        input=input
    )
    return np.array([e.embedding for e in emb.data])


def doc_generate_embedding(docid, model="text-embedding-3-small", path=None):
    base_path = Path(path if path else get_data_dir())
    doc = tools.load(docid)
    if "files" in doc:
        embs = None
        print("DEBUG!", doc["files"])
        for file in doc["files"]:
            emb = get_embedding(file['text'], model=model)
            print("Number of generated embedings ("+file['filename']+"): ", len(emb))
            if embs is None:
                embs = emb
            else:
                embs = np.concatenate((embs, emb))
        emb_file_path = base_path / "embeddings.npy"
        if os.path.exists(emb_file_path):
            allEmbeddings = np.load(emb_file_path)
            print("DEBUG:", allEmbeddings.shape, embs.shape)
            allEmbeddings = np.concatenate((allEmbeddings, embs))
        else:
            allEmbeddings = embs
        np.save(emb_file_path, allEmbeddings)
        with open(base_path / "embeddings_ids.txt", "a") as f:
            for k in range(embs.shape[0]):
                f.write(docid + "\n")
        

def find(q, model="text-embedding-3-small", path=None):
    base_path = Path(path if path else get_data_dir())
    all_emb = np.load(base_path / "embeddings.npy")
    q_emb = get_embedding(q, model=model)
    dot_product = np.dot(q_emb,all_emb.T)

    emb_magnitude = np.linalg.norm(all_emb, axis=1, keepdims=True)
    q_emb_magnitude = np.linalg.norm(q_emb)
    cosine_sim = dot_product.flatten() / (emb_magnitude.flatten() * q_emb_magnitude.flatten())
    sort = np.argsort(cosine_sim.flatten())[::-1]

    with open(base_path / "embeddings_ids.txt", 'r') as file:
        ids = file.readlines()
    #print("DEBUG", all_emb.shape, cosine_sim.shape, len(ids))
    
    return cosine_sim[sort], [ids[id][:-1] for id in sort]
