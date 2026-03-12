# backend/app/rag/retrieve.py
"""
Hybrid retrieval module combining:
- Dense retrieval (semantic embeddings via ChromaDB)
- Sparse retrieval (BM25 keyword search)
- Reranking for improved relevance
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from backend.app.rag.store import (
    get_collection, 
    DEFAULT_COLLECTION, 
    QUANT_COLLECTION,
    SOURCE_APP_LIBRARY,
    SOURCE_QUANT_DATA,
)
from backend.app.rag.bm25 import bm25_search, get_bm25_index
from backend.app.rag.utils import logger

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")


def embed_query(query: str) -> List[float]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=EMBED_MODEL, input=[query])
    return resp.data[0].embedding


def dense_retrieve(
    query: str,
    top_k: int = 10,
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, str, Dict[str, Any], float]]:
    """
    Dense retrieval using ChromaDB vector similarity.
    
    Returns:
        List of (doc_id, document, metadata, distance) tuples
    """
    query = (query or "").strip()
    if not query:
        return []

    col = get_collection(persist_dir=persist_dir, collection_name=collection_name)
    q_emb = embed_query(query)
    
    res = col.query(
        query_embeddings=[q_emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
        where=where,
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    distances = (res.get("distances") or [[]])[0]
    ids = (res.get("ids") or [[]])[0]

    results = []
    for doc_id, doc, meta, dist in zip(ids, docs, metas, distances):
        # Convert distance to similarity score (lower distance = higher similarity)
        similarity = 1.0 / (1.0 + dist)
        results.append((doc_id, doc, meta, similarity))
    
    return results


def sparse_retrieve(
    query: str,
    top_k: int = 10,
    collection_name: str = DEFAULT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, str, Dict[str, Any], float]]:
    """
    Sparse retrieval using BM25 keyword search.
    
    Returns:
        List of (doc_id, document, metadata, score) tuples
    """
    return bm25_search(query, top_k=top_k, collection_name=collection_name, where=where)


def hybrid_retrieve(
    query: str,
    top_k: int = 10,
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
) -> List[Tuple[str, str, Dict[str, Any], float]]:
    """
    Hybrid retrieval combining dense (semantic) and sparse (BM25) search.
    
    Args:
        query: Search query
        top_k: Number of results to return
        persist_dir: Vector store directory
        collection_name: Collection to search
        where: Optional metadata filter
        dense_weight: Weight for dense retrieval scores (0-1)
        sparse_weight: Weight for sparse retrieval scores (0-1)
        
    Returns:
        List of (doc_id, document, metadata, combined_score) tuples
    """
    # Get results from both retrievers
    dense_results = dense_retrieve(
        query, top_k=top_k * 2, persist_dir=persist_dir, 
        collection_name=collection_name, where=where
    )
    sparse_results = sparse_retrieve(
        query, top_k=top_k * 2, collection_name=collection_name, where=where
    )
    
    # Normalize scores within each result set
    def normalize_scores(results: List[Tuple]) -> Dict[str, Tuple[str, Dict, float]]:
        if not results:
            return {}
        scores = [r[3] for r in results]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score > min_score else 1.0
        
        normalized = {}
        for doc_id, doc, meta, score in results:
            norm_score = (score - min_score) / score_range if score_range > 0 else score
            normalized[doc_id] = (doc, meta, norm_score)
        return normalized
    
    dense_norm = normalize_scores(dense_results)
    sparse_norm = normalize_scores(sparse_results)
    
    # Combine scores using Reciprocal Rank Fusion (RRF) style combination
    all_doc_ids = set(dense_norm.keys()) | set(sparse_norm.keys())
    combined_results = []
    
    for doc_id in all_doc_ids:
        dense_score = dense_norm.get(doc_id, (None, None, 0.0))[2] if doc_id in dense_norm else 0.0
        sparse_score = sparse_norm.get(doc_id, (None, None, 0.0))[2] if doc_id in sparse_norm else 0.0
        
        # Get document and metadata from whichever source has it
        if doc_id in dense_norm:
            doc, meta = dense_norm[doc_id][0], dense_norm[doc_id][1]
        else:
            doc, meta = sparse_norm[doc_id][0], sparse_norm[doc_id][1]
        
        combined_score = (dense_weight * dense_score) + (sparse_weight * sparse_score)
        combined_results.append((doc_id, doc, meta, combined_score))
    
    # Sort by combined score descending
    combined_results.sort(key=lambda x: x[3], reverse=True)
    
    return combined_results[:top_k]


def retrieve_with_rerank(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
    use_hybrid: bool = True,
    rerank_provider: str = "cohere",
    rerank_top_n: Optional[int] = None,
) -> List[Tuple[str, str, Dict[str, Any], float]]:
    """
    Retrieve documents with optional reranking.
    
    Args:
        query: Search query
        top_k: Number of final results to return
        persist_dir: Vector store directory
        collection_name: Collection to search
        where: Optional metadata filter
        use_hybrid: Whether to use hybrid retrieval (True) or dense only (False)
        rerank_provider: Reranking provider ("cohere", "jina", "aliyun", or None to skip)
        rerank_top_n: Number of documents to rerank (defaults to top_k * 3)
        
    Returns:
        List of (doc_id, document, metadata, score) tuples
    """
    # Initial retrieval
    candidates_k = (rerank_top_n or top_k * 3) if rerank_provider else top_k
    
    if use_hybrid:
        candidates = hybrid_retrieve(
            query, top_k=candidates_k, persist_dir=persist_dir,
            collection_name=collection_name, where=where
        )
    else:
        candidates = dense_retrieve(
            query, top_k=candidates_k, persist_dir=persist_dir,
            collection_name=collection_name, where=where
        )
    
    if not candidates:
        return []
    
    # Apply reranking if provider is specified
    if rerank_provider and len(candidates) > 1:
        try:
            from backend.app.rag.rerank import rerank_sync
            
            documents = [c[1] for c in candidates]
            rerank_results = rerank_sync(
                query=query,
                documents=documents,
                top_n=top_k,
                provider=rerank_provider
            )
            
            # Reorder candidates based on rerank results
            reranked_candidates = []
            for result in rerank_results:
                idx = result["index"]
                if idx < len(candidates):
                    doc_id, doc, meta, _ = candidates[idx]
                    reranked_candidates.append((doc_id, doc, meta, result["relevance_score"]))
            
            return reranked_candidates[:top_k]
            
        except Exception as e:
            logger.warning(f"Reranking failed, returning unranked results: {e}")
            return candidates[:top_k]
    
    return candidates[:top_k]


def retrieve_from_both_sources(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    where: Optional[Dict[str, Any]] = None,
    use_hybrid: bool = True,
    rerank_provider: Optional[str] = "cohere",
    app_library_weight: float = 0.6,
    quant_data_weight: float = 0.4,
) -> Dict[str, Any]:
    """
    Retrieve from both app_library and quant_data knowledge bases.
    
    Args:
        query: Search query
        top_k: Number of results per source
        persist_dir: Vector store directory
        where: Optional metadata filter
        use_hybrid: Whether to use hybrid retrieval
        rerank_provider: Reranking provider (or None to skip)
        app_library_weight: Weight for app_library results
        quant_data_weight: Weight for quant_data results
        
    Returns:
        Dictionary with combined results and source-specific results
    """
    # Retrieve from app_library (text-rich documents)
    app_library_results = retrieve_with_rerank(
        query, top_k=top_k, persist_dir=persist_dir,
        collection_name=DEFAULT_COLLECTION, where=where,
        use_hybrid=use_hybrid, rerank_provider=rerank_provider
    )
    
    # Retrieve from quant_data (quantitative files)
    quant_results = retrieve_with_rerank(
        query, top_k=top_k, persist_dir=persist_dir,
        collection_name=QUANT_COLLECTION, where=where,
        use_hybrid=use_hybrid, rerank_provider=rerank_provider
    )
    
    # Combine and weight results
    all_results = []
    for doc_id, doc, meta, score in app_library_results:
        all_results.append((doc_id, doc, meta, score * app_library_weight, SOURCE_APP_LIBRARY))
    for doc_id, doc, meta, score in quant_results:
        all_results.append((doc_id, doc, meta, score * quant_data_weight, SOURCE_QUANT_DATA))
    
    # Sort by weighted score
    all_results.sort(key=lambda x: x[3], reverse=True)
    
    return {
        "combined": all_results[:top_k * 2],
        "app_library": app_library_results,
        "quant_data": quant_results,
    }


# ============ Legacy/Compatibility Functions ============

def retrieve(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Returns a single string of top_k snippets + citations.
    Reads from the persisted vector store on disk.
    
    This is the legacy interface for backward compatibility.
    """
    results = retrieve_with_rerank(
        query=query,
        top_k=top_k,
        persist_dir=persist_dir,
        collection_name=collection_name,
        where=where,
        use_hybrid=True,
        rerank_provider=None  # Skip reranking for legacy interface
    )

    parts: List[str] = []
    for i, (doc_id, doc, meta, score) in enumerate(results, start=1):
        source = (meta or {}).get("source", "unknown")
        chunk_index = (meta or {}).get("chunk_index", "—")
        source_type = (meta or {}).get("source_type", "unknown")
        parts.append(
            f"[{i}] Source: {source} (chunk {chunk_index}, type: {source_type})\n{(doc or '').strip()}"
        )

    return "\n\n---\n\n".join(parts)


def retrieve_detailed(
    query: str,
    top_k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
    where: Optional[Dict[str, Any]] = None,
    use_hybrid: bool = True,
    rerank_provider: Optional[str] = "cohere",
) -> List[Dict[str, Any]]:
    """
    Retrieve with detailed results including scores and metadata.
    
    Returns:
        List of dictionaries with doc, source, score, and metadata
    """
    results = retrieve_with_rerank(
        query=query,
        top_k=top_k,
        persist_dir=persist_dir,
        collection_name=collection_name,
        where=where,
        use_hybrid=use_hybrid,
        rerank_provider=rerank_provider
    )
    
    detailed = []
    for doc_id, doc, meta, score in results:
        detailed.append({
            "id": doc_id,
            "document": doc,
            "source": meta.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index"),
            "source_type": meta.get("source_type", "unknown"),
            "score": score,
            "metadata": meta,
        })
    
    return detailed

