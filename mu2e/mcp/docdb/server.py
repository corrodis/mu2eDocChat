from typing import Any
import asyncio
import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import json
import mu2e
from mu2e import search, tools, anl
from datetime import datetime
import os
import threading
import argparse

# Initialize with default values
DEFAULT_DBNAME = "Mu2e"
dbname = DEFAULT_DBNAME

server = Server("docdb")
db = None  # Will be initialized in setup_server

def setup_server(db_name: str = DEFAULT_DBNAME):
    """Initialize the server with given configuration."""
    global dbname, db
    dbname = db_name
    db = mu2e.docdb(login=True)
    return server

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="list",
            description=f"List all document of the last n days from the {dbname} docdb.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "number",
                        "description": "Number of the last n days from which documents are returned.",
                    },
                },
                "required": ["days"],
            },
        ),
        types.Tool(
            name="get",
            description=f"Get the content of a document from the {dbname} docdb by its docid",
            inputSchema={
                "type": "object",
                "properties": {
                    "docid": {
                        "type": "string",
                        "description": "Document id of the document which content is retrieved.",
                    },
                },
                "required": ["docid"],
            },
        ),
        types.Tool(
            name="search",
            description=f"Find relevant documents in the {dbname} database using semantic similarity. Best for conceptual queries and finding related content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search for semantically similar content.",
                    },
                    "n_results": { 
                        "type": "number", 
                        "default": 5, 
                        "description": "Maximum number of documents to retrieve."
                    },
                    "days": {
                        "type": "number",
                        "description": "Optional: Limit search to documents from last N days."
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional: Advanced ChromaDB filters. See file:///schema/metadata resource for available fields and filter examples."
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="fulltext_search",
            description=f"Search for specific keywords or phrases in {dbname} documents. Best for finding exact terms, names, or technical details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or phrases to search for in document text.",
                    },
                    "n_results": { 
                        "type": "number", 
                        "default": 5, 
                        "description": "Maximum number of documents to retrieve."
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional: Advanced ChromaDB filters. See file:///schema/metadata resource for available fields and filter examples."
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="docdb_search",
            description=f"Search the {dbname} docdb using title, abstracts and keyword fields (AND between all words).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query with the word that are search in an AND mode in title, abstract, and keyword fields.",
                    },
                    "before": { 
                        "type": "string", 
                        "description": "Date string in the format YYYY-MM-DD to search for entries before that date."
                    },
                    "after": { 
                        "type": "string", 
                        "description": "Date string in the format YYYY-MM-DD to search for entries after that date."
                    },
                },
                "required": ["query"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if not arguments:
        raise ValueError("Missing arguments")
  
    if name == "list":
        days = arguments.get("days")
        if not days:
            raise ValueError("Missing parameter days")
        document = db.list_latest(days)
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
        formated_text = json.dumps(document, indent=4, cls=DateTimeEncoder)
        return [types.TextContent(type="text", text=formated_text)]

    elif name == "get":
        docid = arguments.get("docid")
        # check if we have this docid already cached
        doc = mu2e.tools.load("mu2e-docdb-"+str(docid), nodb=True)
        if doc is None:
            # get it straight from docdb
            doc = db.get(docid)
            if doc:
                db.parse_files(doc)
                threading.Thread(target=db.save, args=(doc,), daemon=True).start()
        if doc:
            doc_filtered = doc.copy()
            doc_filtered['files'] = [{k: v for k, v in f.items() if k != "document"} for f in doc_filtered['files']]
            formated_text = json.dumps(doc_filtered, indent=4)
        else:
            formated_text = f"Docdb {docid} doesn't seem to exist."
        return [types.TextContent(type="text", text=formated_text)]

    elif name == "docdb_search":
        query = arguments.get("query")
        before = datetime.strptime(arguments["before"], "%Y-%m-%d") if arguments.get("before") else None
        after = datetime.strptime(arguments["after"], "%Y-%m-%d") if arguments.get("after") else None
        document = db.search(query, before, after)
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
        formated_text = json.dumps(document, indent=4, cls=DateTimeEncoder)
        return [types.TextContent(type="text", text=formated_text)]

    elif name == "search":
        query = arguments.get("query")
        n_results = arguments.get("n_results", 5)
        days = arguments.get("days")
        filters = arguments.get("filters")
        
        # Perform search based on parameters
        if days:
            results = search.search_by_date(query, days_back=days, n_results=n_results, filters=filters)
        else:
            results = search.search(query, n_results=n_results, filters=filters)
        
        # Format results for LLM consumption
        response_text = f"<search_results query='{query}' type='vector' count='{results['n_results']}'>\n"
        
        for i, (doc_text, distance, doc_id, metadata) in enumerate(zip(
            results['documents'], results['distances'], results['ids'], results['metadata']
        )):
            response_text += (
                f"<document rank='{i+1}' "
                f"distance='{distance:.3f}' "
                f"docid='{metadata.get('docid', 'N/A')}' "
                f"title='{metadata.get('title', 'N/A')}' "
                f"date='{metadata.get('created', 'N/A')}' "
                f"link='{metadata.get('link', 'N/A')}'>\n"
                f"<chunk>{doc_text}</chunk>\n"
                f"</document>\n"
            )
        
        response_text += "</search_results>"
        return [types.TextContent(type="text", text=response_text)]
    
    elif name == "fulltext_search":
        query = arguments.get("query")
        n_results = arguments.get("n_results", 5)
        filters = arguments.get("filters")
        
        results = search.search_fulltext(query, n_results=n_results, filters=filters)
        
        # Format results for LLM consumption
        response_text = f"<search_results query='{query}' type='fulltext' count='{results['n_results']}'>\n"
        
        for i, (doc_text, distance, doc_id, metadata) in enumerate(zip(
            results['documents'], results['distances'], results['ids'], results['metadata']
        )):
            response_text += (
                f"<document rank='{i+1}' "
                f"docid='{metadata.get('docid', 'N/A')}' "
                f"title='{metadata.get('title', 'N/A')}' "
                f"date='{metadata.get('created', 'N/A')}' "
                f"link='{metadata.get('link', 'N/A')}'>\n"
                f"<chunk>{doc_text}</chunk>\n"
                f"</document>\n"
            )
        
        response_text += "</search_results>"
        return [types.TextContent(type="text", text=response_text)]

    else:
        raise ValueError(f"Unknown tool: {name}")

@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="file:///overview/mu2e",
            name="Mu2e Overview",
            description="This gives a general overview of the details of the mu2e experiment.",
            mimeType="text/plain"
        ),
        types.Resource(
            uri="file:///experiment/conditions",
            name="Current experiment conditions",
            mimeType="text/plain"
        ),
        types.Resource(
            uri="file:///schema/metadata",
            name="Document Metadata Schema",
            description="Available metadata fields for filtering in vector_search and fulltext_search. Use this to understand what fields you can filter on.",
            mimeType="application/json"
        ),
    ]

@server.read_resource()
async def read_resource(uri: types.AnyUrl) -> str:
    """Read a resource by URI."""
    if str(uri) == "file:///overview/mu2e":
        return "Mu2e is an awesome experiment." + os.environ['MU2E_DOCDB_USERNAME']
    elif str(uri) == "file:///experiment/conditions":
        return {
            "experiment": {
                "status": "construction",
                "mood": "good",
                "pwd": os.getcwd()
            }
        }
    elif str(uri) == "file:///schema/metadata":
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
    raise ValueError("Resource not found")

async def run_server(server_name: str = "docdb", server_version: str = "0.1.0"):
    """Run the server with the given configuration."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=server_name,
                server_version=server_version,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )
        )

async def main_async(db_name: str = DEFAULT_DBNAME):
    """Async main entry point."""
    setup_server(db_name)
    #print("DEBUG: db_name", os.environ['MU2E_DOCDB_USERNAME'])
    await run_server()

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description='Run the Mu2e DocDB MCP server')
    parser.add_argument('--dbname', default=DEFAULT_DBNAME,
                      help=f'DocDB database name (default: {DEFAULT_DBNAME})')
    args = parser.parse_args()
    asyncio.run(main_async(args.dbname))

if __name__ == "__main__":
    main()
