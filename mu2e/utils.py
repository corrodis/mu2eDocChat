from pathlib import Path
import os
from datetime import datetime
from typing import Union, Optional

def get_lof_dir():
    log_dir = os.getenv('MU2E_LOG_DIR')
    if log_dir:
        return Path(log_dir)
    return Path.home() / '.mu2e' / 'logs'

def get_data_dir():
    """Get the data directory for docdb storage, creating it if necessary."""
    # First priroty is the environment variable
    data_dir = os.getenv('MU2E_DATA_DIR')
    if data_dir:
        return Path(data_dir)

    # If not set, use default in home directory
    default_dir = Path.home() / '.mu2e' / 'data'
    
    if not default_dir.exists():
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created default data directory at {default_dir}")
            print("You can override this location by setting MU2E_DATA_DIR environment variable")
        except Exception as e:
            raise RuntimeError(
                "Could not find or create data directory. "
                "Please either:\n"
                "1. Set MU2E_DATA_DIR environment variable\n"
                "2. Ensure ~/.mu2e/data can be created\n"
                f"Error: {str(e)}"
            )
    
    return default_dir

def get_chroma_path():
    c_dir = os.getenv('MU2E_CHROMA_PATH')
    if c_dir:
        return Path(c_dir)
    
    default_dir = Path.home() / '.mu2e' / 'chroma'
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir


def convert_to_timestamp(date_input: Union[str, datetime, int]) -> Optional[int]:
    """
    Convert various date formats to Unix timestamp.
    
    Args:
        date_input: Date as string, datetime object, or timestamp
        
    Returns:
        Unix timestamp (int) or None if conversion fails
    """
    if date_input is None:
        return None
    
    if isinstance(date_input, int):
        return date_input
    
    if isinstance(date_input, datetime):
        return int(date_input.timestamp())
    
    if isinstance(date_input, str):
        try:
            # Handle format like '20 Jun 2025, 02:04'
            dt = datetime.strptime(date_input, '%d %b %Y, %H:%M')
            return int(dt.timestamp())
        except ValueError:
            try:
                # Handle format like '20 Jun 2025'
                dt = datetime.strptime(date_input, '%d %b %Y')
                return int(dt.timestamp())
            except ValueError:
                try:
                    # Handle ISO format
                    dt = datetime.fromisoformat(date_input)
                    return int(dt.timestamp())
                except ValueError:
                    return None
    
    return None

def list_to_search_result(docs):
    n_results = len(docs)
    
    # Extract basic fields
    documents = []
    ids = []
    metadata = []
    
    for i, doc in enumerate(docs):
        
        # Create ID with chunk info
        doc_id = doc.get('doc_id', f"mu2e-docdb-{doc.get('id', '')}")
        ids.append(f"{doc_id}")
        
        # Convert datetime to timestamp if present
        last_updated = doc.get('last_updated')
        if last_updated:
            timestamp = int(last_updated.timestamp())
        else:
            timestamp = 0
        
        # Build metadata dictionary
        meta = {
            'created_timestamp': timestamp,
            'revised_timestamp': timestamp,
            'revised_meta': last_updated.strftime('%d %b %Y, %H:%M') if last_updated else '',
            'version': 1,
            'title': doc.get('tite', doc.get('title', '')),
            'created': last_updated.strftime('%d %b %Y, %H:%M') if last_updated else '',
            'docid_str': f"Mu2e-doc-{doc.get('id', '')}-v1",
            'doc_id': doc.get('doc_id', ''),
            'abstract': '',  # Not available in source format
            'topics': ', '.join(doc.get('topics', [])),
            'revised_content': last_updated.strftime('%d %b %Y, %H:%M') if last_updated else '',
            'link': doc.get('link:', ''),
            'doc_type': 'mu2e-docdb',
            'filename': doc.get('filename:', ''),
        }
        
        metadata.append(meta)
    
    return {
        'query': 'list',
        'n_results': n_results,
        'documents': ['']*n_results,
        'distances': [1.0]*n_results,  # Ensure same length
        'ids': ids,
        'metadata': metadata
    }