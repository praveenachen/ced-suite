from __future__ import annotations

import math
import os
import pickle
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.app.rag.utils import logger


@dataclass
class BM25Index:
    k1: float = 1.5
    b: float = 0.75

    documents: List[str] = field(default_factory=list)
    doc_ids: List[str] = field(default_factory=list)
    metadatas: List[Dict[str, Any]] = field(default_factory=list)
    doc_lengths: List[int] = field(default_factory=list)
    avg_doc_length: float = 0.0
    doc_freqs: Dict[str, int] = field(default_factory=dict)
    term_freqs: List[Dict[str, int]] = field(default_factory=list)
    num_docs: int = 0

    def _tokenize(self, text: str) -> List[str]:
        text = (text or "").lower()
        tokens = re.findall(r"\b[a-z0-9]+\b", text)
        stopwords = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "this",
            "that", "these", "those", "it", "its", "as", "if", "when", "than",
            "so", "no", "not", "only", "same", "such", "also", "into"
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]

    def add_documents(
        self,
        documents: List[str],
        doc_ids: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if metadatas is None:
            metadatas = [{} for _ in documents]

        for doc, doc_id, meta in zip(documents, doc_ids, metadatas):
            tokens = self._tokenize(doc)
            term_freq = Counter(tokens)

            self.documents.append(doc)
            self.doc_ids.append(doc_id)
            self.metadatas.append(meta)
            self.doc_lengths.append(len(tokens))
            self.term_freqs.append(dict(term_freq))

            for term in set(tokens):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.num_docs = len(self.documents)
        self.avg_doc_length = sum(self.doc_lengths) / max(1, self.num_docs)

    def _idf(self, term: str) -> float:
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0.0
        return math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1)

    def _score_document(self, query_tokens: List[str], doc_idx: int) -> float:
        score = 0.0
        doc_len = self.doc_lengths[doc_idx]
        term_freq = self.term_freqs[doc_idx]

        for term in query_tokens:
            if term not in term_freq:
                continue
            tf = term_freq[term]
            idf = self._idf(term)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_length))
            score += idf * (numerator / denominator)

        return score

    def search(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, str, Dict[str, Any], float]]:
        if self.num_docs == 0:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: List[Tuple[int, float]] = []
        for idx in range(self.num_docs):
            if where:
                meta = self.metadatas[idx]
                match = True
                for key, value in where.items():
                    if meta.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            score = self._score_document(query_tokens, idx)
            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            results.append((
                self.doc_ids[idx],
                self.documents[idx],
                self.metadatas[idx],
                score,
            ))

        return results

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "documents": self.documents,
                    "doc_ids": self.doc_ids,
                    "metadatas": self.metadatas,
                    "doc_lengths": self.doc_lengths,
                    "avg_doc_length": self.avg_doc_length,
                    "doc_freqs": self.doc_freqs,
                    "term_freqs": self.term_freqs,
                    "num_docs": self.num_docs,
                    "k1": self.k1,
                    "b": self.b,
                },
                f,
            )
        logger.info("Saved BM25 index to %s with %s documents", path, self.num_docs)

    @classmethod
    def load(cls, path: str) -> "BM25Index":
        with open(path, "rb") as f:
            data = pickle.load(f)

        index = cls(k1=data["k1"], b=data["b"])
        index.documents = data["documents"]
        index.doc_ids = data["doc_ids"]
        index.metadatas = data["metadatas"]
        index.doc_lengths = data["doc_lengths"]
        index.avg_doc_length = data["avg_doc_length"]
        index.doc_freqs = data["doc_freqs"]
        index.term_freqs = data["term_freqs"]
        index.num_docs = data["num_docs"]

        logger.info("Loaded BM25 index from %s with %s documents", path, index.num_docs)
        return index


_bm25_indices: Dict[str, BM25Index] = {}


def get_bm25_index_path(collection_name: str = "grant_library") -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    backend_app_dir = os.path.abspath(os.path.join(here, ".."))
    return os.path.join(
        backend_app_dir,
        "data",
        "app_library",
        "vector_store",
        f"{collection_name}_bm25.pkl",
    )


def get_bm25_index(collection_name: str = "grant_library") -> BM25Index:
    if collection_name not in _bm25_indices:
        path = get_bm25_index_path(collection_name)
        if os.path.exists(path):
            _bm25_indices[collection_name] = BM25Index.load(path)
        else:
            _bm25_indices[collection_name] = BM25Index()
    return _bm25_indices[collection_name]


def save_bm25_index(index: BM25Index, collection_name: str = "grant_library") -> None:
    path = get_bm25_index_path(collection_name)
    index.save(path)
    _bm25_indices[collection_name] = index


def bm25_search(
    query: str,
    top_k: int = 10,
    collection_name: str = "grant_library",
    where: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, str, Dict[str, Any], float]]:
    index = get_bm25_index(collection_name)
    return index.search(query, top_k=top_k, where=where)
