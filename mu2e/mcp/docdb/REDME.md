# Mu2e DocDB MCP Server

Model Context Protocol (MCP) server for Mu2e document database integration.

## Tools Available

- `search` - Semantic search using embeddings (and metadata through filters)
- `fulltext_search` - Keyword search in document text  
- `docdb_search` - DocDB search by metadata fields (legacy docdb search)
- `list` - List recent documents
- `get` - Retrieve specific document by ID

## Setup for Desktop

Add to your MCP settings:

```json
"docdb": {
    "command": "/path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server",
    "args": [
        "--dbname",
        "Mu2e"
    ],
    "env": {
        "MU2E_DOCDB_USERNAME": "your_username",
        "MU2E_DOCDB_PASSWORD": "your_password"
    }
}
```

## Testing and Debugging

Use the MCP Inspector to test the server:

```bash
# Using uv
npx @modelcontextprotocol/inspector uv run mu2e-mcp-server

# Or directly via virtual environment
npx @modelcontextprotocol/inspector /path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server
```
