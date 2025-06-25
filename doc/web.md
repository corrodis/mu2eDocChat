# Web Interface

Browser-based interface for Mu2e document search and chat.

## Quick Start

```bash
mu2e-web
mu2e-web --port 5000  # custom port
```

Access at http://localhost:5000 (or specified port)

## Pages

- `/search` - Search documents with AI summaries
- `/chat` - Chat interface with markdown support  
- `/document` - Lookup specific documents by ID

## Requirements

- MCP server running on port 1223 (default)
- Settings from .env/environment variables