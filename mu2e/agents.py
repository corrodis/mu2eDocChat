"""
AI agents for sub-tasks
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from .tools import getOpenAIClient, token_count
from .utils import get_model, get_max_context


class DocumentSummarizerAgent:
    """
    Agent that summarizes document content to reduce context size while preserving relevant information.
    """
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.3, max_tokens: int = 1000, timeout: float = 10.0):
        """
        Initialize the summarizer agent.
        
        Args:
            model: Model to use for summarization (defaults to get_model())
            temperature: Temperature for generation
            max_tokens: Maximum tokens for summary
            timeout: Timeout in seconds for API calls
        """
        self.client = getOpenAIClient()
        self.client.timeout = timeout  # Set timeout on the client
        self.model = model or get_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
    def _build_summarization_prompt(self, document_content: str, user_query: str) -> str:
        """
        Build prompt for summarizing document content.
        
        Args:
            document_content: Raw document content to summarize
            user_query: Original user question for context
            
        Returns:
            Summarization prompt
        """
        return f"""
Please provide a concise summary of the following document content relevant to the following conversation context: "{user_query}"

Document Content:
{document_content}

Create a summary that:
1. Highlights the most relevant information for the user's provided context
2. Preserves key details, names, dates, values, and document references
3. Maintains document IDs and links for citation
4. Focuses on answering the user's specific question
5. try to roughly stay below 500 tokens

Summary:"""
    
    async def summarize_document(self, document_content: str, user_context: str = "") -> str:
        """
        Summarize document content with user query context.
        
        Args:
            document_content: Raw document text to summarize
            user_context: Original user question for context
            
        Returns:
            Summarized content or original content if summarization fails
        """
        #print("DEBUG START summarize_document")
        # Check if content is large enough to warrant summarization
        original_tokens = token_count(document_content)
        #print("DEBUG START summarize_document tokens: ", original_tokens)
        if original_tokens < 500:  # Don't summarize short content
            return document_content
        
        # Truncate if content exceeds 80% of max context limit
        max_context = get_max_context()
        max_input_tokens = int(max_context * 0.8)
        if original_tokens > max_input_tokens:
            # Rough character-to-token ratio (approximately 4 chars per token)
            max_chars = max_input_tokens * 4
            document_content = document_content[:max_chars]
            truncated_tokens = token_count(document_content)
            print(f"Truncated document: {original_tokens} -> {truncated_tokens} tokens (max: {max_input_tokens})")
            original_tokens = truncated_tokens
        
        try:
            # Build summarization prompt
            prompt = self._build_summarization_prompt(document_content, user_context)
            #print("DEBUG START summarize_document send (", self.model, ")")
            # Generate summary using thread pool to avoid blocking the event loop
            import asyncio
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            #print("DEBUG START summarize_document got response")
            summary = response.choices[0].message.content or ""
            summary_tokens = token_count(summary)
            
            # Log the token reduction
            print(f"Summarized document: {original_tokens} -> {summary_tokens} tokens ({original_tokens - summary_tokens} saved)")
            
            # Add metadata about the summarization
            summary_header = f"[SUMMARIZED from {original_tokens} tokens to {summary_tokens} tokens]\n\n"
            
            return summary_header + summary
            
        except Exception as e:
            print(f"Error summarizing document: {e}")
            # Return original content if summarization fails
            return document_content
