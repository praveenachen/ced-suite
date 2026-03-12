# backend/app/rag/__init__.py
"""
Features:
- Dual knowledge bases: app_library (text-rich) and quant_data (quantitative)
- Hybrid retrieval: BM25 keyword search + dense semantic search
- Reranking support: Cohere, Jina, Aliyun
- Ingestion: TXT, PDF, DOCX, MD, CSV, XLSX
"""

from backend.app.rag.store import (
    get_collection,
    get_quant_collection,
    get_client,
    stable_id,
    get_app_library_dir,
    get_quant_data_dir,
    DEFAULT_COLLECTION,
    QUANT_COLLECTION,
)

from backend.app.rag.ingest import (
    ingest_folder,
    ingest_quant_data,
    ingest_all,
    chunk_text,
    embed_texts,
    read_file,
)

from backend.app.rag.retrieve import (
    retrieve,
    retrieve_detailed,
    retrieve_with_rerank,
    retrieve_from_both_sources,
    hybrid_retrieve,
    dense_retrieve,
    sparse_retrieve,
    embed_query,
)

from backend.app.rag.bm25 import (
    BM25Index,
    bm25_search,
    get_bm25_index,
)

from backend.app.rag.rerank import (
    rerank_sync,
    cohere_rerank,
    jina_rerank,
    ali_rerank,
)

__all__ = [
    # Store
    "get_collection",
    "get_quant_collection", 
    "get_client",
    "stable_id",
    "get_app_library_dir",
    "get_quant_data_dir",
    "DEFAULT_COLLECTION",
    "QUANT_COLLECTION",
    # Ingest
    "ingest_folder",
    "ingest_quant_data",
    "ingest_all",
    "chunk_text",
    "embed_texts",
    "read_file",
    # Retrieve
    "retrieve",
    "retrieve_detailed",
    "retrieve_with_rerank",
    "retrieve_from_both_sources",
    "hybrid_retrieve",
    "dense_retrieve",
    "sparse_retrieve",
    "embed_query",
    # BM25
    "BM25Index",
    "bm25_search",
    "get_bm25_index",
    # Rerank
    "rerank_sync",
    "cohere_rerank",
    "jina_rerank",
    "ali_rerank",
]
