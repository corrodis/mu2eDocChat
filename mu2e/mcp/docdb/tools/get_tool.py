"""Get tool handler for MCP server."""

import json
import threading
import mcp.types as types
import mu2e.tools


async def handle_get_tool(arguments: dict, db, collection) -> list[types.TextContent]:
    """Handle the get tool execution."""
    docid = arguments.get("docid")
    
    # Check if we have this docid already cached
    doc = mu2e.tools.load2("mu2e-docdb-"+str(docid), nodb=True, collection=collection)
    if doc is None:
        # Get it straight from docdb
        doc = db.get_and_parse(docid)
     
    if doc:
        doc_filtered = doc.copy()
        doc_filtered['files'] = [{k: v for k, v in f.items() if k != "document"} for f in doc_filtered['files']]
        formatted_text = json.dumps(doc_filtered, indent=4)
    else:
        formatted_text = f"Docdb {docid} doesn't seem to exist."
    
    return [types.TextContent(type="text", text=formatted_text)]