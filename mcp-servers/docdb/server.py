from typing import Any
import asyncio
import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import json
import mu2e
from datetime import datetime

server = Server("docdb")
db = mu2e.docdb(login=True)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        types.Tool(
            name="list",
            description=f"List all document of the last n days from the {global_dbname} docdb.",
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
            description=f"Get the content of a document from the {global_dbname} docdb by its docid",
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
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can fetch weather data and notify clients of changes.
    """
    if not arguments:
        raise ValueError("Missing arguments")
  
    if name == "list":
        n = arguments.get("days")
        if not n:
            raise ValueError("Missing parameter days")
        else:
            document = db.list_latest()
            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return super().default(obj)
            formated_text = json.dumps(document, indent=4, cls=DateTimeEncoder)

            return [
                types.TextContent(
                type="text",
                text=formated_text
                )]
    elif name == "get":
        docid = arguments.get("docid")

        # get it streight from docdb
        doc = db.get(docid) # get it from docdb
        if doc:
            db.parse_files(doc) # parse it
            # remove the actual file 
            doc_filtered = doc.copy()
            doc_filtered['files'] = [{k: v for k, v in f.items() if k != "document"} for f in doc_filtered['files']]
            formated_text = json.dumps(doc_filtered, indent=4)
        else:
            formated_text = f"Docdb {docid} doesn't seem to exist."
        return [
            types.TextContent(
            type="text",
            text=formated_text
        )]

    else:
        raise ValueError(f"Unknown tool: {name}")

@server.list_resources()
async def list_resources() -> list[types.Resource]:
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
    if str(uri) == "file:///overview/mu2e":
        overview = "Mu2e is an owesome experiment." # await get_overview() # TOOD
        return overview
    elif str(uri) == "file:///experiment/conditions":
        return " {'experiment': {'status':'construction',\
                                 'mood':'good'}" 
    raise ValueError("Resource not found")

async def main():
    global global_dbname
    global_dbname = dbname  # Set the global dbname
    #print("Start the docdb mcp server")
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="docdb",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )
        )

# This is needed if you'd like to connect to a custom client
if __name__ == "__main__":
    dbname = "Mu2e"
    asyncio.run(main())
