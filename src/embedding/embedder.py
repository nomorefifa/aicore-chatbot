"""
임베딩 + ChromaDB 저장 모듈 (LangChain Chroma 래퍼 기반)

LangChain Chroma 래퍼를 사용하여 임베딩, 저장, 검색을 처리합니다.
similarity_search 등 LangChain 표준 함수를 그대로 사용할 수 있으며
이후 RAG 체인과 바로 연결됩니다.

컬렉션 분리 전략:
    EmbeddingStore(collection_name="instructor_resumes")  # 강사 이력서 (기본값)
    EmbeddingStore(collection_name="lecture_materials")   # 강의자료
    EmbeddingStore(collection_name="company_docs")        # 회사 문서

임베딩 모델 교체 방법:
    EmbeddingStore(model="models/gemini-embedding-001")          # Google (기본값)
    EmbeddingStore(model="models/text-embedding-004")            # Google 업그레이드
    EmbeddingStore(model="BAAI/bge-m3", provider="hf")          # 로컬 최고 성능
    EmbeddingStore(model="jhgan/ko-sroberta-multitask", provider="hf")  # 한국어 특화
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.parsing.models import Chunk

load_dotenv()

logger = logging.getLogger(__name__)


def _load_embedding_model(model: str, provider: str):
    """
    provider에 따라 임베딩 모델 로드.
    - "google" : Google Generative AI Embeddings (API)
    - "hf"     : HuggingFace sentence-transformers (로컬)
    """
    if provider == "google":
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


class EmbeddingStore:
    """
    LangChain Chroma 래퍼 기반 임베딩 저장/검색 클래스.

    사용 예시:
        store = EmbeddingStore()
        store.add(chunks)

        # LangChain 표준 함수
        store.db.similarity_search("Python 강의", k=5)
        store.db.similarity_search_with_score("Python 강의", k=5)
        store.db.similarity_search("Python 강의", k=5, filter={"section": "강의이력"})
    """

    def __init__(
        self,
        model: str = "models/gemini-embedding-001",
        provider: str = "google",
        collection_name: str = "instructor_resumes",
        db_dir: str | Path = "data/vector_db",
    ):
        self.collection_name = collection_name
        embedding_model = _load_embedding_model(model, provider)

        # LangChain Chroma 래퍼
        # - embedding_function: 텍스트 → 벡터 변환 담당
        # - persist_directory: 로컬 파일로 영구 저장
        # - collection_metadata: 코사인 유사도 사용
        self.db = Chroma(
            collection_name=collection_name,
            embedding_function=embedding_model,
            persist_directory=str(db_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )
        count = self.db._collection.count()
        logger.info(f"ChromaDB 연결 완료 | collection: {collection_name} | 저장 경로: {db_dir} | 문서 수: {count}")

    def add(self, chunks: list[Chunk], batch_size: int = 50) -> None:
        """
        청크 목록을 LangChain Document로 변환 후 임베딩하여 ChromaDB에 저장.
        이미 존재하는 ID는 덮어씀.

        LangChain Document = page_content(텍스트) + metadata(딕셔너리)
        → similarity_search 결과도 동일한 Document 형태로 반환됨
        """
        if not chunks:
            logger.warning("저장할 청크가 없습니다.")
            return

        # Chunk → LangChain Document 변환
        documents = [
            Document(page_content=c.content, metadata=c.metadata)
            for c in chunks
        ]
        ids = [self._make_id(c) for c in chunks]

        logger.info(f"임베딩 시작: {len(chunks)}개 청크 (배치 크기: {batch_size})")

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]

            self.db._collection.upsert(
                ids=batch_ids,
                documents=[d.page_content for d in batch_docs],
                metadatas=[d.metadata for d in batch_docs],
                embeddings=self.db._embedding_function.embed_documents(
                    [d.page_content for d in batch_docs]
                ),
            )
            logger.info(f"  저장 완료: {i + len(batch_docs)}/{len(documents)}")

        logger.info(f"전체 저장 완료 | DB 총 청크 수: {self.count()}")

    def count(self) -> int:
        """현재 DB에 저장된 총 청크 수"""
        return self.db._collection.count()

    def get_by_metadata(self, filter_dict: dict) -> list[dict]:
        """
        메타데이터 필터로 문서 전체 조회.
        반환: [{"content": str, "metadata": dict}, ...]
        """
        result = self.db._collection.get(
            where=filter_dict,
            include=["documents", "metadatas"],
        )
        return [
            {"content": doc, "metadata": meta}
            for doc, meta in zip(result["documents"], result["metadatas"])
        ]

    def delete_collection(self) -> None:
        """컬렉션 초기화 (재색인 시 사용)"""
        self.db.delete_collection()
        logger.info(f"컬렉션 초기화 완료: {self.collection_name}")

    def _make_id(self, chunk: Chunk) -> str:
        """청크 고유 ID 생성 (문서 타입 무관)"""
        meta = chunk.metadata

        # 주체 식별자: 강사명 or 과정명
        name = meta.get("instructor_name") or meta.get("course_name", "unknown")

        section = meta.get("section", "unknown")

        # 인덱스: 있는 필드 중 하나 사용
        idx = ""
        for field in ("teaching_index", "module_index", "week_number"):
            if field in meta:
                idx = f"_{meta[field]}"
                break

        return f"{name}_{section}{idx}"
