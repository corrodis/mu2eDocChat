import json
import os
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from .utils import get_data_dir, convert_to_timestamp, get_chroma_path
from .collections import get_collection, collection_names
from .docdb import docdb
from .chunking import chunk_text_simple
import threading
import time
from datetime import datetime
import tiktoken
from openai import OpenAI
from tqdm import tqdm




def saveInCollection(doc, collection=None, chunking_strategy="default"):
    """
    Save document to ChromaDB collection with text chunking.
    
    Args:
        doc: Document dictionary with 'files' key
        collection: ChromaDB collection (optional)
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks in tokens
        chunking_strategy: Strategy for chunking ('semantic', 'sentence', 'paragraph', 'token')
    """
    load_dotenv()

    docid = f"mu2e-docdb-{doc['docid']}"
    base_meta = {k: v for k, v in doc.items() if k != "files"}
    base_meta['doc_type'] = "mu2e-docdb"
    base_meta['doc_id'] = docid
    if 'topics' in base_meta:
        base_meta['topics'] = ", ".join(base_meta['topics'])
    if 'keyword' in base_meta:
        base_meta['keyword'] = ", ".join(base_meta['keyword'])
    if 'authors' in base_meta:
        base_meta['authors'] = ", ".join(base_meta['authors'])

    documents_ = []
    metadatas_ = []
    ids_ = []

    # Process each file and create chunks
    for file_idx, file_data in enumerate(doc['files']):
        text = file_data.get('text', '')
        if not text.strip():
            continue
            
        # Create chunks for this file
        chunk_size = 256 # defailt for all-MiniLM-L6-v2
        if collection:
            if hasattr(collection, 'max_input'):
                chunk_size = collection.max_input # 8000 for OpenAI models
            
        chunk_overlap = int(0.2 * chunk_size)
        chunks = chunk_text_simple(
            text, 
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=chunking_strategy
        )
        
        # Create ChromaDB entries for each chunk
        for chunk_idx, chunk_text in enumerate(chunks):
            # Create metadata for this chunk
            chunk_meta = base_meta.copy()
            chunk_meta.update({k: v for k, v in file_data.items() if k not in {"text", "document"}})
            chunk_meta['chunk_id'] = chunk_idx
            chunk_meta['total_chunks'] = len(chunks)
            chunk_meta['file_index'] = file_idx
            chunk_meta['chunk_size'] = chunk_size
            chunk_meta['chunk_overlap'] = chunk_overlap
            chunk_meta['chunking_strategy'] = chunking_strategy
            
            # Add timestamp fields for better date filtering
            chunk_meta['created_timestamp'] = convert_to_timestamp(chunk_meta.get('created'))
            chunk_meta['revised_timestamp'] = convert_to_timestamp(chunk_meta.get('revised_content'))
            
            # Create unique ID: docid_fileindex_chunkindex
            chunk_id = f"{docid}_{file_idx}_{chunk_idx}"
            
            documents_.append(chunk_text)
            metadatas_.append(chunk_meta)
            ids_.append(chunk_id)

    if len(ids_) == 0: #no files
        chunk_meta = base_meta.copy()
        chunk_meta['file_index'] = -1
        documents_.append(chunk_meta['abstract'])
        metadatas_.append(chunk_meta)
        chunk_id = f"{docid}_{-1}_{0}"
        ids_.append(chunk_id)

    collection = collection or get_collection() 

    if len(ids_) < 1:
        print(f"{docid} has no documents/chunks to store")
        return 
    
    if len(ids_) > 1000:
        print(f"{len(ids_)} chunks - thats more than {1000}, that doesn't sound right: {docid}")
        ids_ = ids_[:1000]
        metadatas_ = metadatas_[:1000]
        documents_ = documents_[:1000]
    print(f"Storing {len(ids_)} chunks for document {docid}")
    collection.upsert(
        documents=documents_,
        metadatas=metadatas_,
        ids=ids_)


