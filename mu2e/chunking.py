import tiktoken
from typing import List, Optional, Tuple


class TextChunker:
    """
    Text chunking utility for preparing documents for embedding generation.
    Supports various chunking strategies optimized for different content types.
    """
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 model: str = "text-embedding-3-small"):
        """
        Initialize text chunker.
        
        Args:
            chunk_size: Target size for each chunk in tokens
            chunk_overlap: Number of overlapping tokens between chunks
            model: Model name for token counting
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model = model
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except:
            # Fallback to a default encoding if model not found
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def chunk_text(self, text: str, strategy: str = "default") -> List[str]:
        """
        Chunk text using specified strategy.
        """
        if strategy == "default":
            return self._chunk_by_tokens(text)
        elif strategy == "slide":
            return self._chunk_by_slide(text)
        else:
            return self._chunk_by_tokens(text)
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
     
    def _chunk_by_tokens(self, text: str) -> List[str]:
        """Chunk text by token count with sliding window."""
        tokens = self.encoding.encode(text)
        chunks = []
        
        if len(tokens) <= self.chunk_size:
            return [text]
        
        start_idx = 0
        while start_idx < len(tokens):
            end_idx = min(start_idx + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move start position accounting for overlap
            start_idx = end_idx - self.chunk_overlap
            if end_idx >= len(tokens):
                break
        
        return chunks
    
    def _chunk_by_slide(self, text: str) -> List[str]:
        # TODO!
        return self._chunk_by_tokens(text)

def chunk_text_simple(text: str, 
                     chunk_size: int = 1000,
                     chunk_overlap: int = 200,
                     strategy: str = "default",
                     model: str = "text-embedding-3-small") -> List[str]:
    """
    Simple function to chunk text.
    
    Args:
        text: Input text to chunk
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks in tokens
        strategy: Chunking strategy
        model: Model for token counting
        
    Returns:
        List of text chunks
    """

    chunker = TextChunker(chunk_size=chunk_size, 
                         chunk_overlap=chunk_overlap, 
                         model=model)
    return chunker.chunk_text(text, strategy=strategy)