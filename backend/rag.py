"""Vector store retrieval using ChromaDB."""
import chromadb
from chromadb.utils import embedding_functions


class RAGSystem:
    def __init__(
        self,
        collection_name: str = "support_docs",
        persist_dir: str = "./chroma_db",
    ):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

    def retrieve(self, query: str, n_results: int = 5) -> list[dict]:
        """Return top-k most relevant chunks for a query."""
        count = self.collection.count()
        if count == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )

        chunks = []
        for doc, meta in zip(
            results["documents"][0], results["metadatas"][0]
        ):
            chunks.append(
                {
                    "content": doc,
                    "source": meta.get("source", "unknown"),
                    "filename": meta.get("filename", ""),
                }
            )
        return chunks

    def add_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        self.collection.add(
            documents=[c["content"] for c in chunks],
            metadatas=[
                {k: v for k, v in c.items() if k != "content"} for c in chunks
            ],
            ids=[c["id"] for c in chunks],
        )

    def delete_source(self, source: str) -> int:
        """Remove all chunks belonging to a source. Returns number deleted."""
        results = self.collection.get(where={"source": source})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    def list_sources(self) -> list[str]:
        results = self.collection.get()
        return sorted({m["source"] for m in results["metadatas"]})

    def count(self) -> int:
        return self.collection.count()
