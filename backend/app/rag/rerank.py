# backend/app/rag/rerank.py
from __future__ import annotations

import os
import aiohttp
from typing import Any, List, Dict, Optional, Tuple
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from backend.app.rag.utils import logger, TiktokenTokenizer

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=False)


def chunk_documents_for_rerank(
    documents: List[str],
    max_tokens: int = 480,
    overlap_tokens: int = 32,
    tokenizer_model: str = "gpt-4o-mini",
) -> Tuple[List[str], List[int]]:
    """
    Chunk documents that exceed token limit for reranking.

    Args:
        documents: List of document strings to chunk
        max_tokens: Maximum tokens per chunk (default 480 to leave margin for 512 limit)
        overlap_tokens: Number of tokens to overlap between chunks
        tokenizer_model: Model name for tiktoken tokenizer

    Returns:
        Tuple of (chunked_documents, original_doc_indices)
    """
    if overlap_tokens >= max_tokens:
        original_overlap = overlap_tokens
        overlap_tokens = max(0, max_tokens - 1)
        logger.warning(
            f"overlap_tokens ({original_overlap}) must be less than max_tokens ({max_tokens}). "
            f"Clamping to {overlap_tokens} to prevent infinite loop."
        )

    try:
        tokenizer = TiktokenTokenizer(model_name=tokenizer_model)
    except Exception as e:
        logger.warning(
            f"Failed to initialize tokenizer: {e}. Using character-based approximation."
        )
        max_chars = max_tokens * 4
        overlap_chars = overlap_tokens * 4

        chunked_docs = []
        doc_indices = []

        for idx, doc in enumerate(documents):
            if len(doc) <= max_chars:
                chunked_docs.append(doc)
                doc_indices.append(idx)
            else:
                start = 0
                while start < len(doc):
                    end = min(start + max_chars, len(doc))
                    chunk = doc[start:end]
                    chunked_docs.append(chunk)
                    doc_indices.append(idx)

                    if end >= len(doc):
                        break
                    start = end - overlap_chars

        return chunked_docs, doc_indices

    chunked_docs = []
    doc_indices = []

    for idx, doc in enumerate(documents):
        tokens = tokenizer.encode(doc)

        if len(tokens) <= max_tokens:
            chunked_docs.append(doc)
            doc_indices.append(idx)
        else:
            start = 0
            while start < len(tokens):
                end = min(start + max_tokens, len(tokens))
                chunk_tokens = tokens[start:end]
                chunk_text = tokenizer.decode(chunk_tokens)
                chunked_docs.append(chunk_text)
                doc_indices.append(idx)

                if end >= len(tokens):
                    break
                start = end - overlap_tokens

    return chunked_docs, doc_indices


