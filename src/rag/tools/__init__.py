"""
도구 팩토리

USE_GCP_SERVICES 환경변수에 따라 도구 세트를 반환합니다.

false (기본값) → ChromaDB 기반 도구 (로컬)
true           → Vertex AI Search + BigQuery 기반 도구 (GCP)

새 도구 추가 시:
    chromadb/ 폴더 → 로컬 ChromaDB 기반 도구
    gcp/ 폴더      → GCP 서비스 기반 도구
"""

import os


def get_tools(resume_store=None, curriculum_store=None) -> list:
    use_gcp = os.getenv("USE_GCP_SERVICES", "false").lower() == "true"

    if use_gcp:
        from src.rag.tools.gcp.vertex_search_tools import get_vertex_search_tools
        return get_vertex_search_tools()

    tools = []

    if resume_store:
        from src.rag.tools.chromadb.resume_tools import get_resume_tools
        tools += get_resume_tools(resume_store)

    if curriculum_store:
        from src.rag.tools.chromadb.curriculum_tools import get_curriculum_tools
        tools += get_curriculum_tools(curriculum_store)

    from src.rag.tools.chromadb.web_search_tool import get_web_search_tool
    tools += get_web_search_tool()

    return tools
