"""
Vertex AI Search 기반 강사 검색 도구

GCP 관리형 검색 서비스를 사용합니다.
파싱/청킹/임베딩은 Vertex AI Search가 내부적으로 처리합니다.
"""

import os
from langchain_core.tools import tool
from google.cloud import discoveryengine_v1 as discoveryengine

PROJECT_ID = "test-icore"
DATA_STORE_ID = os.getenv(
    "VERTEX_SEARCH_DATASTORE_ID",
    "aicore-test-agent-store_1775436080302"
)


def get_vertex_search_tools() -> list:

    search_client = discoveryengine.SearchServiceClient()
    serving_config = (
        f"projects/{PROJECT_ID}/locations/global"
        f"/collections/default_collection"
        f"/dataStores/{DATA_STORE_ID}"
        f"/servingConfigs/default_config"
    )

    # snippet + extractive answers 동시 요청
    content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
        snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
            return_snippet=True,
            max_snippet_count=3,
        ),
        extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
            max_extractive_answer_count=3,
        ),
    )

    def _extract_content(data: dict) -> str:
        """문서에서 실제 텍스트 내용을 추출. extractive_answers → extractive_segments → snippets 순으로 시도."""
        extractive_answers = data.get("extractive_answers", [])
        if extractive_answers:
            return "\n".join(a.get("content", "") for a in extractive_answers if a.get("content"))

        extractive_segments = data.get("extractive_segments", [])
        if extractive_segments:
            return "\n".join(s.get("content", "") for s in extractive_segments if s.get("content"))

        snippets = data.get("snippets", [])
        if snippets:
            return snippets[0].get("snippet", "")

        return ""

    @tool
    def search_instructor(query: str) -> str:
        """
        강사 이력서에서 전문분야·역량 기준으로 관련 강사를 검색합니다.
        강사 추천, 전문분야 검색, 강의 경험 검색에 사용하세요.
        """
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5,
            content_search_spec=content_search_spec,
        )
        response = search_client.search(request)

        results = []
        for r in response.results:
            data = r.document.derived_struct_data
            title = data.get("title", "이력서")
            text = _extract_content(data)
            if text:
                results.append(f"[{title}]\n{text}")

        return "\n\n".join(results) if results else "관련 강사를 찾지 못했습니다."

    @tool
    def search_teaching_history(query: str) -> str:
        """
        강사들의 강의이력을 검색합니다.
        특정 과목, 기관, 강의 경험을 찾을 때 사용하세요.
        예: 'Python 강의', '삼성 강의 경험', '데이터분석 과정'
        """
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=f"강의이력 {query}",
            page_size=5,
            content_search_spec=content_search_spec,
        )
        response = search_client.search(request)

        results = []
        for r in response.results:
            data = r.document.derived_struct_data
            title = data.get("title", "이력서")
            text = _extract_content(data)
            if text:
                results.append(f"[{title}]\n{text}")

        return "\n\n".join(results) if results else "관련 강의이력을 찾지 못했습니다."

    @tool
    def get_instructor_detail(instructor_name: str) -> str:
        """
        특정 강사의 상세 정보를 조회합니다.
        강사 이름을 입력하세요. 예: '박영준', '강명희', '허강욱'
        """
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=instructor_name,
            page_size=3,
            content_search_spec=content_search_spec,
        )
        response = search_client.search(request)

        results = []
        for r in response.results:
            data = r.document.derived_struct_data
            title = data.get("title", "이력서")
            text = _extract_content(data)
            if text:
                results.append(f"[{title}]\n{text}")

        return "\n\n".join(results) if results else f"'{instructor_name}' 강사를 찾지 못했습니다."

    @tool
    def list_all_instructors() -> str:
        """
        보유 강사 목록을 조회합니다.
        '강사 몇 명이야', '전체 강사 보여줘', '강사 리스트' 같은 질문에 사용하세요.
        """
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query="강사 이력서 프로필",
            page_size=20,
            content_search_spec=content_search_spec,
        )
        response = search_client.search(request)

        titles = []
        for r in response.results:
            data = r.document.derived_struct_data
            title = data.get("title", "")
            if title:
                titles.append(title)

        if not titles:
            return "등록된 강사를 찾지 못했습니다."

        lines = [f"총 {len(titles)}명의 강사 문서가 검색됩니다.\n"]
        for i, t in enumerate(titles, 1):
            lines.append(f"{i}. {t}")
        return "\n".join(lines)

    return [search_instructor, search_teaching_history, get_instructor_detail, list_all_instructors]