def aggregate_chunk_scores(
    chunk_results: List[Dict[str, Any]],
    doc_indices: List[int],
    num_original_docs: int,
    aggregation: str = "max",
) -> List[Dict[str, Any]]:
    """
    Aggregate rerank scores from document chunks back to original documents.
    """
    doc_scores: Dict[int, List[float]] = {i: [] for i in range(num_original_docs)}

    for result in chunk_results:
        chunk_idx = result["index"]
        score = result["relevance_score"]

        if 0 <= chunk_idx < len(doc_indices):
            original_doc_idx = doc_indices[chunk_idx]
            doc_scores[original_doc_idx].append(score)

    aggregated_results = []
    for doc_idx, scores in doc_scores.items():
        if not scores:
            continue

        if aggregation == "max":
            final_score = max(scores)
        elif aggregation == "mean":
            final_score = sum(scores) / len(scores)
        elif aggregation == "first":
            final_score = scores[0]
        else:
            logger.warning(f"Unknown aggregation strategy: {aggregation}, using max")
            final_score = max(scores)

        aggregated_results.append(
            {
                "index": doc_idx,
                "relevance_score": final_score,
            }
        )

    aggregated_results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return aggregated_results


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=(
        retry_if_exception_type(aiohttp.ClientError)
        | retry_if_exception_type(aiohttp.ClientResponseError)
    ),
)
async def generic_rerank_api(
    query: str,
    documents: List[str],
    model: str,
    base_url: str,
    api_key: Optional[str],
    top_n: Optional[int] = None,
    return_documents: Optional[bool] = None,
    extra_body: Optional[Dict[str, Any]] = None,
    response_format: str = "standard",
    request_format: str = "standard",
    enable_chunking: bool = False,
    max_tokens_per_doc: int = 480,
) -> List[Dict[str, Any]]:
    """
    Generic rerank API call for Jina/Cohere/Aliyun models.
    """
    if not base_url:
        raise ValueError("Base URL is required")

    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"

    original_documents = documents
    doc_indices = None
    original_top_n = top_n

    if enable_chunking:
        documents, doc_indices = chunk_documents_for_rerank(
            documents, max_tokens=max_tokens_per_doc
        )
        logger.debug(
            f"Chunked {len(original_documents)} documents into {len(documents)} chunks"
        )
        if top_n is not None:
            logger.debug(
                f"Chunking enabled: disabled API-level top_n={top_n} to ensure complete document coverage"
            )
            top_n = None

    if request_format == "aliyun":
        payload = {
            "model": model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {},
        }
        if top_n is not None:
            payload["parameters"]["top_n"] = top_n
        if return_documents is not None:
            payload["parameters"]["return_documents"] = return_documents
        if extra_body:
            payload["parameters"].update(extra_body)
    else:
        payload = {
            "model": model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        if return_documents is not None and response_format in ("standard",):
            payload["return_documents"] = return_documents
        if extra_body:
            payload.update(extra_body)

    logger.debug(
        f"Rerank request: {len(documents)} documents, model: {model}, format: {response_format}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(base_url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                content_type = response.headers.get("content-type", "").lower()
                is_html_error = (
                    error_text.strip().startswith("<!DOCTYPE html>")
                    or "text/html" in content_type
                )
                if is_html_error:
                    if response.status == 502:
                        clean_error = "Bad Gateway (502) - Rerank service temporarily unavailable."
                    elif response.status == 503:
                        clean_error = "Service Unavailable (503) - Rerank service is temporarily overloaded."
                    elif response.status == 504:
                        clean_error = "Gateway Timeout (504) - Rerank service request timed out."
                    else:
                        clean_error = f"HTTP {response.status} - Rerank service error."
                else:
                    clean_error = error_text
                logger.error(f"Rerank API error {response.status}: {clean_error}")
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"Rerank API error: {clean_error}",
                )

            response_json = await response.json()

            if response_format == "aliyun":
                results = response_json.get("output", {}).get("results", [])
            elif response_format == "standard":
                results = response_json.get("results", [])
            else:
                raise ValueError(f"Unsupported response format: {response_format}")

            if not results:
                logger.warning("Rerank API returned empty results")
                return []

            standardized_results = [
                {"index": result["index"], "relevance_score": result["relevance_score"]}
                for result in results
            ]

            if enable_chunking and doc_indices:
                standardized_results = aggregate_chunk_scores(
                    standardized_results,
                    doc_indices,
                    len(original_documents),
                    aggregation="max",
                )
                if (
                    original_top_n is not None
                    and len(standardized_results) > original_top_n
                ):
                    standardized_results = standardized_results[:original_top_n]

            return standardized_results


async def cohere_rerank(
    query: str,
    documents: List[str],
    top_n: Optional[int] = None,
    api_key: Optional[str] = None,
    model: str = "rerank-v3.5",
    base_url: str = "https://api.cohere.com/v2/rerank",
    extra_body: Optional[Dict[str, Any]] = None,
    enable_chunking: bool = False,
    max_tokens_per_doc: int = 4096,
) -> List[Dict[str, Any]]:
    """Rerank documents using Cohere API."""
    if api_key is None:
        api_key = os.getenv("COHERE_API_KEY") or os.getenv("RERANK_BINDING_API_KEY")

    return await generic_rerank_api(
        query=query,
        documents=documents,
        model=model,
        base_url=base_url,
        api_key=api_key,
        top_n=top_n,
        return_documents=None,
        extra_body=extra_body,
        response_format="standard",
        enable_chunking=enable_chunking,
        max_tokens_per_doc=max_tokens_per_doc,
    )


async def jina_rerank(
    query: str,
    documents: List[str],
    top_n: Optional[int] = None,
    api_key: Optional[str] = None,
    model: str = "jina-reranker-v2-base-multilingual",
    base_url: str = "https://api.jina.ai/v1/rerank",
    extra_body: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Rerank documents using Jina AI API."""
    if api_key is None:
        api_key = os.getenv("JINA_API_KEY") or os.getenv("RERANK_BINDING_API_KEY")

    return await generic_rerank_api(
        query=query,
        documents=documents,
        model=model,
        base_url=base_url,
        api_key=api_key,
        top_n=top_n,
        return_documents=False,
        extra_body=extra_body,
        response_format="standard",
    )


async def ali_rerank(
    query: str,
    documents: List[str],
    top_n: Optional[int] = None,
    api_key: Optional[str] = None,
    model: str = "gte-rerank-v2",
    base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    extra_body: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Rerank documents using Aliyun DashScope API."""
    if api_key is None:
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("RERANK_BINDING_API_KEY")

    return await generic_rerank_api(
        query=query,
        documents=documents,
        model=model,
        base_url=base_url,
        api_key=api_key,
        top_n=top_n,
        return_documents=False,
        extra_body=extra_body,
        response_format="aliyun",
        request_format="aliyun",
    )


# Synchronous wrapper for use in non-async contexts
def rerank_sync(
    query: str,
    documents: List[str],
    top_n: Optional[int] = None,
    provider: str = "cohere",
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for reranking.
    
    Args:
        query: Search query
        documents: List of documents to rerank
        top_n: Number of top results to return
        provider: Rerank provider ("cohere", "jina", "aliyun")
        api_key: API key for the provider
        
    Returns:
        List of reranked results with index and relevance_score
    """
    import asyncio
    
    async def _rerank():
        if provider == "cohere":
            return await cohere_rerank(query, documents, top_n=top_n, api_key=api_key)
        elif provider == "jina":
            return await jina_rerank(query, documents, top_n=top_n, api_key=api_key)
        elif provider == "aliyun":
            return await ali_rerank(query, documents, top_n=top_n, api_key=api_key)
        else:
            raise ValueError(f"Unknown rerank provider: {provider}")
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _rerank())
                return future.result()
        else:
            return loop.run_until_complete(_rerank())
    except RuntimeError:
        return asyncio.run(_rerank())
