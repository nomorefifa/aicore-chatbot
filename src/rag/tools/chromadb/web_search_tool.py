"""
Gemini Google Search Grounding 기반 웹 검색 도구

Gemini API의 내장 Google Search 기능을 사용.
추가 API 키 불필요 (GOOGLE_API_KEY만 있으면 됨).
"""

import os
from langchain_core.tools import tool


def get_web_search_tool() -> list:

    @tool
    def web_search(query: str) -> str:
        """
        최신 기술 트렌드, 교육 동향을 구글에서 검색합니다.
        기존 DB 결과가 부족하거나 최신 정보가 필요할 때만 사용하세요.
        예: '2025 백엔드 개발자 교육 트렌드', 'LLM 커리큘럼 최신 동향'
        """
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools="google_search_retrieval",
        )

        response = model.generate_content(query)

        # 텍스트 응답 추출
        if response.candidates:
            return response.candidates[0].content.parts[0].text
        return "검색 결과를 가져오지 못했습니다."

    return [web_search]
