# Chat Interface

The Mu2e chat interface provides an AI-powered conversational assistant with access to the document database through MCP (Model Context Protocol) tools.

## Environment Configuration

Configure the chat using environment variables (create a `.env` file in your project root):

```bash
# Chat-specific configuration
MU2E_CHAT_BASE_URL=http://localhost:55019/v1    # OpenAI API compatible endpoint
MU2E_CHAT_MODEL=argo:gpt-4o                     # Model name 
MU2E_CHAT_API_KEY=your-api-key-here             # API key
MU2E_CHAT_MCP_URL=http://localhost:1223/mcp/    # MCP server URL

# Fallback (for compatibility)
OPENAI_API_KEY=your-api-key-here
```

## Health Check

Before using the chat, check that all services are running:

```bash
mu2e-chat --health
```

This will show you the status of:
- OpenAI API endpoint (your LLM service)
- MCP server (document search tools)

If services are down, the command provides instructions on how to start them.

## Command Line Usage

### Interactive Mode
Start a conversation that maintains context across questions:

```bash
mu2e-chat
```

Example session:
```
Mu2e docdb chat (Ctrl+C to exit)
Ask questions about Mu2e documents, procedures, or analysis

Chat: What are the latest documents about the tracker?
USING TOOL: search with {'query': 'tracker', 'n_results': 5, 'days': 30}
