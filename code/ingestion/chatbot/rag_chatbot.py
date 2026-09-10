import re
from typing import Tuple, List, Dict, Any, Optional, Union
from langchain_core.messages import HumanMessage
from langchain_core.vectorstores import VectorStore
from langchain_groq import ChatGroq
from langchain_qdrant import QdrantVectorStore
from loguru import logger
from chatbot.reranker import LegalReranker


class LegalRAGChatbot:
    """
    RAG Chatbot powered by LLMs and the persisted Qdrant Cloud legal vector database.
    Retrieves candidate chunks via cosine similarity, then re-ranks using LegalReranker
    across 5 signals: relevance, freshness, authority, jurisdiction, applicability.
    """

    def __init__(
        self,
        vector_store: Union[QdrantVectorStore, VectorStore],
        model_name: str = "qwen/qwen3-32b",
        top_k: int = 4,
        reranker: Optional[LegalReranker] = None,
        candidate_multiplier: int = 3,
    ):
        """
        Args:
            vector_store:          Qdrant vector store instance.
            model_name:            Groq LLM model name.
            top_k:                 Number of final chunks passed to the LLM.
            reranker:              Optional LegalReranker. Defaults to LegalReranker()
                                   with standard weights. Pass None to disable re-ranking.
            candidate_multiplier:  Over-retrieval factor. Fetches top_k * candidate_multiplier
                                   raw results from Qdrant before re-ranking.
        """
        self.vector_store = vector_store
        self.model_name = model_name
        self.top_k = top_k

        # NOTE: response_format json_object removed — Qwen/reasoning models don't
        # reliably honor it (JSON ends up inside <think> or wrapped in prose).
        # Plain text + manual thinking-strip is the more robust path across models.
        self.llm = ChatGroq(
            model=self.model_name,
            temperature=0.3,  # lowered from 0.7 — legal grounding wants determinism, not creativity
        )

        logger.info(self.llm)
        self.reranker = reranker if reranker is not None else LegalReranker()
        self.candidate_multiplier = candidate_multiplier

    def retrieve_context(self, query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieves top matching legal chunks from Qdrant and re-ranks them
        using LegalReranker before returning context to the LLM.
        """
        fetch_k = self.top_k * self.candidate_multiplier
        logger.info(
            f"Qdrant retrieval: fetching {fetch_k} candidates "
            f"(top_k={self.top_k} x multiplier={self.candidate_multiplier})..."
        )

        raw_results = self.vector_store.similarity_search_with_score(query, k=fetch_k)
        logger.info(f"Retrieved {len(raw_results)} raw candidates from Qdrant.")

        logger.info("Re-ranking candidates with LegalReranker...")
        reranked = self.reranker.rerank(query, raw_results)

        logger.info(
            f"\n{'='*72}\n"
            f"{'CHUNK ID':<35} {'RELEV':>6} {'FRESH':>6} {'AUTH':>5} "
            f"{'JURIS':>6} {'APPLI':>6} {'COMPOSITE':>10}\n"
            f"{'-'*72}"
        )
        for doc, composite, signals in reranked:
            cid = doc.metadata.get("chunk_id", "N/A")[:34]
            logger.info(
                f"{cid:<35} "
                f"{signals['relevance']:>6.3f} "
                f"{signals['freshness']:>6.3f} "
                f"{signals['authority']:>5.3f} "
                f"{signals['jurisdiction']:>6.3f} "
                f"{signals['applicability']:>6.3f} "
                f"{signals['composite']:>10.4f}"
            )
        logger.info("=" * 72)

        top_results = reranked[: self.top_k]

        context_blocks = []
        sources = []

        for doc, composite, signals in top_results:
            meta = doc.metadata
            source_info = {
                "id": meta.get("chunk_id", "N/A"),
                "provision": meta.get("provision_ref", "N/A"),
                "title": meta.get("section_title", "N/A"),
                "chapter": meta.get("chapter", "N/A"),
                "pages": f"{meta.get('start_page', '?')} to {meta.get('end_page', '?')}",
                "document_type": meta.get("document_type", "N/A"),
                "effective_from": meta.get("effective_from", "N/A"),
                "applicable_product": meta.get("applicable_product", "all"),
                "generated_context": meta.get("generated_context", ""),
                "rerank_scores": signals,
            }
            sources.append(source_info)

            original_content = meta.get("original_content", doc.page_content)
            block = (
                f"[{source_info['provision']} - {source_info['title']}] "
                f"(Chapter: {source_info['chapter']}, Pages: {source_info['pages']}, "
                f"Type: {source_info['document_type']}, Effective: {source_info['effective_from']}, "
                f"Re-rank score: {composite:.4f})\n"
                f"{original_content}"
            )
            context_blocks.append(block)

        formatted_context = "\n\n---\n\n".join(context_blocks)
        return formatted_context, sources

    def generate_response(self, query: str, context: str) -> str:
        """Queries the LLM with retrieved and re-ranked context. Returns clean plain-text response."""
        prompt = (
            f"You are a specialized legal advisor for an Ayurvedic Business in India.\n"
            f"You must give a grounded and precise answer based strictly on the retrieved statutory context below.\n"
            f"Always cite relevant Section numbers and titles.\n\n"
            f"CONTEXT:\n"
            f"{context}\n\n"
            f"QUESTION: {query}\n\n"
            f"Use ONLY the retrieved legal sources to support legal conclusions.\n\n"
            f"Do not introduce a statutory section, rule, case, regulation,\n"
            f"or legal proposition unless it appears in the retrieved sources.\n\n"
            f"If the retrieved sources are insufficient to answer the question,\n"
            f"say that the retrieved material is insufficient.\n\n"
            f"Do not infer the contents of a section from general legal knowledge.\n\n"
            f"Respond with plain text only. Do not wrap your answer in JSON, "
            f"markdown code fences, or any other structured format."
        )

        res = self.llm.invoke([HumanMessage(content=prompt)])
        raw_text = res.content

        return self._strip_thinking(raw_text)

    @staticmethod
    def _strip_thinking(raw: str) -> str:
        """
        Strips <think>...</think> / <|thinking|>...</|thinking|> blocks that
        reasoning models (Qwen3, DeepSeek-R1, etc.) emit before their answer.
        Returns only the final clean response text.
        """
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        cleaned = re.sub(r"<\|thinking\|>.*?<\|/thinking\|>", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    def ask(self, query: str) -> str:
        """Executes a single RAG query and displays the answer with citations."""
        print("\n" + "=" * 60)
        print(f"Query: {query}")
        print("=" * 60)

        context, sources = self.retrieve_context(query)

        print(f"\nTop {len(sources)} Re-ranked Sections:")
        print(f"  {'#':<3} {'Chunk ID':<35} {'Composite':>10}  Signals")
        print(f"  {'-'*75}")
        for idx, s in enumerate(sources, 1):
            sc = s["rerank_scores"]
            print(
                f"  [{idx}] {s['id'][:34]:<35} {sc['composite']:>10.4f}  "
                f"rel={sc['relevance']:.2f} fresh={sc['freshness']:.2f} "
                f"auth={sc['authority']:.2f} juris={sc['jurisdiction']:.2f} "
                f"appli={sc['applicability']:.2f}"
            )

        print(f"\nQuerying LLM model '{self.model_name}'...")
        answer = self.generate_response(query, context)
        print("\n" + "=" * 60)
        print("LEGAL RAG ANSWER:")
        print("=" * 60)
        print(answer)
        print("=" * 60 + "\n")
        return answer

    def start_chat(self):
        """Starts an interactive command-line chat session."""
        print("\n" + "=" * 60)
        print(f"Patents Act RAG Chatbot (Model: {self.model_name})")
        print("Type your question below, or type 'exit' / 'quit' to end.")
        print("=" * 60)

        while True:
            try:
                query = input("\nAsk a legal question: ").strip()
                if not query:
                    continue
                if query.lower() in ("exit", "quit", "q"):
                    print("Exiting chatbot session. Goodbye!")
                    break
                self.ask(query)
            except (KeyboardInterrupt, EOFError):
                print("\nSession ended.")
                break