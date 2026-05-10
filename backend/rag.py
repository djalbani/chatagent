"""Vector store retrieval using ChromaDB — with lazy-loaded embeddings."""
import chromadb


class RAGSystem:
    def __init__(
        self,
        collection_name: str = "support_docs",
        persist_dir: str = "./chroma_db",
    ):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self._collection_name = collection_name
        self._collection = None   # lazy — only loaded on first use
        self._ef = None           # lazy — embedding model loaded on first use

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_ef(self):
        """Load the sentence-transformer model only when first needed."""
        if self._ef is None:
            from chromadb.utils import embedding_functions
            self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        return self._ef

    def _get_collection(self):
        """Get (or create) the ChromaDB collection, loading EF on demand."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self._collection_name,
                embedding_function=self._get_ef(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(self, query: str, n_results: int = 5) -> list[dict]:
        """Return top-k most relevant chunks for a query."""
        col = self._get_collection()
        count = col.count()
        if count == 0:
            return []
        results = col.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        chunks = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append({
                "content":  doc,
                "source":   meta.get("source", "unknown"),
                "filename": meta.get("filename", ""),
            })
        return chunks

    def add_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        col = self._get_collection()
        col.add(
            documents=[c["content"] for c in chunks],
            metadatas=[{k: v for k, v in c.items() if k != "content"} for c in chunks],
            ids=[c["id"] for c in chunks],
        )

    def delete_source(self, source: str) -> int:
        col = self._get_collection()
        results = col.get(where={"source": source})
        if results["ids"]:
            col.delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    def list_sources(self) -> list[str]:
        """Fast — uses get_collection (no EF load) so count/list are instant."""
        try:
            col = self.client.get_collection(name=self._collection_name)
            results = col.get()
            return sorted({m["source"] for m in results["metadatas"]})
        except Exception:
            return []

    def count(self) -> int:
        """Fast — uses get_collection (no EF load) so healthcheck is instant."""
        try:
            col = self.client.get_collection(name=self._collection_name)
            return col.count()
        except Exception:
            return 0
