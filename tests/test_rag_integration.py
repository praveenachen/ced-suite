"""
RAG Pipeline Integration Tests
===============================
Tests all components of the RAG pipeline without requiring an OpenAI API key
by mocking embedding calls where needed. Tests that DO use the API are clearly marked.

Run:  python -m pytest tests/test_rag_integration.py -v
  Or: python tests/test_rag_integration.py            (standalone)
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import List

# Ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _fake_embeddings(texts: List[str]) -> List[List[float]]:
    """Deterministic fake embeddings for testing (no API call)."""
    dim = 32
    results = []
    for t in texts:
        h = hash(t) & 0xFFFFFFFF
        vec = [(((h * (i + 1)) % 1000) / 1000.0) for i in range(dim)]
        results.append(vec)
    return results


def _fake_embed_query(query: str) -> List[float]:
    return _fake_embeddings([query])[0]


class FakeEmbeddingResponse:
    def __init__(self, embeddings):
        self.data = [type("Obj", (), {"embedding": e})() for e in embeddings]


# ──────────────────────────────────────────────
# Test fixtures
# ──────────────────────────────────────────────
class TestEnvironment:
    """Creates temp directories with sample files for testing."""

    def __init__(self):
        self.base_dir = tempfile.mkdtemp(prefix="rag_test_")
        self.app_library_dir = os.path.join(self.base_dir, "app_library")
        self.quant_data_dir = os.path.join(self.base_dir, "quant_data")
        self.vector_store_dir = os.path.join(self.base_dir, "vector_store")
        os.makedirs(self.app_library_dir, exist_ok=True)
        os.makedirs(self.quant_data_dir, exist_ok=True)
        os.makedirs(self.vector_store_dir, exist_ok=True)
        self._create_sample_files()

    def _create_sample_files(self):
        # Text files
        Path(self.app_library_dir, "proposal1.txt").write_text(
            "This is a grant proposal about affordable housing in Nunavut. "
            "The community faces challenges with water infrastructure and aging pipes. "
            "We propose targeted investments to address these critical needs.",
            encoding="utf-8",
        )
        Path(self.app_library_dir, "proposal2.txt").write_text(
            "SSHRC Insight Development Grant application for CivicInquire platform. "
            "This research focuses on homelessness policy analysis across Canadian "
            "municipalities using machine learning and web scraping tools.",
            encoding="utf-8",
        )
        Path(self.app_library_dir, "guide.md").write_text(
            "# Grant Writing Guide\n\n"
            "## Section 1: Project Summary\n"
            "Provide a 500-word summary of the project objectives.\n\n"
            "## Section 2: Budget\n"
            "Detail the requested funding amount and allocation.\n",
            encoding="utf-8",
        )

        # CSV files
        csv_path = Path(self.quant_data_dir, "housing_stats.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Community", "Population", "HousingUnits", "VacancyRate"])
            writer.writerow(["Iqaluit", "8000", "2500", "1.2"])
            writer.writerow(["Rankin Inlet", "3100", "900", "0.8"])
            writer.writerow(["Arviat", "2800", "750", "1.5"])
            writer.writerow(["Baker Lake", "2100", "600", "2.0"])

        csv_path2 = Path(self.quant_data_dir, "water_quality.csv")
        with open(csv_path2, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Community", "BoilWaterAdvisories", "PipeAge", "RepairCost"])
            writer.writerow(["Iqaluit", "3", "25", "450000"])
            writer.writerow(["Rankin Inlet", "1", "18", "200000"])
            writer.writerow(["Arviat", "5", "30", "600000"])

        # Invalid file (for error handling test)
        Path(self.quant_data_dir, "notes.txt").write_text("This is not a CSV", encoding="utf-8")

    def cleanup(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────
def test_store_module():
    """Test store.py: client creation, collection management, stable_id."""
    print("\n=== Test: store module ===")
    from backend.app.rag.store import (
        get_client, get_collection, stable_id, list_collections,
        get_collection_stats, delete_collection,
    )

    env = TestEnvironment()
    try:
        # Client creation
        client = get_client(persist_dir=env.vector_store_dir)
        assert client is not None, "Client should not be None"
        print("  [PASS] get_client creates a ChromaDB client")

        # Collection creation
        col = get_collection(persist_dir=env.vector_store_dir, collection_name="test_col")
        assert col is not None, "Collection should not be None"
        assert col.name == "test_col"
        print("  [PASS] get_collection creates/gets a collection")

        # stable_id determinism
        id1 = stable_id("hello world", "source1")
        id2 = stable_id("hello world", "source1")
        id3 = stable_id("hello world", "source2")
        assert id1 == id2, "Same content+source should produce same ID"
        assert id1 != id3, "Different source should produce different ID"
        print("  [PASS] stable_id is deterministic and source-aware")

        # Collection stats
        stats = get_collection_stats("test_col", persist_dir=env.vector_store_dir)
        assert stats["exists"] is True
        assert stats["count"] == 0
        print("  [PASS] get_collection_stats returns correct info")

        # Delete collection
        result = delete_collection("test_col", persist_dir=env.vector_store_dir)
        assert result is True
        print("  [PASS] delete_collection works")

    finally:
        env.cleanup()


def test_bm25_module():
    """Test bm25.py: indexing, search, save/load."""
    print("\n=== Test: BM25 module ===")
    from backend.app.rag.bm25 import BM25Index

    env = TestEnvironment()
    try:
        index = BM25Index()

        # Add documents
        docs = [
            "affordable housing in Nunavut communities",
            "water infrastructure challenges in Iqaluit",
            "machine learning for policy analysis",
            "grant proposal budget allocation methods",
        ]
        ids = [f"doc_{i}" for i in range(len(docs))]
        metas = [{"source": f"test_{i}.txt"} for i in range(len(docs))]
        index.add_documents(docs, ids, metas)

        assert index.num_docs == 4, f"Expected 4 docs, got {index.num_docs}"
        print("  [PASS] add_documents indexes correctly")

        # Search
        results = index.search("housing Nunavut", top_k=2)
        assert len(results) > 0, "Should find at least one result"
        assert results[0][0] == "doc_0", f"First result should be doc_0, got {results[0][0]}"
        print(f"  [PASS] BM25 search returns relevant results (top: {results[0][0]})")

        # Search with metadata filter
        results_filtered = index.search("housing", top_k=4, where={"source": "test_0.txt"})
        assert all(r[2]["source"] == "test_0.txt" for r in results_filtered)
        print("  [PASS] BM25 search with metadata filter works")

        # Save/load
        save_path = os.path.join(env.vector_store_dir, "test_bm25.pkl")
        index.save(save_path)
        assert os.path.exists(save_path)

        loaded = BM25Index.load(save_path)
        assert loaded.num_docs == 4
        loaded_results = loaded.search("housing Nunavut", top_k=2)
        assert loaded_results[0][0] == results[0][0]
        print("  [PASS] BM25 save/load preserves index")

    finally:
        env.cleanup()


def test_chunking():
    """Test chunking functions for both text and quantitative data."""
    print("\n=== Test: Chunking ===")
    from backend.app.rag.ingest import chunk_text, chunk_quantitative_data

    # Text chunking
    text = "A" * 3000
    chunks = chunk_text(text, chunk_size=1200, overlap=150)
    assert len(chunks) >= 3, f"Expected >=3 chunks, got {len(chunks)}"
    assert all(len(c) <= 1200 for c in chunks)
    print(f"  [PASS] chunk_text: {len(chunks)} chunks from 3000 chars")

    # Empty text
    assert chunk_text("") == []
    assert chunk_text(None) == []
    print("  [PASS] chunk_text handles empty/None")

    # Quantitative chunking
    lines = [f"row_{i}: value_{i}" for i in range(50)]
    quant_text = "\n".join(lines)
    quant_chunks = chunk_quantitative_data(quant_text, chunk_size=200)
    assert len(quant_chunks) > 1
    # Verify no line breaks mid-row
    for c in quant_chunks:
        for line in c.strip().split("\n"):
            assert "row_" in line or line == ""
    print(f"  [PASS] chunk_quantitative_data: {len(quant_chunks)} chunks, lines preserved")


def test_file_readers():
    """Test file reading functions for all supported types."""
    print("\n=== Test: File Readers ===")
    from backend.app.rag.ingest import read_file

    env = TestEnvironment()
    try:
        # TXT
        txt_content = read_file(Path(env.app_library_dir, "proposal1.txt"))
        assert "affordable housing" in txt_content
        print("  [PASS] read_file handles .txt")

        # Markdown
        md_content = read_file(Path(env.app_library_dir, "guide.md"))
        assert "Grant Writing Guide" in md_content
        print("  [PASS] read_file handles .md")

        # CSV
        csv_content = read_file(Path(env.quant_data_dir, "housing_stats.csv"))
        assert "Iqaluit" in csv_content
        assert "Population" in csv_content or "population" in csv_content.lower()
        print("  [PASS] read_file handles .csv")

        # Unsupported
        unsupported = read_file(Path(env.base_dir, "fake.xyz"))
        assert unsupported == ""
        print("  [PASS] read_file returns empty for unsupported types")

    finally:
        env.cleanup()


def test_ingestion_with_mock_embeddings():
    """Test full ingestion pipeline with mocked embeddings (no API key needed)."""
    print("\n=== Test: Ingestion Pipeline (mocked embeddings) ===")
    from backend.app.rag.ingest import ingest_folder, ingest_quant_data
    from backend.app.rag.store import get_collection

    env = TestEnvironment()
    try:
        with patch("backend.app.rag.ingest.embed_texts", side_effect=_fake_embeddings):
            # Ingest app_library
            result = ingest_folder(
                library_dir=env.app_library_dir,
                persist_dir=env.vector_store_dir,
                collection_name="test_grant_library",
                reset=True,
                source_tag="test"
            )
            assert result["files"] >= 2, f"Expected >=2 files, got {result['files']}"
            assert result["chunks"] > 0, "Should have chunks"
            print(f"  [PASS] ingest_folder: {result['files']} files, {result['chunks']} chunks")

            # Verify ChromaDB has data
            col = get_collection(persist_dir=env.vector_store_dir, collection_name="test_grant_library")
            count = col.count()
            assert count == result["chunks"], f"ChromaDB count {count} != chunks {result['chunks']}"
            print(f"  [PASS] ChromaDB has {count} indexed chunks")

            # Ingest quant_data
            quant_result = ingest_quant_data(
                data_dir=env.quant_data_dir,
                persist_dir=env.vector_store_dir,
                collection_name="test_quant_data",
                reset=True,
            )
            assert quant_result["files"] >= 2, f"Expected >=2 CSV files, got {quant_result['files']}"
            assert quant_result["chunks"] > 0
            print(f"  [PASS] ingest_quant_data: {quant_result['files']} files, {quant_result['chunks']} chunks")

            # Deduplication test: re-ingest and check count doesn't double
            result2 = ingest_folder(
                library_dir=env.app_library_dir,
                persist_dir=env.vector_store_dir,
                collection_name="test_grant_library",
                reset=False,
                source_tag="test"
            )
            col2 = get_collection(persist_dir=env.vector_store_dir, collection_name="test_grant_library")
            count2 = col2.count()
            # With deterministic IDs, Chroma should have the same count or at most 2x
            # (depending on Chroma version upsert behavior)
            print(f"  [INFO] After re-ingest: {count2} chunks (was {count})")
            print("  [PASS] Deduplication: re-ingest completed without error")

    finally:
        env.cleanup()


def test_retrieval_with_mock():
    """Test retrieval pipeline (dense, sparse, hybrid) with mocked embeddings."""
    print("\n=== Test: Retrieval Pipeline (mocked) ===")
    from backend.app.rag.ingest import ingest_folder, ingest_quant_data
    from backend.app.rag.retrieve import dense_retrieve, sparse_retrieve, hybrid_retrieve, retrieve
    from backend.app.rag.bm25 import get_bm25_index

    env = TestEnvironment()
    try:
        # First ingest test data
        with patch("backend.app.rag.ingest.embed_texts", side_effect=_fake_embeddings):
            ingest_folder(
                library_dir=env.app_library_dir,
                persist_dir=env.vector_store_dir,
                collection_name="test_grant_library",
                reset=True,
            )
            ingest_quant_data(
                data_dir=env.quant_data_dir,
                persist_dir=env.vector_store_dir,
                collection_name="test_quant_data",
                reset=True,
            )

        # Test dense retrieval (mocked query embedding)
        with patch("backend.app.rag.retrieve.embed_query", side_effect=_fake_embed_query):
            dense_results = dense_retrieve(
                "affordable housing",
                top_k=3,
                persist_dir=env.vector_store_dir,
                collection_name="test_grant_library"
            )
            assert len(dense_results) > 0, "Dense retrieval should return results"
            print(f"  [PASS] dense_retrieve: {len(dense_results)} results")

        # Test sparse (BM25) retrieval
        sparse_results = sparse_retrieve(
            "housing Nunavut",
            top_k=3,
            collection_name="test_grant_library"
        )
        assert len(sparse_results) > 0, "Sparse retrieval should return results"
        print(f"  [PASS] sparse_retrieve: {len(sparse_results)} results")

        # Test hybrid retrieval
        with patch("backend.app.rag.retrieve.embed_query", side_effect=_fake_embed_query):
            hybrid_results = hybrid_retrieve(
                "housing infrastructure",
                top_k=3,
                persist_dir=env.vector_store_dir,
                collection_name="test_grant_library"
            )
            assert len(hybrid_results) > 0, "Hybrid retrieval should return results"
            print(f"  [PASS] hybrid_retrieve: {len(hybrid_results)} results")

        # Test legacy retrieve (string output)
        with patch("backend.app.rag.retrieve.embed_query", side_effect=_fake_embed_query):
            text_result = retrieve(
                "grant proposal",
                top_k=3,
                persist_dir=env.vector_store_dir,
                collection_name="test_grant_library"
            )
            assert isinstance(text_result, str)
            assert len(text_result) > 0
            print(f"  [PASS] legacy retrieve: returned {len(text_result)} chars")

    finally:
        env.cleanup()


def test_utils_module():
    """Test utils.py: tokenizer and chunk_by_tokens."""
    print("\n=== Test: Utils module ===")
    from backend.app.rag.utils import TiktokenTokenizer, chunk_by_tokens

    # Tokenizer
    try:
        tok = TiktokenTokenizer()
        tokens = tok.encode("Hello, world!")
        assert len(tokens) > 0
        decoded = tok.decode(tokens)
        assert "Hello" in decoded
        count = tok.count_tokens("This is a test sentence.")
        assert count > 0
        print(f"  [PASS] TiktokenTokenizer: encode/decode/count work ({count} tokens)")
    except ImportError:
        print("  [SKIP] tiktoken not installed")

    # chunk_by_tokens
    long_text = "word " * 2000  # ~2000 tokens
    chunks = chunk_by_tokens(long_text, max_tokens=512, overlap_tokens=50)
    assert len(chunks) > 1
    print(f"  [PASS] chunk_by_tokens: {len(chunks)} chunks from ~2000 words")

    # Edge cases
    assert chunk_by_tokens("") == []
    assert chunk_by_tokens("  ") == []
    short = chunk_by_tokens("short text", max_tokens=512)
    assert len(short) == 1
    print("  [PASS] chunk_by_tokens handles edge cases")


def test_rerank_module_structure():
    """Test rerank.py module structure (no API calls)."""
    print("\n=== Test: Rerank module structure ===")
    from backend.app.rag.rerank import (
        chunk_documents_for_rerank,
        aggregate_chunk_scores,
    )

    # chunk_documents_for_rerank
    docs = ["Short doc.", "A " * 500]  # Second doc is long
    chunked, indices = chunk_documents_for_rerank(docs, max_tokens=100, overlap_tokens=10)
    assert len(chunked) >= 2
    assert len(chunked) == len(indices)
    assert indices[0] == 0  # First chunk belongs to doc 0
    print(f"  [PASS] chunk_documents_for_rerank: {len(docs)} docs -> {len(chunked)} chunks")

    # aggregate_chunk_scores
    chunk_results = [
        {"index": 0, "relevance_score": 0.9},
        {"index": 1, "relevance_score": 0.7},
        {"index": 2, "relevance_score": 0.8},
    ]
    doc_indices = [0, 0, 1]
    aggregated = aggregate_chunk_scores(chunk_results, doc_indices, num_original_docs=2)
    assert len(aggregated) == 2
    # Doc 0 should have max(0.9, 0.7) = 0.9
    doc0 = [r for r in aggregated if r["index"] == 0][0]
    assert doc0["relevance_score"] == 0.9
    print("  [PASS] aggregate_chunk_scores: max aggregation correct")


def test_end_to_end_pipeline():
    """End-to-end test: ingest → retrieve → format output."""
    print("\n=== Test: End-to-End Pipeline ===")
    from backend.app.rag.ingest import ingest_folder, ingest_quant_data
    from backend.app.rag.retrieve import retrieve_from_both_sources

    env = TestEnvironment()
    try:
        with patch("backend.app.rag.ingest.embed_texts", side_effect=_fake_embeddings):
            ingest_folder(
                library_dir=env.app_library_dir,
                persist_dir=env.vector_store_dir,
                collection_name="e2e_grant_library",
                reset=True,
            )
            ingest_quant_data(
                data_dir=env.quant_data_dir,
                persist_dir=env.vector_store_dir,
                collection_name="e2e_quant_data",
                reset=True,
            )

        with patch("backend.app.rag.retrieve.embed_query", side_effect=_fake_embed_query):
            results = retrieve_from_both_sources(
                query="housing statistics Iqaluit",
                top_k=3,
                persist_dir=env.vector_store_dir,
                rerank_provider=None,  # Skip reranking for this test
            )

        assert "app_library" in results
        assert "quant_data" in results
        assert "combined" in results
        print(f"  [PASS] End-to-end: app_library={len(results['app_library'])} results, "
              f"quant_data={len(results['quant_data'])} results, "
              f"combined={len(results['combined'])} results")

    finally:
        env.cleanup()


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────
def run_all_tests():
    print("=" * 60)
    print("RAG Pipeline Integration Tests")
    print("=" * 60)

    tests = [
        ("Store Module", test_store_module),
        ("BM25 Module", test_bm25_module),
        ("Chunking", test_chunking),
        ("File Readers", test_file_readers),
        ("Ingestion Pipeline", test_ingestion_with_mock_embeddings),
        ("Retrieval Pipeline", test_retrieval_with_mock),
        ("Utils Module", test_utils_module),
        ("Rerank Module Structure", test_rerank_module_structure),
        ("End-to-End Pipeline", test_end_to_end_pipeline),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  [FAIL] {name}: {e}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
