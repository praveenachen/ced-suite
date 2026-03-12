# backend/app/rag/ingest.py
from __future__ import annotations

import csv
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from backend.app.rag.store import (
    get_collection, 
    stable_id, 
    get_app_library_dir, 
    get_quant_data_dir,
    DEFAULT_COLLECTION,
    QUANT_COLLECTION,
    SOURCE_APP_LIBRARY,
    SOURCE_QUANT_DATA,
)
from backend.app.rag.bm25 import BM25Index, save_bm25_index
from backend.app.rag.utils import logger

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# different ext
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
QUANT_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Stage 1.1) file reading 
# file readers 

def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

# Jimmy Phan - rewrote all read functions 

def _read_pdf_file(path: Path) -> str:
    parts: List[str] = []
    
    # Try PyPDF2/pypdf first
    reader_cls = None
    try:
        import PyPDF2
        reader_cls = PyPDF2.PdfReader
    except ImportError:
        try:
            from pypdf import PdfReader as PypdfReader
            reader_cls = PypdfReader
        except ImportError:
            reader_cls = None
    
    if reader_cls is not None:
        try:
            with open(path, "rb") as f:
                reader = reader_cls(f)
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
        except Exception as e:
            logger.warning(f"PyPDF2 failed for {path}: {e}")
            parts = []
    
    text = "\n".join(parts).strip()
    if len(text) > 200:
        return text
    
    # Fallback to pdfplumber
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except ImportError:
        logger.warning("pdfplumber not installed, PDF text extraction may be incomplete")
        return text
    except Exception as e:
        logger.warning(f"pdfplumber failed for {path}: {e}")
        return text


def _read_docx_file(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except ImportError:
        logger.warning("python-docx not installed, skipping DOCX file")
        return ""
    except Exception as e:
        logger.warning(f"Failed to read DOCX {path}: {e}")
        return ""


def _read_csv_file(path: Path) -> str:
    try:
        import pandas as pd
        df = pd.read_csv(path)
        return _dataframe_to_text(df, path.name)
    except ImportError:
        # Fallback to csv module
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return ""
        headers = rows[0]
        text_parts = [f"File: {path.name}", f"Columns: {', '.join(headers)}", ""]
        for row in rows[1:]:
            row_text = " | ".join(f"{h}: {v}" for h, v in zip(headers, row))
            text_parts.append(row_text)
        return "\n".join(text_parts)


def _read_excel_file(path: Path) -> str:
    try:
        import pandas as pd
        df = pd.read_excel(path)
        return _dataframe_to_text(df, path.name)
    except ImportError:
        logger.warning("pandas/openpyxl not installed, skipping Excel file")
        return ""
    except Exception as e:
        logger.warning(f"Failed to read Excel {path}: {e}")
        return ""


def _dataframe_to_text(df, filename: str) -> str:
    """
    Convert a pandas DataFrame to a structured text representation.
    Optimized for RAG by including column descriptions and statistics.
    """
    import pandas as pd
    
    text_parts = [
        f"=== Data File: {filename} ===",
        f"Shape: {df.shape[0]} rows x {df.shape[1]} columns",
        f"Columns: {', '.join(df.columns.tolist())}",
        ""
    ]
    
    # Add column statistics for numeric columns
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        text_parts.append("=== Numeric Column Statistics ===")
        for col in numeric_cols:
            text_parts.append(f"{col}: min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}")
        text_parts.append("")
    
    # Add sample data rows
    text_parts.append("=== Sample Data ===")
    sample_size = min(20, len(df))
    for idx, row in df.head(sample_size).iterrows():
        row_text = " | ".join(f"{col}: {val}" for col, val in row.items())
        text_parts.append(row_text)
    
    if len(df) > sample_size:
        text_parts.append(f"... and {len(df) - sample_size} more rows")
    
    return "\n".join(text_parts)

# universal file reader, works for all ext
def read_file(path: Path) -> str:

    suffix = path.suffix.lower()
    
    if suffix in TEXT_EXTENSIONS:
        return _read_text_file(path)
    elif suffix in PDF_EXTENSIONS:
        return _read_pdf_file(path)
    elif suffix in DOCX_EXTENSIONS:
        return _read_docx_file(path)
    elif suffix == ".csv":
        return _read_csv_file(path)
    elif suffix in {".xlsx", ".xls"}:
        return _read_excel_file(path)
    else:
        logger.warning(f"Unsupported file type: {suffix}")
        return ""


# Stage 1.2) Chunking

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """
    Simple char-based chunker. Good enough for demo; can swap later for token chunking.
    """
    text = (text or "").strip()
    if not text:
        return []

    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + chunk_size)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        if j >= n:
            break
        i = j - overlap
    return chunks


def chunk_quantitative_data(text: str, chunk_size: int = 800) -> List[str]:
    """
    Chunk quantitative data with smaller chunks and no overlap.
    Quantitative data benefits from denser, more focused chunks.
    """
    text = (text or "").strip()
    if not text:
        return []
    
    # Split by lines first to avoid breaking mid-row
    lines = text.split("\n")
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_size = 0
    
    for line in lines:
        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0
        current_chunk.append(line)
        current_size += line_size
    
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    
    return chunks


