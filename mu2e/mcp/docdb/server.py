from typing import Any
import asyncio
import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import json
import mu2e
from mu2e import rag
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
            name="rag",
            description=f"Performs retrival from the {dbname} docdb using the provided query based on RAG. Only cached documents are used though.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to perform retrieval on.",
                    },
                    "n": { 
                        "type": "number", 
                        "default": 3, 
                        "description": "Maximal number of results to retrieve."
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search",
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

    elif name == "search":
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

    elif name == "rag":
        query = arguments.get("query")
        n = arguments.get("n", 10)
        rag_sim, rag_docs = mu2e.rag.find(query)
        rag_string = f"n={n}<documents>"
        for j, docid in enumerate(rag_docs):
            if j >= n:
                break
            doc_ = mu2e.tools.load(docid)
            doc_type, doc_id = docid.rsplit('-', 1)
            rag_string += (
                f"<document date='{doc_['revised_content']}' "
                f"title='{doc_['title']}' "
                f"score='{rag_sim[j]}' "
                f"link=https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid='{docid}' "
                f"docid='{docid}'>"
            )
            for d in doc_['files']:
                rag_string += (
                    f"<file filename='{d['filename']}' name='{d['filename']}'>"
                    f"{d['text']}</file>"
                )
            rag_string += "</document>"
        rag_string += "</documents>"
        return [types.TextContent(type="text", text=rag_string)]

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
    print("DEBUG: db_name", os.environ['MU2E_DOCDB_USERNAME'])
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
