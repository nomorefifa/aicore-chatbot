"""
BigQuery 기반 강사 정형 데이터 조회 도구

구조화된 데이터(이름, 연락처, 이메일 등)를 SQL로 정확하게 조회합니다.
비정형 텍스트 검색은 vertex_search_tools.py를 사용하세요.
"""

from langchain_core.tools import tool
from google.cloud import bigquery

PROJECT_ID = "test-icore"
DATASET = "aicore_test_bigQuery"
TABLE = "teacher-resume"

bq_client = bigquery.Client(project=PROJECT_ID)


def get_bigquery_tools() -> list:

    @tool
    def list_all_instructors() -> str:
        """
        DB에 등록된 전체 강사 목록과 기본 정보를 반환합니다.
        '강사 몇 명이야', '전체 강사 보여줘', '강사 리스트 뽑아줘' 같은 질문에 사용하세요.
        """
        sql = f"""
        SELECT instructor_name, phone, email, expertise
        FROM `{PROJECT_ID}.{DATASET}.{TABLE}`
        ORDER BY instructor_name
        """
        rows = list(bq_client.query(sql).result())
        if not rows:
            return "등록된 강사가 없습니다."
        lines = [f"총 {len(rows)}명\n"]
        for i, row in enumerate(rows, 1):
            lines.append(
                f"{i}. {row['instructor_name']} "
                f"| {row.get('phone', '')} "
                f"| {row.get('email', '')} "
                f"| {row.get('expertise', '')}"
            )
        return "\n".join(lines)

    @tool
    def get_instructor_detail(instructor_name: str) -> str:
        """
        특정 강사의 상세 정보를 조회합니다.
        강사 이름을 정확히 입력하세요. 예: '강명희'
        """
        sql = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE instructor_name = @name
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("name", "STRING", instructor_name)
            ]
        )
        rows = list(bq_client.query(sql, job_config=job_config).result())
        if not rows:
            return f"'{instructor_name}' 강사를 찾지 못했습니다."
        return str(dict(rows[0]))

    return [list_all_instructors, get_instructor_detail]
