from backend.app.rag.ingest import ingest_folder

if __name__ == "__main__":
    res = ingest_folder(
        library_dir="backend/app/data/app_library",
        index_path="backend/app/data/caches/grants.faiss",
        meta_path="backend/app/data/caches/grants_meta.json",
        reset=True,
    )
    print(res)