def loadFromCollection(docid, nodb=False, collection=None, reconstruct_files=True):
    """
    Load document from ChromaDB collection, handling chunked data.
    
    Args:
        docid: Document ID to load
        nodb: Not used in this version
        collection: ChromaDB collection (optional)
        reconstruct_files: If True, combine chunks back into original files
        
    Returns:
        Document dictionary with reconstructed files or individual chunks
    """
    collection = collection or get_collection()

    if not docid.startswith("mu2e-docdb-"):
        full_docid = f"mu2e-docdb-{docid}"
    else:
        full_docid = docid

    results = collection.get(where={"doc_id": full_docid})
    
    if len(results['ids']) < 1:
        return None

    # Initialize document structure
    out = {'files': []}
    
    # Get base metadata from first result (excluding chunk-specific fields)
    base_metadata = results['metadatas'][0]
    for k, v in base_metadata.items():
        if k not in {'chunk_id', 'total_chunks', 'file_index', 'chunk_size', 
                    'chunk_overlap', 'chunking_strategy', 'link', 'filename', 'type', 'document'}:
            out[k] = v
    
    if not reconstruct_files:
        # Return individual chunks
        for i, (document, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
            chunk_data = {'text': document}
            for k, v in metadata.items():
                if k not in out:
                    chunk_data[k] = v
            out['files'].append(chunk_data)
        return out
    
    # Group chunks by file_index
    files_chunks = {}
    for i, (document, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
        file_idx = metadata.get('file_index', 0)
        chunk_idx = metadata.get('chunk_id', 0)
        
        if file_idx not in files_chunks:
            files_chunks[file_idx] = {}
            
        files_chunks[file_idx][chunk_idx] = {
            'text': document,
            'metadata': metadata
        }
    encoding = tiktoken.get_encoding("cl100k_base")
    # Reconstruct files by combining chunks
    for file_idx in sorted(files_chunks.keys()):
        chunk_dict = files_chunks[file_idx]
        
        # Sort chunks by chunk_id and combine text
        sorted_chunks = sorted(chunk_dict.items())
        combined_text = ""
        file_metadata = {}
        
        for chunk_id, chunk_data in sorted_chunks:
            if chunk_id == 0:
                combined_text = chunk_data['text']
                # Use metadata from first chunk for file-level metadata
                file_metadata = {k: v for k, v in chunk_data['metadata'].items() 
                               if k not in {'chunk_id', 'total_chunks', 'file_index', 
                                          'chunk_size', 'chunk_overlap', 'chunking_strategy'}}
            else:
                chunk_overlap_tokens = int(chunk_data['metadata'].get('chunk_overlap', 0))
                tokens = encoding.encode(chunk_data['text'])
                text_to_add = encoding.decode(tokens[chunk_overlap_tokens:])
                combined_text += text_to_add
        
        # Create file entry
        file_data = {'text': combined_text}
        for k, v in file_metadata.items():
            if k not in out:
                file_data[k] = v
                
        out['files'].append(file_data)
    
    return out

def load2(docid, nodb=False, collection=None):
    out = loadFromCollection(docid, nodb=False, collection=collection)
    if out:
        return out
    if nodb:
        return None
    # else get it  
    try:
        db = docdb()
    except:
        print("docdb connection failed")
        return {'id':id_, 'revised_content':'n/a', 'title':'Document retrival failed', 'files':[]}
    try:
        id_ = int(docid.split("-")[-1])
        return  db.get_parse_store(id_)
    except:
        print("Something went wrong in the document retrival")
        return {'id':id_, 'revised_content':'n/a', 'title':'Document not found', 'files':[]}

def load(docid, base_path=None, nodb=False):
    """
    Loads a document from the local storage/cache.

    Args:
        docid(str): unique docid, this is the name of the folder
        base_path(str, optional): base path of the documents. Defaults to data/docs/.

    Returns:
        dic: doc meta data and list with files
    """
    # load a document from store
    dir_path = Path(base_path if base_path else get_data_dir()) / docid
    # check if the document already exists, if not, lets try to get it
    if not os.path.exists(dir_path):
        if nodb:
            return None # don't load 
        if docid.startswith("mu2e-docdb"):
            import mu2e
            from mu2e import docdb
            id_ = int(docid.split("-")[-1])
            try:
                db = docdb()
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
    with open(dir_path / "meta.json", 'r') as file:
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


def generate_from_local_all():
    """wrapper for generate_from_local that automatically generates all non-default collections"""
    for collection_name in collection_names:
        if collection_name not in ["default"]:
            print(f"Generating {collection_name} collection...")
            c = get_collection(collection_name)
            generate_from_local(c)


def load_from_file(base_path=None, docid=None):
    base_dir = Path(base_path if base_path else get_data_dir())

    if not base_dir.exists():
        print(f"Data directory {base_dir} does not exist")
        return None
    
    if not docid.startswith('mu2e-docdb-'):
        docid = f"mu2e-docdb-{docid}"

    doc_dir = base_dir / docid
    if not doc_dir.exists():
        print(f"Document directory {doc_dir} does not exist")
        return None
    
    meta_file = doc_dir / "meta.json"
    if not meta_file.exists():
        print(f"meta.json not found in {doc_dir}")
        return None
    
    try:
        with open(meta_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {docid}: {str(e)}")
        return None

def iterate_documents(base_path=None, show_progress=True):
    """
    Iterator that yields document metadata from locally stored documents.
    
    Args:
        base_path: Base path for documents (defaults to ~/.mu2e/data)
        show_progress: Whether to show progress bar (default: True)
        
    Yields:
        tuple: (doc_dir_path, document_metadata_dict) for each valid document
    """
    base_dir = Path(base_path if base_path else get_data_dir())
    
    if not base_dir.exists():
        print(f"Data directory {base_dir} does not exist")
        return
    
    doc_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith('mu2e-docdb-')]
    if not doc_dirs:
        print("No documents found in data directory")
        return
    
    print(f"Found {len(doc_dirs)} documents")
    iterator = tqdm(doc_dirs, desc="Processing documents") if show_progress else doc_dirs

    for doc_dir in iterator:
        docid = doc_dir.name
        doc = load_from_file(base_path=base_path, docid=docid)

        if doc is not None:
            yield doc

def generate_from_local(collection=None, chunking_strategy="default", base_path=None, docid=None):
    """
    Generate embeddings from locally stored documents (meta.json files) into a ChromaDB collection.
    This is useful for regenerating collections with different settings without re-downloading.
    
    Args:
        collection: ChromaDB collection (uses default if None)
        chunking_strategy: Strategy for chunking text (default: "default")
        base_path: Base path for documents (defaults to ~/.mu2e/data)
        docid: Specific document ID to process (e.g., "mu2e-docdb-12345"). If None, processes all documents.
    Returns:
        int: Number of documents successfully processed
    """
    processed_count = 0

    if docid:
        doc = load_from_file(base_path=base_path, docid=docid)
        if doc is None:
            return 0
        
        try:
            # Check if we already have this cached
            doc_ = load2(doc['doc_id'], nodb=True, collection=collection)
            if doc_ is not None:
                print(f"{doc['doc_id']} - present")
            else:
                print(f"{doc['doc_id']} - processing")
                saveInCollection(doc, collection=collection, chunking_strategy=chunking_strategy)
            processed_count = 1
            
        except Exception as e:
            print(f"Error processing {doc['doc_id']}: {str(e)}")
            return 0
    else:
        # Process all documents
        for doc in iterate_documents(base_path=base_path):
            try:
                # Check if we already have this cached
                doc_ = load2(doc['doc_id'], nodb=True, collection=collection)
                if doc_ is not None:
                    print(f"{doc['doc_id']} - present")
                else:
                    print(f"{doc['doc_id']} - processing")
                    saveInCollection(doc, collection=collection, chunking_strategy=chunking_strategy)
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing {doc['doc_id']}: {str(e)}")
                continue
    
    print(f"Successfully processed {processed_count} documents")
    
    # Save timestamp
    collection_name = getattr(collection, 'name', 'default') if collection else 'default'
    timestamp_file = Path(get_data_dir()) / f"last_generate_{collection_name}.json"
    Path(get_data_dir()).mkdir(exist_ok=True)
    
    with open(timestamp_file, 'w') as f:
        json.dump({"last_run": datetime.now().isoformat(), "processed": processed_count}, f)
    
    return processed_count

def start_background_generate(interval_minutes=5, days=1, collection=None, from_local=False):
    """Start background generation every interval_minutes"""
    def background_loop():
        from mu2e import docdb
        while True:
            try:
                print("Running background generate...")
                if from_local:
                    generate_from_local(collection=collection)
                else:
                    db = docdb(collection=collection)
                    db.generate(days=days)
                    print(f"Background generate completed, sleeping for {interval_minutes} minutes")
            except Exception as e:
                print(f"Background generate failed: {e}")
            time.sleep(interval_minutes * 60)
    
    thread = threading.Thread(target=background_loop, daemon=True)
    thread.start()
    print(f"Started background generate (every {interval_minutes} minutes)")

def get_last_generate_info(collection_name='default'):
    """Get last generate timestamp info"""
    try:
        timestamp_file = Path(get_data_dir()) / f"last_generate_{collection_name}.json"
        if timestamp_file.exists():
            with open(timestamp_file, 'r') as f:
                return json.load(f)
        return {"last_run": None}
    except:
        return {"last_run": None}

def getOpenAIClient(base_url=None, api_key=None):
    load_dotenv()
    base_url = base_url or os.getenv('MU2E_CHAT_BASE_URL', 'http://localhost:55019/v1')
    api_key = api_key or os.getenv('MU2E_CHAT_API_KEY', 'whatever+random')
        
    return OpenAI(
        base_url=base_url,
        api_key=api_key
    )
