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

### mu2e-chat
LLM based chat interface to docdb (run `mu2e-chat --help` for help):
- starting an interactive mode (allowing threads) by typing `mu2e-chat` (CTRL-C to quit)
- single question mode: `mu2e-chat "\\rag What is the latest timeline?"`

### mu2e-slack
This commands runs a docdb chat with a slack interface. For more details see doc/slack.md.
