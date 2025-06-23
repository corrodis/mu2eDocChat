"""Metadata schema resource for MCP server."""

import json


def get_metadata_schema() -> str:
    """Get the metadata schema for ChromaDB filtering."""
    schema = {
        "description": "Metadata fields available for filtering in ChromaDB searches",
        "fields": {
            # Document identification
            "docid": {
                "type": "integer",
                "description": "Numeric document ID (e.g., 53181)",
                "example_filter": '{"docid": {"$gte": 50000}}'
            },
            "doc_id": {
                "type": "string", 
                "description": "Full document identifier (e.g., 'mu2e-docdb-53181')",
                "example_filter": '{"doc_id": {"$in": ["mu2e-docdb-53181", "mu2e-docdb-53182"]}}'
            },
            "docid_str": {
                "type": "string",
                "description": "Formatted document string (e.g., 'Mu2e-doc-53181-v2')"
            },
            "doc_type": {
                "type": "string",
                "description": "Document type, typically 'mu2e-docdb'",
                "example_filter": '{"doc_type": "mu2e-docdb"}'
            },
            
            # Document content
            "title": {
                "type": "string",
                "description": "Document title",
                "example_filter": '{"title": {"$contains": "timeline"}}'
            },
            "abstract": {
                "type": "string", 
                "description": "Document abstract/summary",
                "example_filter": '{"abstract": {"$contains": "detector"}}'
            },
            "topics": {
                "type": "string",
                "description": "Document topics/categories (comma-separated)"
            },
            
            # File information
            "filename": {
                "type": "string",
                "description": "Original filename",
                "example_filter": '{"filename": {"$contains": ".pdf"}}'
            },
            "type": {
                "type": "string",
                "description": "File type (pdf, ppt, etc.)",
                "example_filter": '{"type": "pdf"}'
            },
            "version": {
                "type": "integer",
                "description": "Document version number",
                "example_filter": '{"version": {"$gte": 2}}'
            },
            "link": {
                "type": "string",
                "description": "URL to download the document"
            },
            
            # Dates and timestamps
            "created": {
                "type": "string",
                "description": "Creation date in format '20 Jun 2025, 02:03'"
            },
            "created_timestamp": {
                "type": "integer",
                "description": "Unix timestamp for creation date - use this for date filtering",
                "example_filter": '{"created_timestamp": {"$gte": 1735689600}}'
            },
            "revised_content": {
                "type": "string", 
                "description": "Last revision date in format '20 Jun 2025, 02:04'"
            },
            "revised_timestamp": {
                "type": "integer",
                "description": "Unix timestamp for revision date - use this for date filtering"
            },
            "revised_meta": {
                "type": "string",
                "description": "Metadata revision date"
            },
            
            # Chunking information (technical details)
            "chunk_id": {
                "type": "integer",
                "description": "Chunk index within document (0-based)"
            },
            "total_chunks": {
                "type": "integer", 
                "description": "Total number of chunks in document"
            },
            "file_index": {
                "type": "integer",
                "description": "File index within document (for multi-file docs)"
            },
            "chunk_size": {
                "type": "integer",
                "description": "Size of text chunks in tokens"
            },
            "chunk_overlap": {
                "type": "integer",
                "description": "Overlap between chunks in tokens"
            },
            "chunking_strategy": {
                "type": "string",
                "description": "Strategy used for text chunking (default, semantic, etc.)"
            }
        },
        "filter_examples": {
            "recent_documents": '{"created_timestamp": {"$gte": 1735689600}}',
            "pdf_files": '{"type": "pdf"}',
            "high_docid": '{"docid": {"$gte": 50000}}',
            "multiple_conditions": '{"$and": [{"type": "pdf"}, {"docid": {"$gte": 50000}}]}',
            "title_contains": '{"title": {"$contains": "detector"}}'
        }
    }
    return json.dumps(schema, indent=2)