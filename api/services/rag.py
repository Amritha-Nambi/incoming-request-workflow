import os
import chromadb
from chromadb.utils import embedding_functions

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PERSIST_DIR = os.path.join(REPO_ROOT, "rag", "knowledge_base", ".chroma")
COLLECTION_NAME = "telecom_faq"

embedding_fn = embedding_functions.DefaultEmbeddingFunction()

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        # keep one client/collection around instead of reconnecting to chroma on every call
        client = chromadb.PersistentClient(path=PERSIST_DIR)
        _collection = client.get_collection(COLLECTION_NAME, embedding_function=embedding_fn)
    return _collection


def retrieve(query: str, k: int = 5) -> list[dict]:
    results = _get_collection().query(query_texts=[query], n_results=k)
    return [
        {"topic": meta["topic"], "content": doc}
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]
