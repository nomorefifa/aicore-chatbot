"""
강사 이력서 검색 도구 모음

새 문서 유형 추가 시 동일한 패턴으로 새 파일 생성:
    tools/lecture_tools.py   → 강의자료 도구
    tools/contract_tools.py  → 계약서 도구
"""

from langchain_core.tools import tool
from src.embedding.embedder import EmbeddingStore


def get_resume_tools(store: EmbeddingStore) -> list:
    """이력서 검색 도구 목록 반환"""

    @tool
    def search_instructor(query: str) -> str:
        """
        강사 이력서 전체에서 쿼리와 관련된 강사를 검색합니다.
        강사 추천, 전문분야 검색, 일반적인 강사 질의에 사용하세요.
        """
        docs = store.db.similarity_search(query, k=5)
        if not docs:
            return "관련 강사를 찾지 못했습니다."
        return "\n\n".join(
            f"[{doc.metadata['instructor_name']} / {doc.metadata['section']}]\n{doc.page_content}"
            for doc in docs
        )

    @tool
    def search_teaching_history(query: str) -> str:
        """
        강사들의 강의이력만 검색합니다.
        특정 과목, 기관, 강의 경험을 찾을 때 사용하세요.
        예: 'Python 강의', '삼성 강의 경험', '데이터분석 과정'
        """
        docs = store.db.similarity_search(
            query, k=5, filter={"section": "강의이력"}
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
        특정 강사의 전체 정보(학력, 경력, 강의이력, 자격증 등)를 조회합니다.
        강사 이름을 정확히 입력하세요. 예: '박영준', '김 승 현'
        """
        docs = store.db.similarity_search(
            instructor_name, k=10, filter={"instructor_name": instructor_name}
        )
        if not docs:
            return f"'{instructor_name}' 강사 정보를 찾지 못했습니다."

        section_order = {"프로필": 0, "학력": 1, "경력": 2, "강의이력": 3, "자격증": 4}
        docs.sort(key=lambda d: section_order.get(d.metadata.get("section", ""), 99))

        return "\n\n".join(
            f"[{doc.metadata['section']}]\n{doc.page_content}"
            for doc in docs
        )

    @tool
    def list_all_instructors() -> str:
        """
        DB에 저장된 전체 강사 목록과 총 인원수를 반환합니다.
        '강사 몇 명이야', '전체 강사 보여줘', '어떤 강사들이 있어' 같은 질문에 사용하세요.
        """
        result = store.db._collection.get(
            where={"section": "프로필"},
            include=["metadatas"]
        )
        names = sorted({m["instructor_name"] for m in result["metadatas"]})
        if not names:
            return "등록된 강사가 없습니다."
        name_list = "\n".join(f"{i+1}. {name}" for i, name in enumerate(names))
        return f"총 {len(names)}명의 강사가 등록되어 있습니다.\n\n{name_list}"

    return [search_instructor, search_teaching_history, get_instructor_detail, list_all_instructors]
