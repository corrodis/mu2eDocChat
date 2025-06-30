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

# Import modular components
from mu2e.mcp.docdb.tools import (
    handle_list_tool,
    handle_get_tool,
    handle_search_tool,
    handle_fulltext_search_tool,
    handle_docdb_search_tool
)
from mu2e.mcp.docdb.resources import (
    get_metadata_schema,
    get_mu2e_overview,
    get_experiment_conditions
)

# Initialize with default values
DEFAULT_DBNAME = "Mu2e"
dbname = DEFAULT_DBNAME

server = Server("docdb")
db = None  # Will be initialized in setup_server
collection = None  # Will be initialized based on args

def setup_server(db_name: str = DEFAULT_DBNAME, use_argo: bool = False, use_argo_remote: bool = False):
    """Initialize the server with given configuration."""
    global dbname, db, collection
    dbname = db_name
    
    # Set up collection based on arguments
    if use_argo_remote:
        collection = anl.get_collection(url="http://localhost:55019/v1/embed")
        print(f"Using Argo-Remote collection for {dbname}")
    elif use_argo:
        collection = anl.get_collection()
        print(f"Using Argo collection for {dbname}")
    else:
        collection = None
        print(f"Using default collection for {dbname}")
    
    db = mu2e.docdb(login=True, collection=collection)
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
        return await handle_list_tool(arguments, db)
    elif name == "get":
        return await handle_get_tool(arguments, db)
    elif name == "search":
        return await handle_search_tool(arguments, collection)
    elif name == "fulltext_search":
        return await handle_fulltext_search_tool(arguments, collection)
    elif name == "docdb_search":
        return await handle_docdb_search_tool(arguments, db)
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
        return get_mu2e_overview()
    elif str(uri) == "file:///experiment/conditions":
        return get_experiment_conditions()
    elif str(uri) == "file:///schema/metadata":
        return get_metadata_schema()
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

async def main_async(db_name: str = DEFAULT_DBNAME, use_argo: bool = False, use_argo_remote: bool = False):
    """Async main entry point."""
    setup_server(db_name, use_argo, use_argo_remote)
    #print("DEBUG: db_name", os.environ['MU2E_DOCDB_USERNAME'])
    await run_server()

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description='Run the Mu2e DocDB MCP server')
    parser.add_argument('--dbname', default=DEFAULT_DBNAME,
                      help=f'DocDB database name (default: {DEFAULT_DBNAME})')
    parser.add_argument('--argo', action='store_true',
                      help='Use Argo embeddings')
    parser.add_argument('--argo-remote', action='store_true',
                      help='Use Argo remote embeddings via proxy')
    args = parser.parse_args()
    asyncio.run(main_async(args.dbname, args.argo, args.argo_remote))

if __name__ == "__main__":
    main()