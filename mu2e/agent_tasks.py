"""
Task implementations for AI agents - specific processing functions that agents perform.
"""

import re
from .tools import token_count
from .agents import DocumentSummarizerAgent


async def summarize_search_results(content: str, conversation_context: str) -> str:
    """
    Parse search results from mcp server and summarize each document individually.
    
    Args:
        content: Raw search results content
        conversation_context: Full conversation history for context
        
    Returns:
        Reconstructed search results with summarized content
    """
    
    # Check if this is XML-like search results
    if '<search_results' not in content:
        return content
        # For JSON or other formats, pass through to agent directly
        #agent = DocumentSummarizerAgent()
        #return await agent.summarize_document(content, conversation_context)
    
    # Extract search metadata
    search_match = re.search(r"<search_results query='([^']+)' type='([^']+)' count='([^']+)'>", content)
    if not search_match:
        return content
    
    query = search_match.group(1)
    search_type = search_match.group(2)
    count = search_match.group(3)
    
    # Start building new results
    new_content = f"<search_results query='{query}' type='{search_type}' count='{count}'>\n"
    
    # Extract all documents first
    doc_pattern = r"<document ([^>]*)>\s*(.*?)\s*</document>"
    documents = []
    
    for match in re.finditer(doc_pattern, content, re.DOTALL):
        attributes = match.group(1)
        doc_content = match.group(2).strip()
        documents.append((attributes, doc_content))
    
    # Build context for summarization
    context_for_summary = f"Search query: {query} | Conversation: {conversation_context}"
    
    # Prepare summarization tasks for documents that need it
    summarization_tasks = []
    doc_indices_to_summarize = []
    
    for i, (attributes, doc_content) in enumerate(documents):
        if token_count(doc_content) >= 200:  # Only summarize substantial content
            # Create a separate agent with short timeout for each task
            agent = DocumentSummarizerAgent(timeout=10.0, model="argo:gpt-4o")#"argo:claude-3.5-sonnet-v2")
            summarization_tasks.append(agent.summarize_document(doc_content, context_for_summary))
            doc_indices_to_summarize.append(i)
    

    #print("DEBUG summarization_tasks number", len(summarization_tasks))

    # Run all summarizations in parallel
    if summarization_tasks:
        try:
            import asyncio
            summarized_results = await asyncio.gather(*summarization_tasks, return_exceptions=True)
        except Exception as e:
            #print(f"Error in parallel summarization: {e}")
            summarized_results = [None] * len(summarization_tasks)
    else:
        summarized_results = []
    
    #print("All done, and building final result")
    
    # Build final content
    summarization_index = 0
    for i, (attributes, doc_content) in enumerate(documents):
        if i in doc_indices_to_summarize:
            # Use summarized content if available and not an exception
            result = summarized_results[summarization_index]
            #("DEBUG", i, summarization_index, result)
            if result and not isinstance(result, Exception):
                new_content += f"<document {attributes}>\n{result}\n</document>\n"
            else:
                print(f"Error summarizing document {i}: {result}")
                new_content += f"<document {attributes}>\n{doc_content}\n</document>\n"
            summarization_index += 1
        else:
            # Use original content for short documents
            new_content += f"<document {attributes}>\n{doc_content}\n</document>\n"
    
    new_content += "</search_results>"
    return new_content