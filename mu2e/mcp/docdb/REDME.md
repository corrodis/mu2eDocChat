# Mu2e DocDB MCP Server

Model Context Protocol (MCP) server for Mu2e document database integration.

## Tools Available

- `search` - Semantic search using embeddings (and metadata through filters)
- `fulltext_search` - Keyword search in document text  
- `docdb_search` - DocDB search by metadata fields (legacy docdb search)
- `list` - List recent documents
- `get` - Retrieve specific document by ID

## Integration with AI IDEs

### Cursor IDE (Quick Install)
[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=docdb&config=eyJjb21tYW5kIjoiL3BhdGgvdG8vbXUyZURvY0NoYXQvLnZlbnYvYmluL211MmUtbWNwLXNlcnZlciAtLWRibmFtZSBNdTJlIiwiZW52Ijp7Ik1VMkVfRE9DREJfVVNFUk5BTUUiOiJ5b3VyX3VzZXJuYW1lIiwiTVUyRV9ET0NEQl9QQVNTV09SRCI6InlvdXJfcGFzc3dvcmQifX0%3D)

### VS Code Copilot

The server can be used with VS Code Copilot via HTTP transport. See the [official documentation](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for setup instructions.

### HTTP Transport (if you run the server independently)
Add this configuration to your VS Code settings:

```json
"mcp": {
    "servers": {
        "docdb": {
            "url": "http://localhost:1223/mcp/"
        }
    }
}
```

**Prerequisites:**
1. Start the MCP server in HTTP mode: `mu2e-mcp-server --port 1223 --dbname Mu2e --argo`
2. Ensure the server is running before using Copilot chat features

### Stdio Transport (Alternative)
You can also use the stdio transport with command-line configuration:

```json
"mcp": {
    "servers": {
        "docdb": {
            "command": "/path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server",
            "args": ["--dbname", "Mu2e", "--argo"],
            "env": {
                "MU2E_DOCDB_USERNAME": "your_username",
                "MU2E_DOCDB_PASSWORD": "your_password"
            }
        }
    }
}
```

## Setup for Claude Desktop

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

### MCP Inspector (stdio transport)
Use the MCP Inspector to test the server:

```bash
# Using uv (default embeddings)
npx @modelcontextprotocol/inspector uv run mu2e-mcp-server

# Using uv with Argo embeddings
npx @modelcontextprotocol/inspector uv run mu2e-mcp-server -- --argo

# Or directly via virtual environment
npx @modelcontextprotocol/inspector /path/to/mu2eDocChat/.venv/bin/mu2e-mcp-server --argo-remote
```

### HTTP Transport Testing

Start the server in HTTP mode:
```bash
mu2e-mcp-server --port 1223 --dbname Mu2e --argo
```

Initialize the MCP connection:
```bash
curl -i -X POST http://localhost:1223/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "curl-client",
        "version": "1.0.0"
      }
    }
  }'
```

**Note:** The response will include an `Mcp-Session-Id` header (e.g., `318cd5d1749d433699de1ede18f0772f`). Use this session ID in all subsequent requests.

List available tools:
```bash
curl -X POST http://localhost:1223/mcp/ \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: 318cd5d1749d433699de1ede18f0772f" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```
