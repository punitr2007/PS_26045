import os
import uuid
from typing import List, Optional
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
from loguru import logger

from structure.models import LegalDocumentConfig
from .embedding import EmbeddingFactory


class VectorStoreManager:
    """
    Manages Qdrant Cloud Vector Database indexing, collections, and document storage.
    Delegates embedding generation to EmbeddingFactory (Google Gemini or HuggingFace).
    Automatically detects and handles vector dimension changes across embedding models.
    """

    def __init__(self, config: LegalDocumentConfig):
        self.config = config
        self.qdrant_url = config.qdrant_url or os.getenv("CLUSTER_ENDPOINT")
        self.qdrant_api_key = config.qdrant_api_key or os.getenv("QDRANT_API_KEY")
        self.gemini_api_key = config.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.collection_name = config.collection_name or "legal_acts"
        
        # Determine provider and model
        self.embedding_provider = (config.embedding_provider or os.getenv("EMBEDDING_PROVIDER", "gemini")).lower()
        if config.embedding_model:
            self.embedding_model = config.embedding_model
        else:
            self.embedding_model = "models/gemini-embedding-001" if self.embedding_provider in ("gemini", "google", "google-genai") else "BAAI/bge-large-en-v1.5"

        self.client = self._init_client()
        self._embeddings: Optional[Embeddings] = None
        self._embedding_dim: int = EmbeddingFactory.get_dimension(self.embedding_provider, self.embedding_model)

    def _init_client(self) -> QdrantClient:
        """Initializes connection to Qdrant Cloud Cluster."""
        if not self.qdrant_url:
            raise ValueError(
                "Qdrant CLUSTER_ENDPOINT is missing. Please set CLUSTER_ENDPOINT in .env or config."
            )
        logger.info(f"Connecting to Qdrant Cloud endpoint: {self.qdrant_url}")
        return QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key, timeout=120)

    @property
    def embeddings(self) -> Embeddings:
        """Lazily initializes and caches the selected embedding model."""
        if self._embeddings is None:
            self._embeddings = EmbeddingFactory.create_embeddings(
                provider=self.embedding_provider,
                model_name=self.embedding_model,
                api_key=self.gemini_api_key
            )
        return self._embeddings

    def _ensure_collection_exists(self, force_recreate: bool = False) -> None:
        """Ensures the target collection exists in Qdrant with matching vector size, cosine metric, and payload indexes."""
        if self.client.collection_exists(self.collection_name):
            collection_info = self.client.get_collection(self.collection_name)
            existing_size = collection_info.config.params.vectors.size
            if existing_size != self._embedding_dim or force_recreate:
                logger.warning(
                    f"Qdrant collection '{self.collection_name}' has dimension {existing_size}, "
                    f"but active embedding model '{self.embedding_model}' requires {self._embedding_dim} dimensions. "
                    f"Recreating collection to match new model dimensions..."
                )
                self.client.delete_collection(self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            logger.info(
                f"Creating Qdrant collection '{self.collection_name}' "
                f"(size={self._embedding_dim}, provider={self.embedding_provider}, distance=COSINE)..."
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self._embedding_dim, distance=Distance.COSINE),
            )
            logger.info(f"Qdrant collection '{self.collection_name}' created successfully.")

        # Ensure keyword payload indexes for fast filtering on documents and structural hierarchy
        indexed_fields = [
            "metadata.source_id_external",
            "metadata.node_type",
            "metadata.chapter",
            "metadata.section",
            "metadata.article",
            "metadata.rule",
            "metadata.clause",
            "metadata.parent_id",
            "metadata.legal_area",
            "legal_area",
            "metadata.applicable_product",
            "applicable_product",
        ]
        for field in indexed_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword"
                )
            except Exception:
                pass

    def is_already_ingested(self) -> bool:
        """Checks if the Qdrant collection exists, has matching dimensions, and contains any points."""
        try:
            if not self.client.collection_exists(self.collection_name):
                return False
            collection_info = self.client.get_collection(self.collection_name)
            if collection_info.config.params.vectors.size != self._embedding_dim:
                return False
            return (collection_info.points_count or 0) > 0
        except Exception as e:
            logger.debug(f"Qdrant collection check error (will re-ingest): {e}")
            return False

    def is_document_already_ingested(self, source_id_external: Optional[str] = None) -> bool:
        """Checks if a specific document (by source_id_external) exists in the Qdrant collection."""
        target_id = source_id_external or self.config.source_id_external
        try:
            if not self.client.collection_exists(self.collection_name):
                return False

            collection_info = self.client.get_collection(self.collection_name)
            if collection_info.config.params.vectors.size != self._embedding_dim:
                return False

            self._ensure_collection_exists()

            # Query Qdrant with filter on source_id_external metadata payload
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.source_id_external",
                            match=MatchValue(value=target_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False
            )
            return len(points) > 0
        except Exception as e:
            logger.debug(f"Qdrant document check error for {target_id}: {e}")
            return False

    def store_documents(self, chunks: List[Document], persist: bool = True) -> Optional[QdrantVectorStore]:
        """Stores legal chunk documents into Qdrant Cloud collection using the active embedding model."""
        if not chunks:
            logger.error("No chunks provided for vector store ingestion.")
            return None

        self._ensure_collection_exists()

        # Qdrant requires IDs to be valid UUIDs or unsigned integers.
        # Generate deterministic UUIDv5 from each unique chunk_id.
        seen_ids = set()
        point_uuids = []
        for i, chunk in enumerate(chunks):
            cid = chunk.metadata.get("chunk_id", f"chunk_{i}")
            if cid in seen_ids:
                cid = f"{cid}_dup{i}"
                chunk.metadata["chunk_id"] = cid
            seen_ids.add(cid)

            # Convert string ID into a valid RFC 4122 UUID string for Qdrant
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, cid))
            point_uuids.append(point_uuid)

        logger.info(
            f"Ingesting {len(chunks)} chunks into Qdrant collection '{self.collection_name}' "
            f"via [{self.embedding_provider.upper()}: {self.embedding_model} ({self._embedding_dim}-dim)]..."
        )

        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings
        )

        # Upload in batches to avoid write timeout on large documents
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_ids = point_uuids[i:i + batch_size]
            logger.info(f"Uploading batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size} ({len(batch_chunks)} chunks)...")
            vector_store.add_documents(documents=batch_chunks, ids=batch_ids)

        logger.info(
            f"Successfully stored and indexed {len(chunks)} chunks in Qdrant collection '{self.collection_name}'."
        )
        return vector_store

    def get_vector_store(self) -> QdrantVectorStore:
        """Loads and returns a reference to the QdrantVectorStore."""
        self._ensure_collection_exists()
        return QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings
        )