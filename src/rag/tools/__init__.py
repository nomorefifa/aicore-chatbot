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


def get_tools(store=None) -> list:
    use_gcp = os.getenv("USE_GCP_SERVICES", "false").lower() == "true"

    if use_gcp:
        from src.rag.tools.gcp.vertex_search_tools import get_vertex_search_tools
        return get_vertex_search_tools()
        # BigQuery 도구는 데이터 적재 완료 후 아래로 교체
        # from src.rag.tools.gcp.bigquery_tools import get_bigquery_tools
        # return get_vertex_search_tools() + get_bigquery_tools()
    else:
        from src.rag.tools.chromadb.resume_tools import get_resume_tools
        return get_resume_tools(store)


# 하위 호환성 유지 — 기존 코드에서 get_resume_tools를 직접 import하는 경우 대비
def get_resume_tools(store):
    from src.rag.tools.chromadb.resume_tools import get_resume_tools as _get
    return _get(store)
