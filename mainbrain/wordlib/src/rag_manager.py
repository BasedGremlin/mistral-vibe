"""
WORDLIB RAG Manager
===================
Indexes documents from storage/ subfolders using LlamaIndex + ChromaDB.
Runs entirely on USB -- all paths are relative to this file's location.

Folder layout expected:
  wordlib/
    src/
      rag_manager.py    <- this file
    storage/
      strategy/         <- .md/.txt files indexed for RAG
      recovery/
      research/
      kb/
      rag_index/        <- ChromaDB persistent store (auto-created)

Dependencies (installed by launcher.py):
  llama-index-core
  llama-index-vector-stores-chroma
  llama-index-embeddings-ollama
  llama-index-llms-ollama
  chromadb

Ollama must be running at 127.0.0.1:11434 before RAG is used.
Embed model: nomic-embed-text (pull once: ollama pull nomic-embed-text)
LLM model:   dolphin3 (Q4_K_M tag recommended for USB)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rag_manager")

# ── Paths (all relative to this file -- USB-portable) ─────────────────────
_SRC_DIR     = Path(__file__).resolve().parent          # wordlib/src/
_USB_ROOT    = _SRC_DIR.parent                           # wordlib/
_STORAGE_DIR = _USB_ROOT / "storage"
_INDEX_DIR   = _STORAGE_DIR / "rag_index"

# Subfolders to index. Must match actual folder names under storage/.
_TARGET_FOLDERS: List[str] = ["strategy", "recovery", "research", "kb"]

# Ollama endpoint (always local)
_OLLAMA_URL = "http://127.0.0.1:11434"

# Model tags -- verified on ollama.com/library June 2026
# LLM:   dolphin3:8b-llama3.1-q4_K_M  (4.9 GB, fits USB)
# Embed: nomic-embed-text              (274 MB, fast, standard)
_DEFAULT_LLM_MODEL   = "dolphin3:8b-llama3.1-q4_K_M"
_DEFAULT_EMBED_MODEL = "nomic-embed-text"


def semantic_context_for_rag_query(query_text: str, as_prompt: bool = True, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Optional read-only semantic hook for RAG prompt building.

    This does not build the vector index, does not ingest documents, does not
    write memory, and does not import graph internals. It only calls
    SemanticAdapter and returns a stable result dict.
    """
    try:
        from semantic_adapter import create_default_adapter
        adapter = create_default_adapter(auto_load=True, auto_save=False, storage_path=storage_path)
        result = adapter.context_for_query(query_text, as_prompt=as_prompt)
        data = result.to_dict()
        data["hook"] = "rag_manager.semantic_context_for_rag_query"
        data["read_only"] = True
        return data
    except Exception as exc:
        return {
            "ok": False,
            "operation": "semantic_context_for_rag_query",
            "data": {},
            "warnings": [],
            "error": f"{type(exc).__name__}: {exc}",
            "hook": "rag_manager.semantic_context_for_rag_query",
            "read_only": True,
        }


