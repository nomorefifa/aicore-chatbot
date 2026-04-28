"""
임베딩 + Weaviate 저장 모듈

EmbeddingStore(ChromaDB)와 동일한 인터페이스를 제공합니다.
기존 resume_tools.py, curriculum_tools.py 등 상위 코드 변경 없이 교체 가능합니다.

사용 예시:
    store = WeaviateEmbeddingStore(collection_name="instructor_resumes")
    store.add(chunks)
    store.db.similarity_search("Python 강의", k=5)

환경변수:
    WEAVIATE_HOST: Weaviate 서버 호스트 (기본값: localhost)
    WEAVIATE_PORT: Weaviate REST 포트 (기본값: 8080)
"""

import logging
import os

import weaviate
from langchain_core.documents import Document
from langchain_weaviate import WeaviateVectorStore

from src.parsing.models import Chunk

logger = logging.getLogger(__name__)


def _load_embedding_model(model: str, provider: str):
    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=model)

    if provider == "hf":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            raise ImportError(
                "HuggingFace 임베딩 사용 시 설치 필요:\n"
                "pip install langchain-huggingface sentence-transformers"
            )
        return HuggingFaceEmbeddings(model_name=model)

    raise ValueError(f"지원하지 않는 provider: {provider} (google / hf 중 선택)")


def _to_pascal(name: str) -> str:
    """컬렉션명 → Weaviate 클래스명 변환. Weaviate는 PascalCase 필요."""
    return "".join(word.capitalize() for word in name.split("_"))


class WeaviateEmbeddingStore:
    """
    Weaviate 기반 임베딩 저장/검색 클래스.
    EmbeddingStore(ChromaDB)와 동일한 인터페이스 제공.

    사용 예시:
        store = WeaviateEmbeddingStore()
        store.add(chunks)

        # LangChain 표준 함수 (ChromaDB와 동일)
        store.db.similarity_search("Python 강의", k=5)
        store.db.similarity_search_with_score("Python 강의", k=5)
    """

    def __init__(
        self,
        model: str = "models/gemini-embedding-001",
        provider: str = "google",
        collection_name: str = "instructor_resumes",
        host: str | None = None,
        port: int | None = None,
    ):
        self.collection_name = collection_name
        self.weaviate_class = _to_pascal(collection_name)

        _host = host or os.getenv("WEAVIATE_HOST", "localhost")
        _port = int(port or os.getenv("WEAVIATE_PORT", "8080"))

        self.client = weaviate.connect_to_local(host=_host, port=_port)
        embedding_model = _load_embedding_model(model, provider)

        self.db = WeaviateVectorStore(
            client=self.client,
            index_name=self.weaviate_class,
            text_key="text",
            embedding=embedding_model,
        )

        count = self.count()
        logger.info(
            f"Weaviate 연결 완료 | collection: {self.weaviate_class} "
            f"| host: {_host}:{_port} | 문서 수: {count}"
        )

    def add(self, chunks: list[Chunk], batch_size: int = 50) -> None:
        """청크 목록을 임베딩하여 Weaviate에 저장."""
        if not chunks:
            logger.warning("저장할 청크가 없습니다.")
            return

        documents = [
            Document(page_content=c.content, metadata=c.metadata)
            for c in chunks
        ]

        logger.info(f"임베딩 시작: {len(chunks)}개 청크")

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            self.db.add_documents(batch)
            logger.info(f"  저장 완료: {i + len(batch)}/{len(documents)}")

        logger.info(f"전체 저장 완료 | DB 총 청크 수: {self.count()}")

    def count(self) -> int:
        """현재 컬렉션에 저장된 총 청크 수."""
        try:
            col = self.client.collections.get(self.weaviate_class)
            result = col.aggregate.over_all(total_count=True)
            return result.total_count or 0
        except Exception:
            return 0

    def get_by_metadata(self, filter_dict: dict) -> list[dict]:
        """
        메타데이터 필터로 문서 전체 조회.
        반환: [{"content": str, "metadata": dict}, ...]
        EmbeddingStore(ChromaDB)와 동일한 인터페이스.
        """
        import weaviate.classes as wvc

        col = self.client.collections.get(self.weaviate_class)

        filters = None
        if len(filter_dict) == 1:
            key, val = next(iter(filter_dict.items()))
            filters = wvc.query.Filter.by_property(key).equal(val)
        else:
            filters = wvc.query.Filter.all_of([
                wvc.query.Filter.by_property(k).equal(v)
                for k, v in filter_dict.items()
            ])

        response = col.query.fetch_objects(filters=filters, limit=10000)

        return [
            {
                "content": obj.properties.get("text", ""),
                "metadata": {k: v for k, v in obj.properties.items() if k != "text"},
            }
            for obj in response.objects
        ]

    def delete_collection(self) -> None:
        """컬렉션 초기화 (재색인 시 사용)."""
        self.client.collections.delete(self.weaviate_class)
        logger.info(f"컬렉션 초기화 완료: {self.weaviate_class}")

    def close(self) -> None:
        """Weaviate 클라이언트 연결 종료."""
        self.client.close()
