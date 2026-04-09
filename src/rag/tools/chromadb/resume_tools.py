"""
강사 이력서 검색 도구 모음 (ChromaDB 기반)

새 도구 추가 시 동일한 패턴으로 작성:
    tools/chromadb/lecture_tools.py   → 강의자료 도구
    tools/chromadb/contract_tools.py  → 계약서 도구
"""

from langchain_core.tools import tool
from src.embedding.embedder import EmbeddingStore


def _resolve_instructor_name(store: EmbeddingStore, instructor_name: str) -> str | None:
    """
    입력된 이름과 DB에 저장된 이름의 공백 차이를 무시하고 정확한 이름을 반환.
    예: '유진혁' → '유 진 혁'
    없으면 None 반환.
    """
    query_norm = instructor_name.replace(" ", "")
    result = store.db._collection.get(
        where={"section": "프로필"},
        include=["metadatas"],
    )
    for meta in result["metadatas"]:
        stored = meta["instructor_name"]
        if stored == instructor_name or stored.replace(" ", "") == query_norm:
            return stored
    return None


def get_resume_tools(store: EmbeddingStore) -> list:
    """강사 이력서 검색 도구 목록 반환"""

    @tool
    def search_instructor(query: str) -> str:
        """
        강사 이력서에서 전문분야·역량 기준으로 관련 강사를 검색합니다.
        강사 추천, 전문분야 검색, 일반적인 강사 질의에 사용하세요.
        결과는 강사별로 묶어서 반환됩니다.
        """
        docs = store.db.similarity_search(query, k=10)
        if not docs:
            return "관련 강사를 찾지 못했습니다."

        seen: dict[str, list[str]] = {}
        for doc in docs:
            name = doc.metadata["instructor_name"]
            seen.setdefault(name, []).append(
                f"  [{doc.metadata['section']}] {doc.page_content}"
            )

        blocks = []
        for name, lines in seen.items():
            blocks.append(f"[{name}]\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    @tool
    def search_teaching_history(query: str) -> str:
        """
        강사들의 강의이력만 검색합니다.
        특정 과목, 기관, 강의 경험을 찾을 때 사용하세요.
        예: 'Python 강의', '삼성 강의 경험', '데이터분석 과정'
        """
        docs = store.db.similarity_search(
            query, k=8, filter={"section": "강의이력"}
        )
        if not docs:
            return "관련 강의이력을 찾지 못했습니다."
        return "\n\n".join(
            f"[{doc.metadata['instructor_name']}]\n{doc.page_content}"
            for doc in docs
        )

    @tool
    def get_instructor_detail(instructor_name: str) -> str:
        """
        특정 강사의 전체 정보(연락처, 이메일, 학력, 경력, 강의이력, 자격증 등)를 조회합니다.
        강사 이름을 입력하세요. 예: '박영준', '유진혁', '김승현'
        """
        matched_name = _resolve_instructor_name(store, instructor_name)
        if not matched_name:
            return f"'{instructor_name}' 강사를 찾지 못했습니다. 이름을 다시 확인하세요."

        result = store.db._collection.get(
            where={"instructor_name": matched_name},
            include=["documents", "metadatas"],
        )
        if not result["documents"]:
            return f"'{matched_name}' 강사 정보를 찾지 못했습니다."

        section_order = {"프로필": 0, "학력": 1, "경력": 2, "강의이력": 3, "자격증": 4}
        items = sorted(
            zip(result["documents"], result["metadatas"]),
            key=lambda x: section_order.get(x[1].get("section", ""), 99),
        )
        return "\n\n".join(
            f"[{meta['section']}]\n{doc}"
            for doc, meta in items
        )

    @tool
    def list_all_instructors() -> str:
        """
        DB에 저장된 전체 강사 목록을 반환합니다. 각 강사의 이름, 연락처, 이메일, 전문분야를 포함합니다.
        '강사 몇 명이야', '전체 강사 보여줘', '강사 리스트 뽑아줘', '연락처 목록' 같은 질문에 사용하세요.
        """
        result = store.db._collection.get(
            where={"section": "프로필"},
            include=["documents", "metadatas"],
        )
        if not result["documents"]:
            return "등록된 강사가 없습니다."

        items = sorted(
            zip(result["documents"], result["metadatas"]),
            key=lambda x: x[1]["instructor_name"],
        )
        lines = [f"총 {len(items)}명의 강사가 등록되어 있습니다.\n"]
        for i, (doc, _) in enumerate(items, 1):
            lines.append(f"{i}. {doc}")
        return "\n".join(lines)

    return [search_instructor, search_teaching_history, get_instructor_detail, list_all_instructors]