# Stage 1.3) Embedding
def embed_texts(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Embed texts using OpenAI with batching for large inputs."""
    if not texts:
        return []
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    all_embeddings: List[List[float]] = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        all_embeddings.extend([r.embedding for r in resp.data])
    
    return all_embeddings


# Stage 1.4) Ingesting 
# there are 4 functions

def ingest_folder(
    library_dir: str,
    persist_dir: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION,
    reset: bool = False,
    source_tag: Optional[str] = None,
    use_case: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Ingests text-rich documents (TXT, PDF, DOCX, MD) from a directory.
    Also builds a parallel BM25 index for keyword search.
    """
    lib = Path(library_dir)
    lib.mkdir(parents=True, exist_ok=True)

    col = get_collection(persist_dir=persist_dir, collection_name=collection_name)
    
    # Initialize BM25 index
    bm25_index = BM25Index()

    if reset:
        try:
            col.delete(where={})
        except Exception:
            pass

    # Find text-rich files
    extensions = TEXT_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS
    files = sorted([
        p for p in lib.rglob("*") 
        if p.is_file() and p.suffix.lower() in extensions
    ])

    total_chunks = 0
    added = 0

    for fp in files:
        raw = read_file(fp)
        chunks = chunk_text(raw)

        if not chunks:
            continue

        embeddings = embed_texts(chunks)

        ids: List[str] = []
        metas: List[Dict] = []
        for idx, chunk in enumerate(chunks):
            source = str(fp.relative_to(lib)).replace("\\", "/")
            chunk_id = stable_id(chunk, source=source)
            ids.append(chunk_id)
            meta: Dict[str, Any] = {
                "source": source, 
                "chunk_index": idx,
                "source_type": SOURCE_APP_LIBRARY,
                "file_type": fp.suffix.lower()
            }
            if source_tag:
                meta["source_tag"] = source_tag
            if use_case:
                meta["use_case"] = use_case
            if extra_metadata:
                meta.update(extra_metadata)
            metas.append(meta)

        col.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metas,
        )
        
        # Add to BM25 index
        bm25_index.add_documents(chunks, ids, metas)

        total_chunks += len(chunks)
        added += len(chunks)
        logger.info(f"Ingested {fp.name}: {len(chunks)} chunks")

    # Save BM25 index
    save_bm25_index(bm25_index, collection_name)
    
    return {"files": len(files), "chunks": total_chunks, "added": added}


def ingest_quant_data(
    data_dir: Optional[str] = None,
    persist_dir: Optional[str] = None,
    collection_name: str = QUANT_COLLECTION,
    reset: bool = False,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Ingests quantitative data files (CSV, XLSX) from the quant-data directory.
    """
    if data_dir is None:
        data_dir = get_quant_data_dir()
    
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    col = get_collection(persist_dir=persist_dir, collection_name=collection_name)
    bm25_index = BM25Index()

    if reset:
        try:
            col.delete(where={})
        except Exception:
            pass

    files = sorted([
        p for p in data_path.rglob("*") 
        if p.is_file() and p.suffix.lower() in QUANT_EXTENSIONS
    ])

    total_chunks = 0
    added = 0

    for fp in files:
        raw = read_file(fp)
        chunks = chunk_quantitative_data(raw)

        if not chunks:
            continue

        embeddings = embed_texts(chunks)

        ids: List[str] = []
        metas: List[Dict] = []
        for idx, chunk in enumerate(chunks):
            source = str(fp.relative_to(data_path)).replace("\\", "/")
            chunk_id = stable_id(chunk, source=source)
            ids.append(chunk_id)
            meta: Dict[str, Any] = {
                "source": source,
                "chunk_index": idx,
                "source_type": SOURCE_QUANT_DATA,
                "file_type": fp.suffix.lower(),
                "data_type": "quantitative"
            }
            if extra_metadata:
                meta.update(extra_metadata)
            metas.append(meta)

        col.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metas,
        )
        
        bm25_index.add_documents(chunks, ids, metas)

        total_chunks += len(chunks)
        added += len(chunks)
        logger.info(f"Ingested quant data {fp.name}: {len(chunks)} chunks")

    save_bm25_index(bm25_index, collection_name)
    
    return {"files": len(files), "chunks": total_chunks, "added": added}


def ingest_all(
    reset: bool = False,
    persist_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest both knowledge bases: app_library and quant_data.
    """
    logger.info("Starting full ingestion of both knowledge bases...")
    
    # Ingest app_library (text-rich documents)
    app_lib_dir = get_app_library_dir()
    app_lib_result = ingest_folder(
        library_dir=app_lib_dir,
        persist_dir=persist_dir,
        collection_name=DEFAULT_COLLECTION,
        reset=reset,
        source_tag="app_library"
    )
    logger.info(f"App library ingestion complete: {app_lib_result}")
    
    # Ingest quant_data (quantitative files)
    quant_data_dir = get_quant_data_dir()
    quant_result = ingest_quant_data(
        data_dir=quant_data_dir,
        persist_dir=persist_dir,
        collection_name=QUANT_COLLECTION,
        reset=reset
    )
    logger.info(f"Quant data ingestion complete: {quant_result}")
    
    return {
        "app_library": app_lib_result,
        "quant_data": quant_result,
        "total_files": app_lib_result["files"] + quant_result["files"],
        "total_chunks": app_lib_result["chunks"] + quant_result["chunks"]
    }

