"""
커리큘럼 검색 도구 모음 (ChromaDB 기반)

새 도구 추가 시 동일한 패턴으로 작성.
"""

from langchain_core.tools import tool
from src.embedding.embedder import EmbeddingStore


def get_curriculum_tools(store: EmbeddingStore) -> list:

    @tool
    def search_curriculum(query: str) -> str:
        """
        기존 교육 과정 DB에서 유사한 커리큘럼을 검색합니다.
        커리큘럼 생성/추천 요청 시 반드시 먼저 이 도구를 사용하세요.
        예: 'Python 데이터분석 비전공자', 'AWS 클라우드 초급 160시간'
        """
        docs = store.db.similarity_search(query, k=5)
        if not docs:
            return "관련 커리큘럼을 찾지 못했습니다."

        seen: dict[str, list[str]] = {}
        for doc in docs:
            name = doc.metadata.get("course_name", "unknown")
            seen.setdefault(name, []).append(
                f"  [{doc.metadata.get('section', '')}] {doc.page_content}"
            )

        blocks = []
        for name, lines in seen.items():
            blocks.append(f"[{name}]\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    @tool
    def search_curriculum_by_domain(domain: str) -> str:
        """
        특정 도메인/기술 분야의 커리큘럼을 검색합니다.
        예: 'AI', 'LLM', '클라우드', '데이터분석', 'IoT', '컴퓨터비전'
        """
        # ChromaDB: filter 키워드로 과정개요 섹션만 조회
        # Weaviate: filter 파라미터 무시 → 전체 검색 후 Python에서 필터
        docs = store.db.similarity_search(domain, k=8, filter={"section": "과정개요"})
        if not docs:
            docs = store.db.similarity_search(domain, k=8)

        if not docs:
            return f"'{domain}' 관련 커리큘럼을 찾지 못했습니다."

        target = [d for d in docs if d.metadata.get("section") == "과정개요"] or docs
        return "\n\n".join(d.page_content for d in target)

    @tool
    def get_curriculum_detail(course_name: str) -> str:
        """
        특정 과정의 전체 커리큘럼(모듈/주차별 세부 내용)을 조회합니다.
        과정명을 입력하세요. 예: 'Python 데이터분석', 'AWS Solution Architect'
        """
        section_order = {"과정개요": 0, "모듈": 1, "주차": 2}

        # ChromaDB 백엔드: 메타데이터 필터로 정확한 과정명 전체 조회
        _col = getattr(store.db, "_collection", None)
        if _col is not None and hasattr(_col, "get"):
            result = _col.get(
                where={"course_name": course_name},
                include=["documents", "metadatas"],
            )
            if result and result["documents"]:
                items = sorted(
                    zip(result["documents"], result["metadatas"]),
                    key=lambda x: section_order.get(x[1].get("section", ""), 99),
                )
                return "\n\n".join(
                    f"[{meta.get('section','')}]\n{doc}"
                    for doc, meta in items
                )

        # Weaviate 백엔드 또는 ChromaDB fallback: 유사도 검색 후 Python 필터
        docs = store.db.similarity_search(course_name, k=10)
        if not docs:
            return f"'{course_name}' 과정을 찾지 못했습니다."

        exact = [d for d in docs if d.metadata.get("course_name", "") == course_name]
        target = sorted(
            exact if exact else docs,
            key=lambda d: section_order.get(d.metadata.get("section", ""), 99),
        )
        return "\n\n".join(
            f"[{doc.metadata.get('section','')}]\n{doc.page_content}"
            for doc in target
        )

    return [search_curriculum, search_curriculum_by_domain, get_curriculum_detail]
