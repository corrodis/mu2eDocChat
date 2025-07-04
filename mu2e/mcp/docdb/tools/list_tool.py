"""List tool handler for MCP server."""

import json
from datetime import datetime
import mcp.types as types
from mu2e.search import search_list


async def handle_list_tool(arguments: dict, db) -> list[types.TextContent]:
    """Handle the list tool execution."""
    days = arguments.get("days")
    include_documents = bool(arguments.get("include_documents", True))
    if not days:
        raise ValueError("Missing parameter days")
    
    enhance = 2 if include_documents else 1

    results = search_list(days, enhence=enhance, db=db)
    
    # Format results for LLM consumption (same as search tools)
    response_text = f"<search_results query='list' type='list' count='{results['n_results']}'>\n"
    
    for i, (doc_text, distance, doc_id, metadata) in enumerate(zip(
        results['documents'], results['distances'], results['ids'], results['metadata']
    )):
        response_text += (
            f"<document rank='{i+1}' "
            f"docid='{metadata.get('docid', 'N/A')}' "
            f"title='{metadata.get('title', 'N/A')}' "
            f"created='{metadata.get('created', 'N/A')}' "
            f"revised='{metadata.get('revised_content', 'N/A')}' "
            f"abstract='{metadata.get('abstract', 'N/A')}' "
            f"link='{metadata.get('link', 'N/A')}'>\n"
            f"{doc_text}\n"
            f"</document>\n"
        )
    
    response_text += "</search_results>"
    return [types.TextContent(type="text", text=response_text)]