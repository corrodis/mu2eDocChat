"""DocDB search tool handler for MCP server."""

import json
from datetime import datetime
import mcp.types as types


async def handle_docdb_search_tool(arguments: dict, db) -> list[types.TextContent]:
    """Handle the docdb_search tool execution."""
    query = arguments.get("query")
    before = datetime.strptime(arguments["before"], "%Y-%m-%d") if arguments.get("before") else None
    after = datetime.strptime(arguments["after"], "%Y-%m-%d") if arguments.get("after") else None
    
    document = db.search(query, before, after)
    
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)
    
    formatted_text = json.dumps(document, indent=4, cls=DateTimeEncoder)
    return [types.TextContent(type="text", text=formatted_text)]