"""List tool handler for MCP server."""

import json
from datetime import datetime
import mcp.types as types


async def handle_list_tool(arguments: dict, db) -> list[types.TextContent]:
    """Handle the list tool execution."""
    days = arguments.get("days")
    if not days:
        raise ValueError("Missing parameter days")
    
    document = db.list_latest(days)
    
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)
    
    formatted_text = json.dumps(document, indent=4, cls=DateTimeEncoder)
    return [types.TextContent(type="text", text=formatted_text)]