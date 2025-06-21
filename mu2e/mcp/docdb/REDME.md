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

### Default (OpenAI embeddings)
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

### Using Argo embeddings
```json
"docdb": {
    "command": "/path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server",
    "args": [
        "--dbname",
        "Mu2e",
        "--argo"
    ],
    "env": {
        "MU2E_DOCDB_USERNAME": "your_username",
        "MU2E_DOCDB_PASSWORD": "your_password"
    }
}
```

### Using Argo remote embeddings (via proxy)
```json
"docdb": {
    "command": "/path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server",
    "args": [
        "--dbname",
        "Mu2e",
        "--argo-remote"
    ],
    "env": {
        "MU2E_DOCDB_USERNAME": "your_username",
        "MU2E_DOCDB_PASSWORD": "your_password"
    }
}
```

## CLI Options

- `--dbname`: DocDB database name (default: Mu2e)
- `--argo`: Use Argo embeddings for larger context windows
- `--argo-remote`: Use Argo remote embeddings via SSH tunnel proxy

## Testing and Debugging

Use the MCP Inspector to test the server:

```bash
# Using uv (default embeddings)
npx @modelcontextprotocol/inspector uv run mu2e-mcp-server

# Using uv with Argo embeddings
npx @modelcontextprotocol/inspector uv run mu2e-mcp-server -- --argo

# Or directly via virtual environment
npx @modelcontextprotocol/inspector /path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server --argo-remote
```
