# Chat Interface

For the chat interface, if openAI or Anthropic APIs are used (vs Argo), corresponding API keys need to be set in the environment:
- ANTHROPIC_API_KEY
- OPENAI_API_KEY

## Quick Start
```python
from mu2e.chat import chat

# Initialize the chat with Anthropic's Claude (default)
agent = chat(api="antropic")

# Ask a simple question
# this doesn't use any internal infos
response = agent("What are the main subsystems of the Mu2e experiment?")
print(response)


# Use RAG to get information from documents
response = agent("\\rag What is the latest status of the tracker?")
print(response)

# You can specify a different model
response = agent("\\rag \\model=sonnet Tell me about the calorimeter design")
print(response)

# You can also directly reference a specific document
response = agent("\\mu2e-docdb-51478 What does this document say about the CRV?")
print(response)
```

## List of arguments
```
from mu2e.chat import InputParser

InputParser.list_commands(print_help=True)

>>> Available Commands for Mu2e Chat:
>>> ========================================
>>> 
>>> \model=<name>
>>>   Select LLM model to use
>>>   Examples: \model=sonnet, \model=haiku, \model=4o-mini
>>>   Available values:
>>>     Anthropic: sonnet, haiku, opus
>>>     OpenAI: 4o-mini, 4o, o1-mini, o1-preview
>>>     Argo: argo-4o, argo-o1
>>> 
>>> \rag
>>>   Enable RAG (Retrieval Augmented Generation)
>>>   Example: \rag What is the latest status of the tracker?
>>> 
>>> \mu2e-docdb-<number>
>>>   Reference specific DocDB document
>>>   Example: \mu2e-docdb-51478 What does this document say?
>>> 
>>> \temperature=<value>
>>>   Set temperature for LLM response (0.0-1.0)
>>>   Example: \temperature=0.7
>>> 
>>> \print-settings
>>>   Show current settings in response
>>> 
>>> ========================================
```

## Chat with follow up questions
```python
from mu2e.chat import chat

# Initialize the chat
agent = chat()

# First question
response = agent("What are the main subsystems of the Mu2e experiment?")
print("First response:", response)

# Follow-up question - no need to reference previous context
response = agent("Tell me more about the tracker")
print("Follow-up response:", response)

# Another follow-up
response = agent("What material is used in its straws?")
print("Second follow-up:", response)

# You can still use RAG or specify documents in follow-ups
response = agent("\\rag What's the latest status on its construction?")
print("Follow-up with RAG:", response)
```