class USBRAGManager:
    """
    Builds and queries a ChromaDB vector index over the wordlib storage folders.
    Designed to be imported by usb_orchestrator.py and optionally by main.py.

    Usage:
        mgr = USBRAGManager()
        ok  = mgr.build_index()
        if ok:
            results = mgr.query("how do I handle recovery supplements?")
    """

    def __init__(
        self,
        llm_model:   str = _DEFAULT_LLM_MODEL,
        embed_model: str = _DEFAULT_EMBED_MODEL,
    ) -> None:
        self.llm_model   = llm_model
        self.embed_model = embed_model
        self.index: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._ready = False

        # Create storage dirs if they don't exist yet
        _INDEX_DIR.mkdir(parents=True, exist_ok=True)
        for folder in _TARGET_FOLDERS:
            (_STORAGE_DIR / folder).mkdir(parents=True, exist_ok=True)

        self._setup_llama_index()

    # ── Internal setup ─────────────────────────────────────────────────────

    def _setup_llama_index(self) -> None:
        """Configure LlamaIndex global settings. Fails gracefully if packages missing."""
        try:
            from llama_index.core import Settings
            from llama_index.embeddings.ollama import OllamaEmbedding
            from llama_index.llms.ollama import Ollama

            Settings.llm = Ollama(
                model=self.llm_model,
                base_url=_OLLAMA_URL,
                request_timeout=300.0,
            )
            Settings.embed_model = OllamaEmbedding(
                model_name=self.embed_model,
                base_url=_OLLAMA_URL,
            )
            Settings.chunk_size    = 512
            Settings.chunk_overlap = 50

        except ImportError as e:
            logger.error(
                f"LlamaIndex packages not installed: {e}. "
                "Run launcher.py with internet access to install RAG packages."
            )
            raise
        except Exception as e:
            logger.error(f"LlamaIndex setup failed: {e}")
            raise

    def _get_chroma_resources(self):
        """Return (chroma_client, collection, vector_store, storage_context)."""
        import chromadb
        from llama_index.vector_stores.chroma import ChromaVectorStore
        from llama_index.core import StorageContext

        client = chromadb.PersistentClient(path=str(_INDEX_DIR))
        collection = client.get_or_create_collection(
            name="wordlib_vault",
            metadata={"hnsw:space": "cosine"},
        )
        vector_store     = ChromaVectorStore(chroma_collection=collection)
        storage_context  = StorageContext.from_defaults(vector_store=vector_store)
        return client, collection, vector_store, storage_context

    # ── Public API ─────────────────────────────────────────────────────────

    def build_index(self) -> bool:
        """
        Scans storage/ subfolders for .md and .txt files, embeds them,
        and persists the index to storage/rag_index/.

        Returns True on success (even if no documents found -- existing index reused).
        Returns False on hard failure.
        """
        logger.info("Building RAG index from storage/ folders...")
        self._ready = False

        try:
            from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
            _, self._collection, vector_store, storage_context = self._get_chroma_resources()
        except Exception as e:
            logger.error(f"ChromaDB / LlamaIndex init failed: {e}")
            return False

        # Collect documents from all target folders
        all_docs = []
        for folder_name in _TARGET_FOLDERS:
            folder_path = _STORAGE_DIR / folder_name
            md_txt_files = list(folder_path.glob("**/*.md")) + list(folder_path.glob("**/*.txt"))
            if not md_txt_files:
                logger.debug(f"  {folder_name}/: empty, skipping")
                continue
            try:
                reader = SimpleDirectoryReader(
                    input_dir=str(folder_path),
                    required_exts=[".md", ".txt"],
                    recursive=True,
                )
                docs = reader.load_data()
                if docs:
                    logger.info(f"  {folder_name}/: {len(docs)} document(s) loaded")
                    all_docs.extend(docs)
            except Exception as e:
                logger.warning(f"  {folder_name}/: read error -- {e}")

        if not all_docs:
            # No documents yet -- load existing index if available, else empty index
            logger.info("No documents found. Loading existing index (if any).")
            try:
                from llama_index.core import VectorStoreIndex
                self.index = VectorStoreIndex.from_vector_store(
                    vector_store, storage_context=storage_context
                )
                self._ready = True
                return True
            except Exception as e:
                logger.warning(f"Could not load existing index: {e}")
                self._ready = False
                return False

        try:
            from llama_index.core import VectorStoreIndex
            self.index = VectorStoreIndex.from_documents(
                all_docs,
                storage_context=storage_context,
                show_progress=False,
            )
            chunk_count = self._collection.count() if self._collection else "?"
            logger.info(f"RAG index built. Total chunks: {chunk_count}")
            self._ready = True
            return True

        except Exception as e:
            logger.error(f"Index build failed: {e}")
            self._ready = False
            return False


    def semantic_context(self, query_text: str, as_prompt: bool = True) -> Dict[str, Any]:
        """Return optional read-only semantic context through SemanticAdapter."""
        return semantic_context_for_rag_query(query_text, as_prompt=as_prompt)

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Query the index. Returns a list of result dicts with keys:
          text   -- truncated chunk text
          score  -- cosine similarity score (float)
          source -- original file name
          folder -- which storage subfolder it came from

        Returns [] if index not ready or query fails.
        """
        if not self._ready or self.index is None:
            logger.warning("RAG query attempted but index not ready.")
            return []

        try:
            engine   = self.index.as_query_engine(similarity_top_k=top_k)
            response = engine.query(query_text)
            results  = []
            for node in response.source_nodes:
                file_path = node.node.metadata.get("file_path", "")
                # Derive which storage subfolder this came from
                try:
                    folder = Path(file_path).parent.name
                except Exception:
                    folder = "unknown"
                results.append({
                    "text":   node.node.text[:600],
                    "score":  round(float(node.score or 0.0), 4),
                    "source": node.node.metadata.get("file_name", "unknown"),
                    "folder": folder,
                })
            return results

        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Return current index health and chunk count."""
        try:
            if not self._collection:
                _, self._collection, _, _ = self._get_chroma_resources()
            return {
                "status":       "healthy" if self._ready else "not_ready",
                "total_chunks": self._collection.count(),
                "folders":      _TARGET_FOLDERS,
                "index_path":   str(_INDEX_DIR),
                "llm_model":    self.llm_model,
                "embed_model":  self.embed_model,
                "semantic_hook": "available_read_only",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def rebuild(self) -> bool:
        """Force a full rebuild (clears existing ChromaDB collection first)."""
        logger.info("Forcing RAG index rebuild...")
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(_INDEX_DIR))
            client.delete_collection("wordlib_vault")
            logger.info("Existing collection cleared.")
        except Exception as e:
            logger.warning(f"Could not clear collection: {e}")
        return self.build_index()

    @property
    def ready(self) -> bool:
        return self._ready
