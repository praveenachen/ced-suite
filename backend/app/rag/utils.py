# backend/app/rag/utils.py
from __future__ import annotations

import logging
import os
from typing import List, Optional

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag")


class TiktokenTokenizer:
    """
    Token-based text processing using tiktoken.
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        try:
            import tiktoken
            self.encoding = tiktoken.encoding_for_model(model_name)
        except Exception:
            # Fallback to cl100k_base encoding
            import tiktoken
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def encode(self, text: str) -> List[int]:
        """Encode text to tokens."""
        return self.encoding.encode(text)
    
    def decode(self, tokens: List[int]) -> str:
        """Decode tokens to text."""
        return self.encoding.decode(tokens)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encode(text))


def chunk_by_tokens(
    text: str,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    model_name: str = "gpt-4o-mini"
) -> List[str]:
    """
    Chunk text by token count with overlap.
    
    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of overlapping tokens between chunks
        model_name: Model name for tokenizer
        
    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []
    
    try:
        tokenizer = TiktokenTokenizer(model_name)
        tokens = tokenizer.encode(text)
        
        if len(tokens) <= max_tokens:
            return [text]
        
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            if end >= len(tokens):
                break
            start = end - overlap_tokens
        
        return chunks
        
    except ImportError:
        # Fallback to character-based chunking
        logger.warning("tiktoken not available, using character-based chunking")
        max_chars = max_tokens * 4
        overlap_chars = overlap_tokens * 4
        
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            
            if end >= len(text):
                break
            start = end - overlap_chars
        
        return chunks
