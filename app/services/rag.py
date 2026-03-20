import io
import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class RAGService:
    """Serviço de Retrieval-Augmented Generation usando Supabase pgvector."""

    def __init__(self, supabase_client, openai_client: AsyncOpenAI):
        self._db = supabase_client
        self._openai = openai_client
        self._embedding_model = "text-embedding-3-small"
        self._chunk_size = 500
        self._chunk_overlap = 50

    # --------------------------------------------------
    # Embeddings
    # --------------------------------------------------

    async def _embed_text(self, text: str) -> list[float]:
        """Gera embedding para um texto usando OpenAI."""
        response = await self._openai.embeddings.create(
            model=self._embedding_model,
            input=text,
        )
        return response.data[0].embedding

    # --------------------------------------------------
    # Chunking
    # --------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        """Divide texto em chunks com overlap."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            chunk = text[start:end]

            # Tentar cortar em final de frase
            if end < len(text):
                last_period = chunk.rfind(".")
                last_newline = chunk.rfind("\n")
                cut_at = max(last_period, last_newline)
                if cut_at > self._chunk_size // 2:
                    chunk = chunk[: cut_at + 1]
                    end = start + cut_at + 1

            chunk = chunk.strip()
            if chunk:
                chunks.append(chunk)

            start = end - self._chunk_overlap
            if start >= len(text):
                break

        return chunks

    # --------------------------------------------------
    # Extração de texto
    # --------------------------------------------------

    def _extract_text(self, content_bytes: bytes, filetype: str) -> str:
        """Extrai texto de diferentes formatos de arquivo."""
        filetype = filetype.lower()

        if filetype in ("txt", "text/plain"):
            return content_bytes.decode("utf-8", errors="ignore")

        if filetype in ("pdf", "application/pdf"):
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)

        if filetype in (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            from docx import Document

            doc = Document(io.BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)

        raise ValueError(f"Tipo de arquivo não suportado: {filetype}")

    # --------------------------------------------------
    # Upload de documento
    # --------------------------------------------------

    async def upload_document(
        self, filename: str, content_bytes: bytes, filetype: str
    ) -> dict:
        """Processa e armazena um documento com embeddings."""
        # Extrair texto
        text = self._extract_text(content_bytes, filetype)
        if not text.strip():
            raise ValueError("Documento vazio ou sem texto extraível")

        # Chunkar
        chunks = self._chunk_text(text)
        logger.info(f"📄 Documento '{filename}': {len(chunks)} chunks")

        # Criar registro do documento
        doc_result = (
            await self._db.table("knowledge_documents")
            .insert(
                {
                    "filename": filename,
                    "filetype": filetype,
                    "file_size": len(content_bytes),
                    "chunk_count": len(chunks),
                }
            )
            .execute()
        )
        doc_id = doc_result.data[0]["id"]

        # Embedar e salvar chunks
        for i, chunk in enumerate(chunks):
            embedding = await self._embed_text(chunk)
            await self._db.table("knowledge_chunks").insert(
                {
                    "document_id": doc_id,
                    "content": chunk,
                    "chunk_index": i,
                    "embedding": embedding,
                }
            ).execute()

        logger.info(f"✅ Documento '{filename}' processado: {len(chunks)} chunks salvos")
        return doc_result.data[0]

    # --------------------------------------------------
    # Busca semântica
    # --------------------------------------------------

    async def get_relevant_context(
        self, query: str, threshold: float = 0.7, max_chunks: int = 3
    ) -> str:
        """Busca chunks relevantes para uma query."""
        try:
            query_embedding = await self._embed_text(query)

            result = await self._db.rpc(
                "match_knowledge_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": max_chunks,
                },
            ).execute()

            if not result.data:
                return ""

            chunks_text = "\n---\n".join([r["content"] for r in result.data])
            return f"Relevant teaching material:\n---\n{chunks_text}\n---"

        except Exception as e:
            logger.warning(f"⚠️ RAG search failed: {e}")
            return ""

    # --------------------------------------------------
    # CRUD documentos
    # --------------------------------------------------

    async def list_documents(self) -> list[dict]:
        """Lista todos os documentos."""
        result = (
            await self._db.table("knowledge_documents")
            .select("*")
            .order("uploaded_at", desc=True)
            .execute()
        )
        return result.data

    async def delete_document(self, document_id: str) -> bool:
        """Deleta um documento e seus chunks (cascade)."""
        await self._db.table("knowledge_documents").delete().eq(
            "id", document_id
        ).execute()
        logger.info(f"🗑️ Documento {document_id} deletado")
        return True
