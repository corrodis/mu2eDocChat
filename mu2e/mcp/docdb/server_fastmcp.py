"""FastMCP-based Mu2e DocDB Server."""

from typing import Any, AsyncIterator, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass
import argparse
import json

from mcp.server.fastmcp import FastMCP
from pydantic import Field
import mu2e
from mu2e import anl
from mu2e.mcp.docdb.resources import (
    get_metadata_schema,
    get_mu2e_overview,
    get_experiment_conditions
)

# Configuration
DEFAULT_DBNAME = "Mu2e"
ARGO_REMOTE_URL = "http://localhost:55019/v1/embed"


@dataclass
class AppContext:
    """Application context with database connections."""
    db: Any
    collection: Any
    dbname: str


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle and database connections."""
    # Get configuration from server context (set during initialization)
    config = getattr(server, '_config', {})
    dbname = config.get('dbname', DEFAULT_DBNAME)
    use_argo = config.get('use_argo', False)
    use_argo_remote = config.get('use_argo_remote', False)
    
    # Set up collection based on arguments
    if use_argo_remote:
        collection = anl.get_collection(url=ARGO_REMOTE_URL)
        # Use stderr to avoid corrupting stdio protocol
        import sys
        print(f"Using Argo-Remote collection for {dbname}", file=sys.stderr)
    elif use_argo:
        collection = anl.get_collection()
        import sys
        print(f"Using Argo collection for {dbname}", file=sys.stderr)
    else:
        collection = None
        import sys
        print(f"Using default collection for {dbname}", file=sys.stderr)
    
    # Initialize database connection
    #db = mu2e.docdb(login=True, collection=collection)
    db = None
    
    try:
        yield AppContext(db=db, collection=collection, dbname=dbname)
    finally:
        # Cleanup would go here if needed
        pass

def get_db():
    app_context = get_app_context()
    if app_context.db is None:
        print("log into docdb")
        app_context.db = mu2e.docdb(login=True, collection=app_context.collection)
    return app_context.db

# Initialize FastMCP server
mcp = FastMCP("docdb", lifespan=app_lifespan)


def get_app_context() -> AppContext:
    """Helper function to get the application context from FastMCP."""
    ctx = mcp.get_context()
    return ctx.request_context.lifespan_context


@mcp.tool()
async def list(
    days: int = Field(description="Number of the last n days from which documents are returned.")
) -> str:
    """List all documents from the last n days from the docdb."""
    from mu2e.mcp.docdb.tools.list_tool import handle_list_tool
    
    arguments = {"days": days}
    results = await handle_list_tool(arguments, get_db())
    return results[0].text


@mcp.tool()
async def get(
    docid: str = Field(description="Document id of the document which content is retrieved.")
) -> str:
    """Get the content of a document from the docdb by its docid."""
    from mu2e.mcp.docdb.tools.get_tool import handle_get_tool
    
    arguments = {"docid": docid}
    results = await handle_get_tool(arguments, get_app_context().db)
    return results[0].text


@mcp.tool()
async def search(
    query: str = Field(description="The query to search for semantically similar content."),
    n_results: int = Field(description="Maximum number of documents to retrieve.", default=5),
    days: Optional[int] = Field(description="Limit search to documents from last N days.", default=None),
    filters: Optional[dict] = Field(description="Advanced ChromaDB filters. See file:///schema/metadata resource for available fields and filter examples.", default=None)
) -> str:
    """Find relevant documents using semantic similarity. Best for conceptual queries."""
    from mu2e.mcp.docdb.tools.search_tool import handle_search_tool
    
    arguments = {
        "query": query,
        "n_results": n_results,
        "days": days,
        "filters": filters
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}
    
    results = await handle_search_tool(arguments, get_app_context().collection)
    return results[0].text


@mcp.tool()
async def fulltext_search(
    query: str = Field(description="Keywords or phrases to search for in document text."),
    n_results: int = Field(description="Maximum number of documents to retrieve.", default=5),
    filters: Optional[dict] = Field(description="Advanced ChromaDB filters. See file:///schema/metadata resource for available fields and filter examples.", default=None)
) -> str:
    """Search for specific keywords or phrases in documents. Best for finding exact terms."""
    from mu2e.mcp.docdb.tools.fulltext_search_tool import handle_fulltext_search_tool
    
    arguments = {
        "query": query,
        "n_results": n_results,
        "filters": filters
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}
    
    results = await handle_fulltext_search_tool(arguments, get_app_context().collection)
    return results[0].text


@mcp.tool()
async def docdb_search(
    query: str = Field(description="The query with the word that are search in an AND mode in title, abstract, and keyword fields."),
    before: Optional[str] = Field(description="Date string in the format YYYY-MM-DD to search for entries before that date.", default=None),
    after: Optional[str] = Field(description="Date string in the format YYYY-MM-DD to search for entries after that date.", default=None)
) -> str:
    """Search the docdb using title, abstracts and keyword fields (AND between all words)."""
    from mu2e.mcp.docdb.tools.docdb_search_tool import handle_docdb_search_tool
    
    arguments = {
        "query": query,
        "before": before,
        "after": after
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}
    

    results = await handle_docdb_search_tool(arguments, get_db())
    return results[0].text


@mcp.resource("file:///overview/mu2e")
def mu2e_overview() -> str:
    """General overview of the details of the mu2e experiment."""
    return get_mu2e_overview()


@mcp.resource("file:///experiment/conditions")
def experiment_conditions() -> str:
    """Current experiment conditions."""
    return get_experiment_conditions()


@mcp.resource("file:///schema/metadata")
def metadata_schema() -> str:
    """Document Metadata Schema - Available metadata fields for filtering in searches."""
    return get_metadata_schema()


def setup_server_config(dbname: str = DEFAULT_DBNAME, use_argo: bool = False, use_argo_remote: bool = False):
    """Set server configuration for lifespan context."""
    mcp._config = {
        'dbname': dbname,
        'use_argo': use_argo,
        'use_argo_remote': use_argo_remote
    }


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description='Run the Mu2e DocDB FastMCP server')
    parser.add_argument('--dbname', default=DEFAULT_DBNAME,
                      help=f'DocDB database name (default: {DEFAULT_DBNAME})')
    parser.add_argument('--argo', action='store_true',
                      help='Use Argo embeddings')
    parser.add_argument('--argo-remote', action='store_true',
                      help='Use Argo remote embeddings via proxy')
    parser.add_argument('--port', type=int,
                      help='Run as HTTP server on specified port (default: stdio for MCP clients)')
    args = parser.parse_args()
    
    # Configure server before running
    setup_server_config(args.dbname, args.argo, args.argo_remote)
    
    if args.port:
        # HTTP streamable transport - prints are safe here
        print(f"Starting FastMCP server on HTTP port {args.port}")
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        # Default stdio transport for MCP clients - NO PRINTS (corrupts protocol)
        mcp.run()


if __name__ == "__main__":
    main()