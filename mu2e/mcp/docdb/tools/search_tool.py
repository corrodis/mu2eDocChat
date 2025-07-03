"""Search tool handler for MCP server."""

import mcp.types as types
from mu2e import search


async def handle_search_tool(arguments: dict, collection) -> list[types.TextContent]:
    """Handle the search tool execution."""
    query = arguments.get("query")
    n_results = arguments.get("n_results", 5)
    days = arguments.get("days")
    filters = arguments.get("filters")
    
    # Perform search based on parameters
    if days:
        results = search.search_by_date(query, days_back=days, n_results=n_results, filters=filters, collection=collection)
    else:
        results = search.search(query, n_results=n_results, filters=filters, collection=collection)
    
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
            f"{doc_text}\n"
            f"</document>\n"
        )
    
    response_text += "</search_results>"
    return [types.TextContent(type="text", text=response_text)]