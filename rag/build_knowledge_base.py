import json
import os
import chromadb
from chromadb.utils import embedding_functions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSIST_DIR = os.path.join(BASE_DIR, "knowledge_base", ".chroma")
FAQ_PATH = os.path.join(BASE_DIR, "knowledge_base", "faq.json")
COLLECTION_NAME = "telecom_faq"

embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def build():
    with open(FAQ_PATH) as f:
        chunks = json.load(f)

    client = chromadb.PersistentClient(path=PERSIST_DIR)
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME, embedding_function=embedding_fn)

    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["content"] for c in chunks],
        metadatas=[{"topic": c["topic"]} for c in chunks],
    )
    print(f"Indexed {len(chunks)} chunks into '{COLLECTION_NAME}' at {PERSIST_DIR}")


if __name__ == "__main__":
    build()
