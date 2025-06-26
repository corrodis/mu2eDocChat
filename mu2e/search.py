"""
Search and retrieval interface for ChromaDB collections with filtering capabilities.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from .tools import getDefaultCollection
from .utils import convert_to_timestamp, list_to_search_result
from .docdb import docdb


def search(
    query: str,
    collection=None,
    n_results: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    date_range: Optional[Dict[str, Union[str, datetime, int]]] = None,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Search documents in ChromaDB collection with filtering options.
    
    Args:
        query: Search query text
        collection: ChromaDB collection (uses default if None)
        n_results: Number of results to return
        filters: Raw ChromaDB where filters (dict)
        date_range: Date filtering with 'start' and/or 'end' keys 
                   (accepts datetime objects, timestamps, or date strings)
        include_metadata: Whether to include full metadata in results
        
    Returns:
        Dictionary with search results including documents, metadata, distances, and ids
    """
    collection = collection or getDefaultCollection()
    
    # Build where clause from filters
    where_clause = _build_where_clause(
        filters=filters,
        date_range=date_range
    )
    
    # Perform search
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_clause if where_clause else None,
        include=['documents', 'metadatas', 'distances']
    )
    
    # Format results
    formatted_results = {
        'query': query,
        'n_results': len(results['ids'][0]),
        'documents': results['documents'][0],
        'distances': results['distances'][0],
        'ids': results['ids'][0]
    }
    
    if include_metadata:
        formatted_results['metadata'] = results['metadatas'][0]
    
    return formatted_results


def search_fulltext(
    query: str,
    n_results: int = 5,
    collection=None,
    filters: Optional[Dict[str, Any]] = None,
    date_range: Optional[Dict[str, Union[str, datetime, int]]] = None,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Full-text search using ChromaDB's native document search.
    
    Args:
        query: Search query text
        n_results: Number of results to return
        collection: ChromaDB collection (uses default if None)
        filters: Raw ChromaDB where filters (dict)
        date_range: Date filtering with 'start' and/or 'end' keys
        include_metadata: Whether to include full metadata in results
        
    Returns:
        Dictionary with search results matching search() format
    """
    collection = collection or getDefaultCollection()
    
    # Build where clause from filters
    where_clause = _build_where_clause(
        filters=filters,
        date_range=date_range
    )
    
    # Use ChromaDB's document search with contains operator
    where_document = {"$contains": query}
    
    try:
        # Perform document-based search
        results = collection.get(
            where=where_clause if where_clause else None,
            where_document=where_document,
            limit=n_results,
            include=['documents', 'metadatas']
        )
        
        # Format results to match search() output
        # For full-text search, we don't have distance scores, so we'll use a placeholder
        formatted_results = {
            'query': query,
            'n_results': len(results['ids']),
            'documents': results['documents'],
            'distances': [0.5] * len(results['ids']),  # Placeholder distances for full-text
            'ids': results['ids']
        }
        
        if include_metadata:
            formatted_results['metadata'] = results['metadatas']
        
        return formatted_results
        
    except Exception as e:
        # Return empty results if search fails
        return {
            'query': query,
            'n_results': 0,
            'documents': [],
            'distances': [],
            'ids': [],
            'metadata': [] if include_metadata else None
        }


def search_by_date(
    query: str,
    days_back: int = 30,
    collection=None,
    n_results: int = 5,
    **kwargs
) -> Dict[str, Any]:
    """
    Search documents created within the last N days.
    
    Args:
        query: Search query text
        days_back: Number of days to look back
        collection: ChromaDB collection (uses default if None)
        n_results: Number of results to return
        **kwargs: Additional arguments passed to search()
        
    Returns:
        Dictionary with search results
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days_back)
    
    date_range = {
        'start': start_time,
        'end': end_time
    }
    
    return search(
        query=query,
        collection=collection,
        n_results=n_results,
        date_range=date_range,
        **kwargs
    )

def search_list(days=1, enhence=2, db=None):
    if not db:
        db = docdb()
    return list_to_search_result(
            db.list_latest(days=days),
            enhence=enhence)


def _build_where_clause(
    filters: Optional[Dict[str, Any]] = None,
    date_range: Optional[Dict[str, Union[str, datetime, int]]] = None
) -> Optional[Dict[str, Any]]:
    """
    Build ChromaDB where clause from filter options.
    
    Args:
        filters: Raw ChromaDB where filters
        date_range: Date filtering with 'start' and/or 'end' keys
        
    Returns:
        ChromaDB where clause or None if no filters
    """
    where_conditions = []
    
    # Add raw filters
    if filters:
        where_conditions.append(filters)
    
    # Add date range filtering
    if date_range:
        date_condition = _build_date_filter(date_range)
        if date_condition:
            where_conditions.append(date_condition)
    
    # Combine all conditions
    if not where_conditions:
        return None
    elif len(where_conditions) == 1:
        return where_conditions[0]
    else:
        return {"$and": where_conditions}


def _build_date_filter(date_range: Dict[str, Union[str, datetime, int]]) -> Optional[Dict[str, Any]]:
    """
    Build date filter using timestamp comparison.
    
    Args:
        date_range: Dict with 'start' and/or 'end' keys 
                   (datetime objects, timestamps, or date strings)
        
    Returns:
        ChromaDB date filter condition or None
    """
    conditions = []
    
    if 'start' in date_range:
        start_ts = convert_to_timestamp(date_range['start'])
        if start_ts is not None:
            conditions.append({"created_timestamp": {"$gte": start_ts}})
    
    if 'end' in date_range:
        end_ts = convert_to_timestamp(date_range['end'])
        if end_ts is not None:
            conditions.append({"created_timestamp": {"$lte": end_ts}})
    
    if not conditions:
        return None
    elif len(conditions) == 1:
        return conditions[0]
    else:
        return {"$and": conditions}