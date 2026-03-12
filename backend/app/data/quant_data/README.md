# Quantitative Data Knowledge Base

This directory contains structured quantitative data files (CSV, XLSX) that are ingested as a secondary knowledge base alongside the text-rich documents in `app_library`.

## Supported File Types

- `.csv` - Comma-separated values
- `.xlsx` - Excel workbooks
- `.xls` - Legacy Excel files

## How Data is Processed

1. **Reading**: Each file is loaded using pandas for robust parsing
2. **Text Conversion**: Data is converted to a structured text format including:
   - File metadata (name, shape)
   - Column names and types
   - Numeric statistics (min, max, mean)
   - Sample rows
3. **Chunking**: Data is chunked with smaller sizes (800 chars) without overlap for denser retrieval
4. **Indexing**: Chunks are embedded and indexed in both:
   - ChromaDB (dense/semantic search)
   - BM25 index (keyword search)

## Usage

Place your CSV/XLSX files in this directory, then run the ingestion:

```python
from backend.app.rag.ingest import ingest_quant_data

# Ingest all quantitative data
result = ingest_quant_data(reset=True)
print(f"Ingested {result['files']} files, {result['chunks']} chunks")
```

Or ingest both knowledge bases at once:

```python
from backend.app.rag.ingest import ingest_all

result = ingest_all(reset=True)
```

## Retrieval

The quant_data collection is automatically queried alongside app_library:

```python
from backend.app.rag.retrieve import retrieve_from_both_sources

results = retrieve_from_both_sources(
    query="housing statistics in Nunavut",
    top_k=6,
    use_hybrid=True,
    rerank_provider="cohere"
)
```
