# Mu2e Docdb Interface

A Python interface to the Mu2e docdb with support for document retrieval, vector search, and LLM chat interface.

## Setup
For installation and setup instructions see here: doc/install.md

## Command Line Interface
### mu2e-docdb
The package provides a command-line tool `mu2e-docdb` with the following commands (just run `mu2e-docdb` for help):
- List documents from the last day `mu2e-docdb list`
- Generate embeddings for vector search: `mu2e-docdb generate --days 10`
- Vector search to retrieve relevant documents: `mu2e-docdb search "mu2e timeline"`
- Full-text keyword search: `mu2e-docdb search "timeline" --fulltext`
- Use Argo embeddings: `mu2e-docdb --argo search "detector design"`
See [doc/docdb.md](doc/docdb.md) for more details.

### mu2e-chat
LLM based chat interface to docdb (run `mu2e-chat --help` for help):
- starting an interactive mode (allowing threads) by typing `mu2e-chat` (CTRL-C to quit)
- single question mode: `mu2e-chat "\\rag What is the latest timeline?"`

### mu2e-slack
This commands runs a docdb chat with a slack interface. For more details see [doc/slack.md](doc/slack.md).

### mu2e-mcp-server
Model Context Protocol (MCP) server for integration with Claude Desktop and other MCP-compatible AI assistants. Provides vector search, full-text search, and document retrieval tools. See [mu2e/mcp/docdb/REDME.md](mu2e/mcp/docdb/REDME.md) for setup instructions.

### mu2e-web
Web interface providing document search, chat, and document lookup through a browser. Run with `mu2e-web` and access at http://localhost:5000. See [doc/web.md](doc/web.md) for details.
